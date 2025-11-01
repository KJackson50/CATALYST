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

