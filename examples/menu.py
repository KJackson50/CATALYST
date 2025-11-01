#!/usr/bin/env python3
"""
catalyst_menu.py
Menu-driven Cisco Catalyst Center (DNA Center) helper using your standard auth preamble.

Options:
  1) Get Devices
  2) Get Templates (projects)
  3) Run Command (Command Runner)
  4) Compliance Summary
  0) Exit
"""

import json
import time
import sys
import argparse
import requests
import getpass
from requests.exceptions import RequestException
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# === CONFIGURATION ===
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

DNAC = "https://10.147.3.62"        # Example: https://10.10.10.5
USERNAME = "206889554"

# === AUTHENTICATION ===
print("🔐 Catalyst Center Login")
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

auth_resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                          auth=(USERNAME, PASSWORD), verify=False)
auth_resp.raise_for_status()
token = auth_resp.json()["Token"]
HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}

print("[+] Authentication successful.\n")


# ===== Helpers =====
def pretty(obj):
    return json.dumps(obj, indent=2, sort_keys=True)


def _get(path: str, params=None):
    url = f"{DNAC}{path}"
    r = requests.get(url, headers=HEADERS, params=params or {}, verify=False, timeout=60)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return r.text


def _post(path: str, payload=None):
    url = f"{DNAC}{path}"
    r = requests.post(url, headers=HEADERS, json=payload or {}, verify=False, timeout=60)
    r.raise_for_status()
    return r.json()


def paginate(path: str, page_size: int = 500):
    """Simple paginator for list-style intent APIs."""
    results = []
    index = 1
    while True:
        data = _get(path, params={"offset": index, "limit": page_size})
        # Some Catalyst Center endpoints return {"response":[...]} while others may return a list directly
        chunk = data.get("response", data if isinstance(data, list) else [])
        if not chunk:
            break
        results.extend(chunk)
        if len(chunk) < page_size:
            break
        index += page_size
    return results


# ===== Actions =====
def action_get_devices():
    try:
        # If pagination params aren’t supported by your cluster version, fall back to single GET
        try:
            devices = paginate("/dna/intent/api/v1/network-device")
        except Exception:
            devices = _get("/dna/intent/api/v1/network-device").get("response", [])
        print(f"\n=== Devices ({len(devices)}) ===")
        for d in devices[:25]:
            host = d.get("hostname") or d.get("name") or "-"
            mgmt = d.get("managementIpAddress") or "-"
            series = d.get("series") or d.get("platformId") or "-"
            uuid = d.get("id") or d.get("instanceUuid") or "-"
            print(f"{host:30} {mgmt:16} {series:20} UUID: {uuid}")
        print()
    except RequestException as ex:
        print(f"[!] Error getting devices: {ex}")


def action_get_templates():
    try:
        data = _get("/dna/intent/api/v1/template-programmer/project")
        projects = data.get("response", [])
        print(f"\n=== Template Projects ({len(projects)}) ===")
        for p in projects:
            print(f"{p.get('name')}  |  ID: {p.get('id')}")
        print()
    except RequestException as ex:
        print(f"[!] Error getting template projects: {ex}")


def action_run_command():
    print("\nEnter one or more CLI commands. Blank line to end.")
    commands = []
    while True:
        line = input("cmd> ").strip()
        if not line:
            break
        commands.append(line)
    if not commands:
        print("No commands provided; canceled.\n")
        return

    # Choose targets
    print("\nChoose device UUIDs:")
    print("  1) Paste UUIDs manually")
    print("  2) List devices and select by index")
    choice = input("Select [1/2]: ").strip() or "1"

    device_uuids = []
    if choice == "2":
        try:
            devices = _get("/dna/intent/api/v1/network-device").get("response", [])
        except RequestException as ex:
            print(f"[!] Could not list devices: {ex}")
            return

        if not devices:
            print("No devices found.")
            return

        for i, d in enumerate(devices, start=1):
            host = d.get("hostname") or d.get("name") or "-"
            mgmt = d.get("managementIpAddress") or "-"
            uuid = d.get("id") or d.get("instanceUuid") or "-"
            print(f"{i:3}) {host:30} {mgmt:16} UUID: {uuid}")

        sel = input("Enter indexes (comma-separated): ").strip()
        if not sel:
            print("No selection; canceled.")
            return
        try:
            idxs = [int(x.strip()) for x in sel.split(",")]
            for i in idxs:
                device = devices[i - 1]
                uuid = device.get("id") or device.get("instanceUuid")
                if uuid:
                    device_uuids.append(uuid)
        except Exception:
            print("Invalid selection; canceled.")
            return
    else:
        raw = input("Paste UUIDs (comma-separated): ").strip()
        device_uuids = [x.strip() for x in raw.split(",") if x.strip()]

    if not device_uuids:
        print("No device UUIDs; canceled.\n")
        return

    # Submit
    try:
        body = {"commands": commands, "deviceUuids": device_uuids}
        resp = _post("/dna/intent/api/v1/network-device-poller/cli/read-request", body)
        task_id = resp["response"]["taskId"]
        print(f"Task submitted: {task_id}")
    except RequestException as ex:
        print(f"[!] Submit failed: {ex}")
        return

    # Poll task for fileId
    print("Polling task for results...")
    file_id = None
    last_progress = ""
    for _ in range(40):  # ~80s max (2s * 40)
        time.sleep(2)
        try:
            t = _get(f"/dna/intent/api/v1/task/{task_id}")
        except RequestException as ex:
            print(f"[!] Task poll error: {ex}")
            return

        resp = t.get("response", {})
        is_error = resp.get("isError")
        progress = resp.get("progress", "")
        if progress and progress != last_progress:
            print(f"...progress: {progress}")
            last_progress = progress

        if is_error:
            print("[!] Task reported error:")
            print(pretty(t))
            return

        # File id may appear in progress as JSON string or directly in response
        maybe = None
        if isinstance(progress, str):
            try:
                prog_obj = json.loads(progress)
                maybe = prog_obj.get("fileId")
            except Exception:
                pass
        file_id = maybe or resp.get("fileId")
        if file_id:
            break

    if not file_id:
        print("[!] No fileId found yet. Full task object:")
        print(pretty(t))
        return

    # Fetch results
    try:
        r = requests.get(f"{DNAC}/dna/intent/api/v1/file/{file_id}",
                         headers=HEADERS, verify=False, timeout=60)
        r.raise_for_status()
        try:
            result = r.json()
        except ValueError:
            result = r.text
        print("\n=== Command Runner Results ===")
        if isinstance(result, (list, dict)):
            print(pretty(result))
        else:
            print(result)
        print()
    except RequestException as ex:
        print(f"[!] Error fetching results: {ex}")


def action_compliance():
    try:
        data = _get("/dna/intent/api/v1/compliance")
        items = data.get("response", [])
        print(f"\n=== Compliance ({len(items)}) ===")
        for it in items:
            dev = it.get("deviceUuid") or it.get("entityId") or "-"
            status = it.get("status") or it.get("complianceType") or "-"
            cat = it.get("complianceType") or it.get("category") or ""
            print(f"{dev}  ->  {status}  {cat}")
        print()
    except RequestException as ex:
        print(f"[!] Error getting compliance: {ex}")


# ===== Main =====
def main():
    parser = argparse.ArgumentParser(description="Catalyst Center menu")
    parser.parse_args()  # (reserved; nothing yet)
    while True:
        print("""
======== Catalyst Center API ========
1) Get Devices
2) Get Templates (projects)
3) Run Command (Command Runner)
4) Compliance Summary
0) Exit
""")
        choice = input("Select: ").strip()
        if choice == "1":
            action_get_devices()
        elif choice == "2":
            action_get_templates()
        elif choice == "3":
            action_run_command()
        elif choice == "4":
            action_compliance()
        elif choice == "0":
            print("Goodbye.")
            break
        else:
            print("Invalid selection.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
