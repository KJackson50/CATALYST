#!/usr/bin/env python3
"""
Catalyst Center Command Runner (CSV-only version)
-------------------------------------------------
Runs read-only "show" commands via Catalyst Center Command Runner API
across a list of switches and exports a single CSV report.

REQUIREMENTS:
- Python 3.x
- requests library:  pip install requests
- switches.txt file with one IP or hostname per line
"""

import os, sys, time, json, csv, getpass, requests
from datetime import datetime
from typing import List, Dict, Any, Optional

# ======== EDIT ME: your Catalyst Center base URL ========
DNAC_BASE = "https://your-dnac.example.com"  # EDIT ME
# ========================================================
DEFAULT_SWITCHES_FILE = "switches.txt"

REQUEST_TIMEOUT = 30
POLL_INTERVAL_SEC = 2
POLL_TIMEOUT_SEC = 120


# ------------------- Helper Functions -------------------
def die(msg: str, code: int = 1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def read_switch_list(path: str) -> List[str]:
    if not os.path.exists(path):
        die(f"Switch list file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines()]
    return [x for x in lines if x and not x.startswith("#")]


def get_token(base: str, username: str, password: str) -> str:
    url = f"{base}/dna/system/api/v1/auth/token"
    resp = requests.post(url, auth=(username, password), timeout=REQUEST_TIMEOUT, verify=True)
    if resp.status_code != 200:
        die(f"Auth failed: HTTP {resp.status_code} -> {resp.text}")
    data = resp.json()
    token = data.get("Token") or data.get("token")
    if not token:
        die("Auth succeeded but token missing in response.")
    return token


def get_device_id_by_ip(base: str, token: str, ip: str) -> Optional[str]:
    url = f"{base}/dna/intent/api/v1/network-device/ip-address/{ip}"
    h = {"X-Auth-Token": token}
    r = requests.get(url, headers=h, timeout=REQUEST_TIMEOUT)
    if r.ok:
        j = r.json() or {}
        resp = j.get("response")
        if isinstance(resp, dict) and resp.get("id"):
            return resp["id"]
        if isinstance(resp, list) and resp and resp[0].get("id"):
            return resp[0]["id"]
    return None


def get_device_id_by_hostname_scan(base: str, token: str, name_or_ip: str) -> Optional[str]:
    h = {"X-Auth-Token": token}
    url = f"{base}/dna/intent/api/v1/network-device"
    offset, limit, tries = 1, 500, 0
    while tries < 20:
        r = requests.get(url, headers=h, params={"offset": offset, "limit": limit}, timeout=REQUEST_TIMEOUT)
        if not r.ok:
            break
        j = r.json() or {}
        devices = j.get("response") or []
        if not devices:
            break
        for d in devices:
            host = (d.get("hostname") or "").lower()
            mgmt_ip = (d.get("managementIpAddress") or "").lower()
            if name_or_ip.lower() in (host, mgmt_ip):
                return d.get("id")
        offset += limit
        tries += 1
    return None


def resolve_device_ids(base: str, token: str, targets: List[str]) -> Dict[str, str]:
    mapping = {}
    for t in targets:
        dev_id = get_device_id_by_ip(base, token, t) or get_device_id_by_hostname_scan(base, token, t)
        if dev_id:
            mapping[t] = dev_id
        else:
            print(f"[WARN] Could not resolve device ID for '{t}'. Skipping.")
    return mapping


def submit_command_runner(base: str, token: str, device_ids: List[str], commands: List[str], timeout_sec: int = 600):
    url = f"{base}/dna/intent/api/v1/network-device-poller/cli/read-request"
    payload = {"commands": commands, "deviceUuids": device_ids, "timeout": timeout_sec}
    h = {"X-Auth-Token": token, "Content-Type": "application/json"}
    r = requests.post(url, headers=h, json=payload, timeout=REQUEST_TIMEOUT)
    if not r.ok:
        die(f"Command Runner submit failed: HTTP {r.status_code} -> {r.text}")
    return r.json() or {}


def poll_command_result(base: str, token: str, submit_resp: Dict[str, Any]):
    h = {"X-Auth-Token": token}
    resp = submit_resp.get("response") if isinstance(submit_resp, dict) else None
    read_url = None
    if isinstance(resp, dict):
        if resp.get("url") and "/network-device-poller/cli/read-request/" in resp["url"]:
            read_url = resp["url"]
        elif resp.get("id"):
            read_url = f"/dna/intent/api/v1/network-device-poller/cli/read-request/{resp['id']}"
    task_id = resp.get("taskId") if isinstance(resp, dict) else None
    start = time.time()
    while time.time() - start < POLL_TIMEOUT_SEC:
        if read_url:
            r = requests.get(f"{base}{read_url}", headers=h, timeout=REQUEST_TIMEOUT)
            if r.ok:
                j = r.json() or {}
                if any(k in j for k in ("status", "deviceId", "commandResponses", "response")):
                    return j
        time.sleep(POLL_INTERVAL_SEC)
    die("Timed out waiting for Command Runner results.")
    return {}


def flatten_results(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    container = raw.get("response", raw)
    if isinstance(container, list):
        items = container
    elif isinstance(container, dict) and "result" in container and isinstance(container["result"], list):
        items = container["result"]
    else:
        items = [container]
    for item in items:
        if not isinstance(item, dict):
            continue
        device_id = item.get("deviceId") or item.get("deviceUuid") or item.get("id") or "unknown"
        cmd_resp = item.get("commandResponses") or {}
        for bucket in ("SUCCESS", "FAILURE", "BLACKLISTED", "TIMEOUT", "INVALID"):
            if bucket in cmd_resp and isinstance(cmd_resp[bucket], dict):
                for cmd, out in cmd_resp[bucket].items():
                    rows.append({
                        "deviceId": device_id,
                        "command": cmd,
                        "output": out,
                        "status": bucket
                    })
    return rows


def write_csv_report(rows: List[Dict[str, Any]], id_map: Dict[str, str]):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_name = f"cc_command_runner_{ts}.csv"
    dev_index = {v: k for k, v in id_map.items()}
    with open(csv_name, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "device_label", "device_id", "command", "status", "output"])
        stamp = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            label = dev_index.get(r["deviceId"], "")
            w.writerow([stamp, label, r["deviceId"], r["command"], r["status"], r.get("output", "")])
    print(f"\n✅ CSV report saved to: {os.path.abspath(csv_name)}")


# ------------------- Main Program -------------------
def main():
    print("\n=== Catalyst Center Command Runner (CSV-only) ===\n")

    path = input(f"Path to switch list file (Enter for '{DEFAULT_SWITCHES_FILE}'): ").strip() or DEFAULT_SWITCHES_FILE
    targets = read_switch_list(path)
    if not targets:
        die("No targets found in the switch list.")

    print("\nEnter the CLI command(s) to run (read-only).")
    print("Example: show interface status\nType 'y' to add another command.\n")
    commands = []
    while True:
        cmd = input("Command: ").strip()
        if cmd:
            commands.append(cmd)
        more = input("Add another? (y/n): ").strip().lower()
        if more != "y":
            break
    if not commands:
        die("No commands were provided.")

    username = os.getenv("DNAC_USERNAME") or input("Catalyst Center username: ").strip()
    password = os.getenv("DNAC_PASSWORD") or getpass.getpass("Catalyst Center password: ")
    if not DNAC_BASE or DNAC_BASE.startswith("https://your-dnac"):
        die("Please set DNAC_BASE at the top of the script.")
    token = get_token(DNAC_BASE, username, password)

    print("\nResolving device IDs...")
    id_map = resolve_device_ids(DNAC_BASE, token, targets)
    if not id_map:
        die("No device IDs resolved from your list. Nothing to run.")

    print(f"Submitting {len(commands)} command(s) for {len(id_map)} device(s)...")
    submit_resp = submit_command_runner(DNAC_BASE, token, list(id_map.values()), commands)

    print("Waiting for results...")
    raw_result = poll_command_result(DNAC_BASE, token, submit_resp)
    rows = flatten_results(raw_result)

    print("\n=== RESULTS SUMMARY ===")
    for r in rows:
        label = next((k for k, v in id_map.items() if v == r["deviceId"]), r["deviceId"])
        print(f"[{r['status']}] {label} :: {r['command']}")

    write_csv_report(rows, id_map)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
