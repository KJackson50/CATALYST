#!/usr/bin/env python3
"""
catalyst_api_snippets.py
Minimal, menu-driven Cisco Catalyst Center (DNA Center) API helper.

Features:
  - Secure password prompt (not stored)
  - Token auth
  - Get Devices
  - Get Templates (Template Programmer projects)
  - Run Command (Command Runner) with task polling + file fetch
  - Compliance summary

Usage:
  python catalyst_api_snippets.py
"""

import os
import sys
import time
import json
import getpass
import argparse
from typing import List, Dict, Any

import requests
from requests.exceptions import RequestException

# ======= Settings =======
VERIFY_SSL = False  # Set to True if your Catalyst Center has a valid cert

if not VERIFY_SSL:
    # Suppress "InsecureRequestWarning" if verify=False
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass


# ======= Helpers =======
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def pretty(obj):
    return json.dumps(obj, indent=2, sort_keys=True)


# ======= API Client =======
class CatalystClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.token = None
        self.headers = {}

    # --- Auth ---
    def get_token(self) -> str:
        url = f"{self.base_url}/dna/system/api/v1/auth/token"
        try:
            resp = requests.post(url, auth=(self.username, self.password),
                                 verify=VERIFY_SSL, timeout=self.timeout)
            resp.raise_for_status()
            token = resp.json().get("Token")
            if not token:
                raise RuntimeError("No 'Token' field found in auth response.")
            self.token = token
            self.headers = {"X-Auth-Token": token}
            return token
        except RequestException as ex:
            raise RuntimeError(f"Auth request failed: {ex}") from ex

    # --- Devices ---
    def get_devices(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/dna/intent/api/v1/network-device"
        resp = requests.get(url, headers=self.headers, verify=VERIFY_SSL, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("response", [])

    # --- Template Programmer (Projects) ---
    def get_template_projects(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/dna/intent/api/v1/template-programmer/project"
        resp = requests.get(url, headers=self.headers, verify=VERIFY_SSL, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("response", [])

    # --- Command Runner: submit ---
    def submit_command_runner(self, commands: List[str], device_uuids: List[str]) -> str:
        url = f"{self.base_url}/dna/intent/api/v1/network-device-poller/cli/read-request"
        body = {"commands": commands, "deviceUuids": device_uuids}
        resp = requests.post(url, headers=self.headers, json=body, verify=VERIFY_SSL, timeout=self.timeout)
        resp.raise_for_status()
        task_id = resp.json()["response"]["taskId"]
        return task_id

    # --- Task polling ---
    def get_task(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/dna/intent/api/v1/task/{task_id}"
        resp = requests.get(url, headers=self.headers, verify=VERIFY_SSL, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # --- File fetch (for Command Runner results) ---
    def get_file(self, file_id: str) -> Any:
        url = f"{self.base_url}/dna/intent/api/v1/file/{file_id}"
        resp = requests.get(url, headers=self.headers, verify=VERIFY_SSL, timeout=self.timeout)
        resp.raise_for_status()
        # Command Runner returns JSON; other endpoints may return bytes
        try:
            return resp.json()
        except ValueError:
            return resp.content

    # --- Compliance summary (coarse) ---
    def get_compliance(self) -> List[Dict[str, Any]]:
        # Per your spec: /dna/intent/api/v1/compliance
        url = f"{self.base_url}/dna/intent/api/v1/compliance"
        resp = requests.get(url, headers=self.headers, verify=VERIFY_SSL, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("response", [])


# ======= Menu Actions =======
def action_get_devices(client: CatalystClient):
    devices = client.get_devices()
    if not devices:
        print("No devices returned.")
        return
    print(f"\n=== Devices ({len(devices)}) ===")
    for d in devices:
        host = d.get("hostname") or d.get("name") or "<no-hostname>"
        mgmt = d.get("managementIpAddress") or d.get("ipAddress") or "-"
        series = d.get("series") or d.get("platformId") or "-"
        uuid = d.get("id") or d.get("instanceUuid") or "-"
        print(f"{host:30} {mgmt:16} {series:20} UUID: {uuid}")
    print()


def action_get_templates(client: CatalystClient):
    projects = client.get_template_projects()
    if not projects:
        print("No template projects found.")
        return
    print(f"\n=== Template Projects ({len(projects)}) ===")
    for p in projects:
        print(f"Project: {p.get('name')}  |  ID: {p.get('id')}")
    print()


def action_run_command(client: CatalystClient):
    print("\nEnter one or more CLI commands. Blank line to end.")
    commands = []
    while True:
        line = input("cmd> ").strip()
        if not line:
            break
        commands.append(line)
    if not commands:
        print("No commands provided; canceled.")
        return

    # Let user pick devices by UUID or by quick list
    print("\nChoose device UUIDs:")
    print("  1) Paste UUIDs manually")
    print("  2) List devices and select by index")
    choice = input("Select [1/2]: ").strip() or "1"

    device_uuids: List[str] = []
    if choice == "2":
        devices = client.get_devices()
        if not devices:
            print("No devices returned.")
            return
        for idx, d in enumerate(devices, start=1):
            host = d.get("hostname") or d.get("name") or "<no-hostname>"
            mgmt = d.get("managementIpAddress") or d.get("ipAddress") or "-"
            uuid = d.get("id") or d.get("instanceUuid") or "-"
            print(f"{idx:3}) {host:30} {mgmt:16} UUID: {uuid}")
        picks = input("Enter indexes (comma-separated): ").strip()
        if not picks:
            print("No selection; canceled.")
            return
        try:
            indexes = [int(p.strip()) for p in picks.split(",")]
            for i in indexes:
                device = devices[i - 1]
                uuid = device.get("id") or device.get("instanceUuid")
                if uuid:
                    device_uuids.append(uuid)
        except (ValueError, IndexError):
            print("Invalid selection; canceled.")
            return
    else:
        print("Paste device UUIDs (comma-separated):")
        raw = input("UUIDs: ").strip()
        device_uuids = [x.strip() for x in raw.split(",") if x.strip()]

    if not device_uuids:
        print("No device UUIDs; canceled.")
        return

    print("\nSubmitting Command Runner task...")
    try:
        task_id = client.submit_command_runner(commands, device_uuids)
        print(f"Task submitted: {task_id}")
    except Exception as ex:
        eprint(f"Submit failed: {ex}")
        return

    # Poll the task until fileId arrives or error
    print("Polling task for results...")
    file_id = None
    for _ in range(20):  # ~20 * 2s = 40 seconds max
        time.sleep(2)
        task = client.get_task(task_id)
        progress = task.get("response", {}).get("progress")
        is_error = task.get("response", {}).get("isError")
        if is_error:
            eprint("Task reports error:")
            print(pretty(task))
            return
        if progress:
            # Progress is often a JSON string containing "fileId"
            try:
                prog_obj = json.loads(progress) if isinstance(progress, str) else progress
            except json.JSONDecodeError:
                prog_obj = {}
            file_id = prog_obj.get("fileId") or task.get("response", {}).get("fileId")
            if file_id:
                break
        print("...still waiting")

    if not file_id:
        eprint("No fileId found in task progress; full task object:")
        print(pretty(task))
        return

    print(f"Fetching results (fileId={file_id})...")
    result = client.get_file(file_id)

    print("\n=== Command Runner Results ===")
    # Command Runner typically returns a list of dicts with 'deviceUuid', 'commandResponses'
    if isinstance(result, (list, dict)):
        print(pretty(result))
    else:
        # raw bytes content; try decode
        try:
            print(result.decode("utf-8", errors="replace"))
        except Exception:
            print(result)


def action_compliance(client: CatalystClient):
    try:
        items = client.get_compliance()
    except Exception as ex:
        eprint(f"Compliance call failed: {ex}")
        return

    if not items:
        print("No compliance data returned.")
        return

    print(f"\n=== Compliance ({len(items)}) ===")
    # Items can vary by system; print a few common fields if present
    for it in items:
        dev = it.get("deviceUuid") or it.get("entityId") or "-"
        status = it.get("status") or it.get("complianceType") or "-"
        detail = it.get("complianceType") or it.get("category") or ""
        print(f"{dev}  ->  {status}  {detail}")
    print()


# ======= Main =======
def main():
    parser = argparse.ArgumentParser(description="Catalyst Center API helper")
    parser.add_argument("--url", default=os.environ.get("DNAC_URL", "https://10.147.3.62"),
                        help="Catalyst Center base URL (e.g., https://10.10.10.5)")
    parser.add_argument("--user", default=os.environ.get("DNAC_USER", ""),
                        help="Username (or set DNAC_USER env var)")
    args = parser.parse_args()

    base_url = args.url.strip()
    username = args.user.strip() or input("Username: ").strip()
    password = getpass.getpass("Password: ")

    client = CatalystClient(base_url, username, password)

    print("🔐 Logging in to Catalyst Center...")
    try:
        token = client.get_token()
        print("✅ Token acquired.")
    except Exception as ex:
        eprint(f"❌ Login failed: {ex}")
        sys.exit(1)

    # Menu loop
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
            try:
                action_get_devices(client)
            except Exception as ex:
                eprint(f"Error: {ex}")
        elif choice == "2":
            try:
                action_get_templates(client)
            except Exception as ex:
                eprint(f"Error: {ex}")
        elif choice == "3":
            try:
                action_run_command(client)
            except Exception as ex:
                eprint(f"Error: {ex}")
        elif choice == "4":
            action_compliance(client)
        elif choice == "0":
            print("Goodbye.")
            break
        else:
            print("Invalid selection.")

if __name__ == "__main__":
    try:
        import requests  # noqa: F401 (verify dependency early)
    except Exception:
        eprint("The 'requests' package is required. Install with:\n  pip install requests")
        sys.exit(1)

    main()
