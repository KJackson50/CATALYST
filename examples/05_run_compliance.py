#!/usr/bin/env python
# Fetch config compliance summary (category varies by version).
import json
from src.config import Settings
from src.dnac_client import DNACClient
from src.compliance_api import get_compliance_status

def main():
    s = Settings()
    client = DNACClient(s.dnac_url, s.username, s.password, verify=s.verify_ssl, timeout=s.timeout, proxies=s.proxies())
    data = get_compliance_status(client)
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()