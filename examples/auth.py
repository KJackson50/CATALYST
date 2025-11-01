import requests, getpass

DNAC = "https://10.147.3.62"
USERNAME = "admin"
PASSWORD = getpass.getpass("Enter your Catalyst password: ")

resp = requests.post(f"{DNAC}/dna/system/api/v1/auth/token",
                     auth=(USERNAME, PASSWORD),
                     verify=False)
token = resp.json()["Token"]
print("Access Token:", token)
