#!/usr/bin/env python
# List all network devices and (optionally) write CSV.

import argparse
import csv
import os
import requests
import getpass
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# === CONFIGURATION ===
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

DNAC = "https://sandboxdnac2.cisco.com"        # e.g. https://10.10.10.5
USERNAME = "devnetuser"
SWITCH_FILE = "device_ids.txt"      # one networkDeviceId per line (not used here)
OUTDIR = "baselines"                # local snapshots & diffs

# === AUTHENTICATION ===
print("🔐 Catalyst Center Login")
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

auth_resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                          auth=(USERNAME, PASSWORD), verify=False)
auth_resp.raise_for_status()
token = auth_resp.json().get("Token") or auth_resp.json().get("token")
HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}
print("[+] Authentication successful.\n")

# === INVENTORY ===
def get_all_devices():
    url = f"{DNAC}/dna/intent/api/v1/network-device"
    devices = []
    while url:
        resp = requests.get(url, headers=HEADERS, verify=False)
        resp.raise_for_status()
        data = resp.json()
        devices.extend(data.get("response", []))
        next_link = None
        for link in data.get("links", []):
            if link.get("rel") == "next":
                next_link = link.get("href")
                break
        url = next_link
    return devices


def main():
    parser = argparse.ArgumentParser(description="Inventory: list Catalyst Center network devices")
    parser.add_argument("--csv", default=None, help="Path to write inventory CSV (optional)")
    parser.add_argument("--limit", type=int, default=10, help="Print preview count (default: 10)")
    args = parser.parse_args()

    devices = get_all_devices()
    print(f"Devices: {len(devices)}")

    for d in devices[: args.limit]:
        print(d.get("hostname"), d.get("managementIpAddress"), d.get("platformId"))

    if args.csv:
        os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["hostname", "mgmtIp", "platformId", "softwareVersion", "serialNumber", "id", "site"])
            for d in devices:
                w.writerow([
                    d.get("hostname"),
                    d.get("managementIpAddress"),
                    d.get("platformId"),
                    d.get("softwareVersion"),
                    d.get("serialNumber"),
                    d.get("id"),
                    d.get("locationName") or "",
                ])
        print(f"[+] Wrote CSV: {args.csv}")


if __name__ == "__main__":
    main()
