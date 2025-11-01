resp = requests.get(f"{DNAC}/dna/intent/api/v1/compliance",
                    headers=headers, verify=False)
compliance = resp.json()["response"]

for item in compliance:
    print(f"{item['deviceUuid']} - {item['status']}")
