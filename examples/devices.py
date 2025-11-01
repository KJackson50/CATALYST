headers = {"X-Auth-Token": token}
resp = requests.get(f"{DNAC}/dna/intent/api/v1/network-device",
                    headers=headers, verify=False)
devices = resp.json()["response"]

for dev in devices:
    print(f"{dev['hostname']} ({dev['managementIpAddress']}) - {dev['series']}")
