import requests
import json
import time
import getpass
import csv
from urllib3.exceptions import InsecureRequestWarning

# === CONFIGURATION ===
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

DNAC = "https://10.147.3.62"        # Example: https://10.10.10.5
USERNAME = "206889554"
SWITCH_FILE = "switches.txt"

COMMANDS = ["show power inline", "show lldp neighbors"]
TEXT_OUT = "ap_hunt_results.txt"
CSV_OUT = "ap_hunt_results.csv"


# === AUTHENTICATION ===
print("🔐 Catalyst Center Login")
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

auth_resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                          auth=(USERNAME, PASSWORD), verify=False)
auth_resp.raise_for_status()
token = auth_resp.json()["Token"]
HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}

print("[+] Authentication successful.\n")


# === LOAD SWITCH LIST ===
with open(SWITCH_FILE, "r") as f:
    switch_names = [line.strip() for line in f if line.strip()]

print(f"[+] Loaded {len(switch_names)} switches from {SWITCH_FILE}\n")


# === RESULT STORAGE ===
results_summary = []
text_output = []


# === FUNCTION: RUN COMMANDS ON ONE SWITCH ===
def run_commands_for_switch(hostname):
    print(f"[>] Processing switch: {hostname}")

    # Step 1: Get UUID
    device_resp = requests.get(f"{DNAC}/dna/intent/api/v1/network-device?hostname={hostname}",
                               headers=HEADERS, verify=False)
    data = device_resp.json()
    if not data.get("response"):
        print(f"    [!] Switch {hostname} not found in Catalyst Center.")
        return

    device_uuid = data["response"][0]["id"]
    print(f"    [i] Found UUID: {device_uuid}")

    # Step 2: Start Command Runner Job
    payload = {"commands": COMMANDS, "deviceUuids": [device_uuid]}
    run_resp = requests.post(f"{DNAC}/dna/intent/api/v1/network-device-poller/cli/",
                             headers=HEADERS, json=payload, verify=False)
    task_id = run_resp.json()["taskId"]
    print(f"    [>] Task started: {task_id}")

    # Step 3: Poll until file is ready
    file_id = None
    while not file_id:
        task_resp = requests.get(f"{DNAC}/dna/intent/api/v1/task/{task_id}",
                                 headers=HEADERS, verify=False)
        progress = task_resp.json().get("progress", "")
        if "fileId" in progress:
            file_id = json.loads(progress)["fileId"]
            print("    [✓] Output ready.")
            break
        print("    [~] Waiting for Catalyst Center to finish...")
        time.sleep(3)

    # Step 4: Retrieve Command Output
    file_resp = requests.get(f"{DNAC}/dna/intent/api/v1/file/{file_id}",
                             headers=HEADERS, verify=False)
    command_output = file_resp.json()[0]["commandResponses"]

    power_output = command_output.get("show power inline", "")
    lldp_output = command_output.get("show lldp neighbors", "")

    # Step 5: Parse + Diff
    suspect_ports = []

    # Identify PoE ports that are "on" or "delivering power"
    for line in power_output.splitlines():
        if line and ("on" in line.lower() or "deliver" in line.lower()):
            port = line.split()[0]
            # If port not in LLDP output → suspect
            if port not in lldp_output:
                suspect_ports.append(port)

    # Step 6: Save Results
    if suspect_ports:
        print(f"    [!] {len(suspect_ports)} suspect ports found.")
        text_output.append(f"\n=== Switch: {hostname} ===\nSuspect Ports:\n" +
                           "\n".join(suspect_ports))
        for p in suspect_ports:
            results_summary.append({"Switch": hostname, "Port": p})
    else:
        print("    [✓] No suspect ports found.")
        text_output.append(f"\n=== Switch: {hostname} ===\nNo suspect ports found.\n")

    print("")


# === MAIN LOOP ===
for switch in switch_names:
    try:
        run_commands_for_switch(switch)
    except Exception as e:
        print(f"[!] Error processing {switch}: {e}\n")
        continue


# === WRITE OUTPUT FILES ===
with open(TEXT_OUT, "w") as txt:
    txt.write("\n".join(text_output))
print(f"[+] Text summary written to {TEXT_OUT}")

if results_summary:
    with open(CSV_OUT, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Switch", "Port"])
        writer.writeheader()
        writer.writerows(results_summary)
    print(f"[+] CSV summary written to {CSV_OUT}")

print("\n✅ AP Hunt completed successfully.")
