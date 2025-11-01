#!/usr/bin/env python3
import requests
import json
import time
import getpass
import csv
from urllib3.exceptions import InsecureRequestWarning

# === CONFIGURATION ===
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

DNAC = ""        # e.g. https://10.10.10.5
USERNAME = ""
SWITCH_FILE = "device_uuids.txt"   # one deviceUuid per line
COMMANDS = ["show version", "show ip interface brief"]
TEXT_OUT = "command_runner_results.txt"
CSV_OUT = "command_runner_results.csv"

# === AUTHENTICATION ===
print("🔐 Catalyst Center Login")
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

auth_resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                          auth=(USERNAME, PASSWORD), verify=False)
auth_resp.raise_for_status()
token = auth_resp.json().get("Token") or auth_resp.json().get("token")
HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}
print("[+] Authentication successful.\n")

# === SUBMIT COMMAND RUNNER JOB ===
with open(SWITCH_FILE, "r", encoding="utf-8") as f:
    device_uuids = [ln.strip() for ln in f if ln.strip()]

submit_url = f"{DNAC}/dna/intent/api/v1/network-device-poller/cli/read-request"
payload = {"deviceUuids": device_uuids, "commands": COMMANDS, "timeout": 60}
r = requests.post(submit_url, headers=HEADERS, json=payload, verify=False)
r.raise_for_status()
task_id = r.json().get("response", {}).get("taskId") or r.json().get("taskId")
print(f"[>] Submitted Command Runner task: {task_id}")

# === POLL TASK ===
detail_url = f"{DNAC}/dna/intent/api/v1/tasks/{task_id}/detail"
file_id = None
while True:
    tr = requests.get(detail_url, headers=HEADERS, verify=False)
    tr.raise_for_status()
    tj = tr.json() or {}
    prog = str(tj.get("progress", "")).lower()
    file_id = tj.get("fileId")
    if tj.get("isError"):
        print("[x] Task error:", json.dumps(tj, indent=2))
        break
    if "complete" in prog or "success" in prog:
        print("[✓] Task complete.")
        break
    time.sleep(2)

# === FETCH RESULT FILE ===
rows = []
if file_id:
    fr = requests.get(f"{DNAC}/dna/intent/api/v1/file/{file_id}",
                      headers=HEADERS, verify=False)
    fr.raise_for_status()
    try:
        data = fr.json()
    except Exception:
        data = {"raw": fr.text}

    # minimal flatten for typical shape
    cr = data.get("commandResponses") if isinstance(data, dict) else None
    if cr and isinstance(cr, dict):
        for dev, outs in (cr.get("SUCCESS") or {}).items():
            if isinstance(outs, dict):
                for cmd, out in outs.items():
                    rows.append({"deviceUuid": dev, "command": cmd, "output": out})
            elif isinstance(outs, list):
                for i, out in enumerate(outs, 1):
                    rows.append({"deviceUuid": dev, "index": i, "output": out})
        for dev, err in (cr.get("FAILURE") or {}).items():
            rows.append({"deviceUuid": dev, "error": str(err)})
    else:
        rows.append({"payload": json.dumps(data)})

# === WRITE OUTPUTS ===
with open(TEXT_OUT, "w", encoding="utf-8") as f:
    for rrow in rows:
        f.write(json.dumps(rrow, ensure_ascii=False) + "\n")
print(f"[+] Wrote text -> {TEXT_OUT}")

if rows:
    headers = sorted({k for rrow in rows for k in rrow.keys()})
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader(); w.writerows(rows)
    print(f"[+] Wrote CSV  -> {CSV_OUT}")
