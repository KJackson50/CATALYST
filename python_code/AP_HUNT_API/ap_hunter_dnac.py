#!/usr/bin/env python3
"""
ap_hunter_dnac.py

Catalyst Center (DNAC) AP Hunter:
  - Runs "show power inline" and "show lldp neighbors" via Command Runner
  - Flags interfaces with PoE ON and NO LLDP neighbor
  - Writes per-switch files and combined_all_suspects.csv

Requirements:
  - Python 3.8+
  - pip install requests
"""

import os
import re
import time
import json
import csv
import argparse
from math import ceil
from getpass import getpass
from typing import List, Dict, Set

import requests

# ---------------------- USER INPUTS / ENVIRONMENT -----------------------
# 🔶 OPTION A: Hardcode DNAC_BASE here (uncomment and edit).
DNAC_BASE = "https:10.147.3.62"   ### 🔶 YOU EDIT HERE (optional)
# DNAC_BASE = os.getenv("DNAC_BASE", "").rstrip("/")  # or set as environment variable

# 🔶 VERIFY_TLS: set True if your DNAC uses a valid SSL certificate
VERIFY_TLS = os.getenv("DNAC_VERIFY_TLS", "false").lower() in ("1", "true", "yes")  ### 🔶 YOU EDIT HERE (optional)

# 🔶 OPTIONAL: set DNAC_USER / DNAC_PASS via env vars
# Example (Windows CMD): setx DNAC_USER netadmin
# Example (Linux/macOS): export DNAC_USER=netadmin
# -----------------------------------------------------------------------

SESSION = requests.Session()
SESSION.verify = VERIFY_TLS
SESSION.headers.update({"Content-Type": "application/json"})

SHORTEN_MAP = {
    "GigabitEthernet": "Gi",
    "TenGigabitEthernet": "Te",
    "TwentyFiveGigE": "Twe",
    "FortyGigabitEthernet": "Fo",
    "HundredGigE": "Hu",
    "FastEthernet": "Fa",
    "TwoGigabitEthernet": "Tw",
    "AppGigabitEthernet": "Ap",
    "Ethernet": "Eth",
}

# ---------------------- Interface normalization ------------------------
def norm_intf(name: str) -> str:
    if not name:
        return ""
    s = name.strip().rstrip(",:")
    s = re.sub(r"\s+", "", s)
    m = re.match(r"^([A-Za-z]{1,3})(.+)$", s)
    if m:
        prefix, rest = m.groups()
        if len(prefix) <= 3 and re.match(r"^\d", rest):
            return prefix[:2].capitalize() + rest
    for long, short in SHORTEN_MAP.items():
        if s.startswith(long):
            return short + s[len(long):]
    return s

def parse_poe_on(output: str) -> Set[str]:
    poe_on = set()
    if not output:
        return poe_on
    for line in output.splitlines():
        ln = line.strip()
        if not ln:
            continue
        if re.match(r"^(Interface|Port|Module|Available|Max|Admin|-----|Power)", ln, flags=re.IGNORECASE):
            continue
        m = re.match(r"^(?P<intf>[A-Za-z][A-Za-z0-9/._:-]+)\s+.*\b(on)\b", ln, flags=re.IGNORECASE)
        if m:
            poe_on.add(norm_intf(m.group("intf")))
    return poe_on

def parse_lldp_ports(output: str) -> Set[str]:
    lldp_ports = set()
    if not output:
        return lldp_ports
    lines = output.splitlines()
    # summary table form
    header_idx = None
    for i, ln in enumerate(lines):
        if re.search(r"\bLocal\s+Intf\b", ln, flags=re.IGNORECASE):
            header_idx = i
            break
    if header_idx is not None:
        for ln in lines[header_idx + 1:]:
            if not ln.strip() or re.match(r"^[=\-]{3,}\s*$", ln):
                continue
            first = ln.strip().split()[0]
            if re.match(r"^[A-Za-z][A-Za-z0-9/._:-]+$", first):
                lldp_ports.add(norm_intf(first))
    # fallback: detail form
    for ln in lines:
        m = re.search(r"Local\s+Intf\s*[:=]\s*([A-Za-z0-9/._:-]+)", ln, flags=re.IGNORECASE)
        if m:
            lldp_ports.add(norm_intf(m.group(1)))
    return lldp_ports

# ---------------------- DNAC API helpers -------------------------------
def dnac_token(base: str, user: str, pwd: str) -> str:
    url = f"{base}/dna/system/api/v1/auth/token"
    r = SESSION.post(url, auth=(user, pwd))
    r.raise_for_status()
    j = r.json()
    token = j.get("Token") or j.get("token") or j.get("response", {}).get("Token")
    if not token and "response" in j and isinstance(j["response"], dict):
        token = j["response"].get("Token") or j["response"].get("token")
    if not token:
        raise RuntimeError("DNAC token not found in response.")
    return token

def get_devices_map(base: str, headers: dict, hostnames: List[str]) -> Dict[str, str]:
    url = f"{base}/dna/intent/api/v1/network-device"
    devmap = {}
    params = {"offset": 1, "limit": 500}
    while True:
        r = SESSION.get(url, headers=headers, params=params)
        r.raise_for_status()
        resp = r.json().get("response", [])
        for d in resp:
            hn = (d.get("hostname") or "").strip()
            if hn:
                devmap[d["id"]] = hn
        if not resp or len(resp) < params["limit"]:
            break
        params["offset"] += params["limit"]
    if hostnames:
        want = set(h.lower() for h in hostnames)
        devmap = {k: v for k, v in devmap.items() if v.lower() in want}
    return devmap

def command_runner(base: str, headers: dict, device_ids: List[str], commands: List[str]) -> str:
    url = f"{base}/dna/intent/api/v1/network-device-poller/cli/read-request"
    payload = {"commands": commands, "deviceUuids": device_ids, "timeout": 0}
    r = SESSION.post(url, headers=headers, json=payload)
    r.raise_for_status()
    j = r.json()
    task_id = j.get("response", {}).get("taskId") or j.get("taskId")
    if not task_id:
        raise RuntimeError(f"No taskId in response: {j}")
    return task_id

def wait_for_file(base: str, headers: dict, task_id: str, timeout=300, poll=3) -> str:
    url = f"{base}/dna/intent/api/v1/task/{task_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = SESSION.get(url, headers=headers)
        r.raise_for_status()
        resp = r.json().get("response", {})
        prog = resp.get("progress")
        if prog:
            try:
                prog_json = json.loads(prog) if isinstance(prog, str) else prog
            except Exception:
                prog_json = {}
            if isinstance(prog_json, dict):
                file_id = prog_json.get("fileId") or prog_json.get("fileid")
                if file_id:
                    return file_id
        time.sleep(poll)
    raise TimeoutError(f"Timed out waiting for fileId (task {task_id})")

def get_file_json(base: str, headers: dict, file_id: str):
    url = f"{base}/dna/intent/api/v1/file/{file_id}"
    r = SESSION.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get("response")

def chunk_list(lst: List, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# ---------------------- Main ------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Catalyst Center AP Hunter")
    parser.add_argument("--hosts-file", help="Path to text file (one hostname per line).")
    parser.add_argument("--hostnames", nargs="*", help="Space-separated hostnames to target.")
    parser.add_argument("--out", default="./aphunt_dnac_out", help="Output folder for results.")
    parser.add_argument("--batch-size", type=int, default=50, help="Devices per Command Runner batch.")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds to wait per Command Runner task.")
    args = parser.parse_args()

    # Load hostnames
    hostnames = []
    if args.hosts_file:
        with open(args.hosts_file, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    hostnames.append(ln)
    elif args.hostnames:
        hostnames = [h.strip() for h in args.hostnames if h.strip()]
    else:
        print("[ERROR] No hosts provided. Use --hosts-file or --hostnames.")
        return
    if not hostnames:
        print("[ERROR] No valid hostnames found.")
        return

    # Credentials (no plaintext)
    base = DNAC_BASE or os.environ.get("DNAC_BASE", "").rstrip("/")
    if not base:
        print("[ERROR] DNAC_BASE not set. Edit script or set env var.")
        return
    dnac_user = os.getenv("DNAC_USER", "").strip() or input("Catalyst Center username: ").strip()
    dnac_pass = os.getenv("DNAC_PASS", "") or getpass("Catalyst Center password (hidden): ")

    try:
        token = dnac_token(base, dnac_user, dnac_pass)
    except Exception as e:
        print(f"[ERROR] Auth failed: {e}")
        return
    headers = {"X-Auth-Token": token, "Content-Type": "application/json"}

    print(f"Resolving {len(hostnames)} hostnames in Catalyst Center...")
    devmap = get_devices_map(base, headers, hostnames)
    if not devmap:
        print("[ERROR] No devices matched your list.")
        return

    lower_to_id = {v.lower(): k for k, v in devmap.items()}
    ordered_pairs = [(lower_to_id[h.lower()], devmap[lower_to_id[h.lower()]]) for h in hostnames if h.lower() in lower_to_id]

    os.makedirs(args.out, exist_ok=True)
    device_ids = [p[0] for p in ordered_pairs]
    total_batches = ceil(len(device_ids) / args.batch_size)
    print(f"Running Command Runner in {total_batches} batch(es)...")

    combined = []
    for batch_index, batch in enumerate(chunk_list(device_ids, args.batch_size), 1):
        print(f"  -> Batch {batch_index}/{total_batches} ({len(batch)} devices)")
        task_id = command_runner(base, headers, batch, ["show power inline", "show lldp neighbors"])
        file_id = wait_for_file(base, headers, task_id, timeout=args.timeout)
        results = get_file_json(base, headers, file_id)
        for item in results:
            dev_id = item.get("deviceUuid")
            host = devmap.get(dev_id, dev_id)
            succ = item.get("commandResponses", {}).get("SUCCESS", {}) or {}
            poe_txt = succ.get("show power inline", "") or ""
            lldp_txt = succ.get("show lldp neighbors", "") or ""
            poe_on = parse_poe_on(poe_txt)
            lldp_ports = parse_lldp_ports(lldp_txt)
            suspects = sorted(poe_on - lldp_ports)
            basepath = os.path.join(args.out, host)
            with open(f"{basepath}_poe_on.txt", "w") as f: f.write("\n".join(sorted(poe_on)))
            with open(f"{basepath}_lldp_local.txt", "w") as f: f.write("\n".join(sorted(lldp_ports)))
            with open(f"{basepath}_suspects.csv", "w", newline="") as f:
                w = csv.writer(f); w.writerow(["switch","interface","reason"])
                for iface in suspects: w.writerow([host, iface, "PoE on, no LLDP neighbor"])
            for iface in suspects:
                combined.append((host, iface))
            print(f"[OK] {host}: {len(suspects)} suspect port(s)")

    from datetime import datetime
    combined_path = os.path.join(args.out, "combined_all_suspects.csv")
    with open(combined_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["switch","interface","reason","timestamp"])
        ts = datetime.utcnow().isoformat() + "Z"
        for host, iface in sorted(combined):
            w.writerow([host, iface, "PoE on, no LLDP neighbor", ts])
    print(f"\n✅ Wrote combined suspects: {combined_path}")

if __name__ == "__main__":
    main()
