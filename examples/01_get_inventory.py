#!/usr/bin/env python
# List all network devices and (optionally) write CSV.
import argparse, csv
from src.config import Settings
from src.dnac_client import DNACClient

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to write inventory CSV (optional)")
    args = parser.parse_args()

    s = Settings()
    client = DNACClient(
        base_url=s.dnac_url, username=s.username, password=s.password,
        verify=s.verify_ssl, timeout=s.timeout, proxies=s.proxies()
    )
    devices = client.paginate("/dna/intent/api/v1/network-device")
    print(f"Devices: {len(devices)}")
    for d in devices[:10]:
        print(d.get("hostname"), d.get("managementIpAddress"), d.get("platformId"))

    if args.csv:
        import os
        os.makedirs(os.path.dirname(args.csv), exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["hostname","mgmtIp","platformId","softwareVersion","serialNumber","id","site"])
            for d in devices:
                w.writerow([
                    d.get("hostname"),
                    d.get("managementIpAddress"),
                    d.get("platformId"),
                    d.get("softwareVersion"),
                    d.get("serialNumber"),
                    d.get("id"),
                    (d.get("locationName") or ""),
                ])
        print(f"Wrote CSV: {args.csv}")

if __name__ == "__main__":
    main()