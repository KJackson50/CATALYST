#!/usr/bin/env python3
import requests
import json
import time
import getpass
import csv
from urllib3.exceptions import InsecureRequestWarning
import os, difflib

# === CONFIGURATION ===
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

DNAC = "https://10.147.3.62"        # e.g. https://10.10.10.5
USERNAME = "206889554"
SWITCH_FILE = "device_ids.txt"    # one networkDeviceId per line
OUTDIR = "baselines"              # local snapshots & diffs

# === AUTHENTICATION ===
print("🔐 Catalyst Center Login")
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

auth_resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                          auth=(USERNAME, PASSWORD), verify=False)
auth_resp.raise_for_status()
token = auth_resp.json().get("Token") or auth_resp.json().get("token")
HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}
print("[+] Authentication successful.\n")

# === SNAPSHOT & DIFF ===
os.makedirs(OUTDIR, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")

with open(SWITCH_FILE, "r", encoding="utf-8") as f:
    device_ids = [ln.strip() for ln in f if ln.strip()]

for dev in device_ids:
    dev_dir = os.path.join(OUTDIR, dev)
    os.makedirs(dev_dir, exist_ok=True)

    # Pull current running config (per-device endpoint)
    url = f"{DNAC}/dna/intent/api/v1/network-device/{dev}/config"
    r = requests.get(url, headers=HEADERS, verify=False)
    r.raise_for_status()
    obj = r.json() if r.headers.get("Content-Type","").startswith("application/json") else None

    if isinstance(obj, dict) and "response" in obj:
        resp = obj["response"]
        if isinstance(resp, str):
            cfg = resp
        elif isinstance(resp, list) and resp and isinstance(resp[0], dict):
            cfg = resp[0].get("runningConfig") or resp[0].get("config") or ""
        else:
            cfg = json.dumps(obj)
    else:
        cfg = r.text

    cur_path = os.path.join(dev_dir, f"{stamp}.cfg")
    with open(cur_path, "w", encoding="utf-8") as f:
        f.write(cfg)

    # Diff against previous snapshot (if any)
    snaps = sorted([p for p in os.listdir(dev_dir) if p.endswith(".cfg")])
    status = "BASELINED"
    if len(snaps) >= 2:
        prev_path = os.path.join(dev_dir, snaps[-2])
        with open(prev_path, "r", encoding="utf-8") as f:
            old = f.read()
        diff_txt = "".join(difflib.unified_diff(
            old.splitlines(keepends=True),
            cfg.splitlines(keepends=True),
            fromfile="previous", tofile="current"
        ))
        with open(os.path.join(dev_dir, f"{stamp}.diff"), "w", encoding="utf-8") as f:
            f.write(diff_txt)
        status = "DRIFT" if diff_txt.strip() else "NO_CHANGE"

    print(json.dumps({"deviceId": dev, "snapshot": cur_path, "status": status}, indent=2))
