resp = requests.get(f"{DNAC}/dna/intent/api/v1/template-programmer/project",
                    headers=headers, verify=False)
projects = resp.json()["response"]

for p in projects:
    print(f"Project: {p['name']} - ID: {p['id']}")
