import requests, json, time, getpass
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ======= EDIT THESE =======
DNAC = "https://10.147.3.62"     # e.g. https://10.10.10.5
USERNAME = "206889554"
HOSTNAME = "UE-B1085-FUELTANK3.use.ucdp.net"  # exact Inventory hostname
# ==========================

def jprint(title, obj):
    print(f"\n=== {title} ===")
    try:
        print(json.dumps(obj, indent=2))
    except Exception:
        print(obj)

def main():
    # 1) AUTH
    pwd = getpass.getpass("Catalyst password: ")
    r = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                      auth=(USERNAME, pwd), verify=False)
    if not r.ok:
        print(f"[!] Auth failed {r.status_code}: {r.text}")
        return
    tok = r.json().get("Token")
    if not tok:
        print(f"[!] No token in response: {r.text}")
        return
    H = {"X-Auth-Token": tok, "Content-Type": "application/json"}
    print("[+] Auth OK")

    # 2) DEVICE LOOKUP
    r = requests.get(f"{DNAC}/dna/intent/api/v1/network-device",
                     params={"hostname": HOSTNAME}, headers=H, verify=False)
    if not r.ok:
        print(f"[!] Device lookup failed {r.status_code}: {r.text}")
        return
    dev = r.json()
    jprint("DEVICE LOOKUP RAW", dev)
    items = dev.get("response") or []
    if not items:
        print("[!] No device found for that hostname")
        return
    device_uuid = items[0].get("id")
    if not device_uuid:
        print("[!] No device UUID in lookup response")
        return
    print(f"[+] UUID: {device_uuid}")

    # 3) RUN COMMAND RUNNER
    payload = {
        "commands": ["show power inline", "show lldp neighbors"],
        "deviceUuids": [device_uuid]
    }
    r = requests.post(f"{DNAC}/dna/intent/api/v1/network-device-poller/cli/",
                      headers=H, json=payload, verify=False)
    if not r.ok:
        print(f"[!] Run failed {r.status_code}: {r.text}")
        return
    run_json = r.json()
    jprint("RUN RAW", run_json)

    # ---- BASIC, ROBUST taskId extraction (all common shapes) ----
    task_id = (
        run_json.get("taskId")
        or (run_json.get("response") or {}).get("taskId")
        or (run_json.get("response") or {}).get("task", {}).get("id")
        or run_json.get("id")  # rare
    )
    if not task_id:
        print("[!] Could not find taskId in RUN RAW above. That’s the issue.")
        return
    print(f"[+] taskId: {task_id}")

    # 4) POLL TASK (print the whole thing so we see 'progress' and 'fileId')
    for _ in range(20):
        t = requests.get(f"{DNAC}/dna/intent/api/v1/task/{task_id}",
                         headers=H, verify=False)
        if not t.ok:
            print(f"[!] Task poll failed {t.status_code}: {t.text}")
            time.sleep(2)
            continue
        task_json = t.json()
        jprint("TASK RAW", task_json)

        # surface errors immediately
        if task_json.get("isError"):
            print(f"[!] Task error: {task_json.get('failureReason') or task_json}")
            return

        progress = task_json.get("progress")
        file_id = None
        # progress is usually a JSON string with {"fileId":"..."}
        if isinstance(progress, str) and progress.startswith("{"):
            try:
                file_id = json.loads(progress).get("fileId")
            except Exception:
                pass
        elif isinstance(progress, dict):
            file_id = progress.get("fileId")

        if file_id:
            print(f"[+] fileId: {file_id}  (we’re good — next step is GET /file/{file_id})")
            return

        print("[~] Waiting for fileId...")
        time.sleep(2)

    print("[!] Timed out waiting for fileId (see TASK RAW prints above).")

if __name__ == "__main__":
    main()
