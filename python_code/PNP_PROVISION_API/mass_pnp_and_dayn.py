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

PNP_PAYLOAD = "pnp_payload.json"  # {"devices":[...], "claims":[...]}
TEMPLATE_ID = ""                  # DayN templateId (string)
TARGETS_FILE = "targets.json"     # [{"id":"<networkDeviceId>","type":"MANAGED_DEVICE_IP","params":{...}}]

# === AUTHENTICATION ===
print("🔐 Catalyst Center Login")
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

auth_resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                          auth=(USERNAME, PASSWORD), verify=False)
auth_resp.raise_for_status()
token = auth_resp.json().get("Token") or auth_resp.json().get("token")
HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}
print("[+] Authentication successful.\n")

# === OPTIONAL: PnP IMPORT ===
try:
    with open(PNP_PAYLOAD, "r", encoding="utf-8") as f:
        pnp = json.load(f)
except FileNotFoundError:
    pnp = {"devices": [], "claims": []}

if pnp.get("devices"):
    url = f"{DNAC}/dna/intent/api/v1/onboarding/pnp-device/import"
    r = requests.post(url, headers=HEADERS,
                      json={"deviceInfoList": pnp["devices"]}, verify=False)
    r.raise_for_status()
    task_id = r.json().get("response", {}).get("taskId") or r.json().get("taskId")
    print(f"[>] PnP Import task: {task_id}")
    # Poll
    while True:
        tr = requests.get(f"{DNAC}/dna/intent/api/v1/tasks/{task_id}/detail",
                          headers=HEADERS, verify=False)
        tr.raise_for_status()
        tj = tr.json() or {}
        if tj.get("isError"): print("[x] PnP import error:", tj); break
        if "complete" in str(tj.get("progress", "")).lower(): print("[✓] PnP import done."); break
        time.sleep(2)

# === OPTIONAL: PnP CLAIM ===
if pnp.get("claims"):
    url = f"{DNAC}/dna/intent/api/v1/onboarding/pnp-device/site-claim"
    # siteName or siteId can be used inside each claim object depending on cluster version
    r = requests.post(url, headers=HEADERS, json={"siteId": None, "device": pnp["claims"]},
                      verify=False)
    r.raise_for_status()
    task_id = r.json().get("response", {}).get("taskId") or r.json().get("taskId")
    print(f"[>] PnP Claim task: {task_id}")
    # Poll
    while True:
        tr = requests.get(f"{DNAC}/dna/intent/api/v1/tasks/{task_id}/detail",
                          headers=HEADERS, verify=False)
        tr.raise_for_status()
        tj = tr.json() or {}
        if tj.get("isError"): print("[x] PnP claim error:", tj); break
        if "complete" in str(tj.get("progress", "")).lower(): print("[✓] PnP claim done."); break
        time.sleep(2)

# === OPTIONAL: DayN TEMPLATE DEPLOY ===
try:
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        targets = json.load(f)
except FileNotFoundError:
    targets = []

if TEMPLATE_ID and targets:
    url = f"{DNAC}/dna/intent/api/v1/template-programmer/template/deploy"
    body = {
        "templateId": TEMPLATE_ID,
        "forcePushTemplate": True,
        "isComposite": False,
        "targetInfo": [
            {"id": t.get("id"),
             "type": t.get("type", "MANAGED_DEVICE_IP"),
             "params": t.get("params", {})}
            for t in targets
        ],
    }
    r = requests.post(url, headers=HEADERS, json=body, verify=False)
    r.raise_for_status()
    dep_id = r.json().get("deploymentId")
    task_id = r.json().get("response", {}).get("taskId") or r.json().get("taskId")

    if task_id:
        print(f"[>] DayN Deploy task: {task_id}")
        while True:
            tr = requests.get(f"{DNAC}/dna/intent/api/v1/tasks/{task_id}/detail",
                              headers=HEADERS, verify=False)
            tr.raise_for_status()
            tj = tr.json() or {}
            if tj.get("isError"): print("[x] DayN deploy error:", tj); break
            if "complete" in str(tj.get("progress", "")).lower(): print("[✓] DayN deploy done."); break
            time.sleep(2)
    elif dep_id:
        print(f"[i] DayN deploymentId: {dep_id} (add deploy/status polling if needed)")
    else:
        print("[i] DayN deploy response:", r.json())
