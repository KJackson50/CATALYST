#!/usr/bin/env python
# Claim a PnP device to a site with optional Day-0 template.
import argparse, json
from src.config import Settings
from src.dnac_client import DNACClient
from src.pnp_api import site_claim

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", required=True, help="PnP device ID")
    parser.add_argument("--site", required=True, help="Site name as in Catalyst hierarchy")
    parser.add_argument("--template", default=None, help="Template name (optional)")
    parser.add_argument("--vars", default=None, help="Path to JSON or YAML vars file (optional)")
    args = parser.parse_args()

    s = Settings()
    client = DNACClient(
        base_url=s.dnac_url, username=s.username, password=s.password,
        verify=s.verify_ssl, timeout=s.timeout, proxies=s.proxies()
    )

    template_params = {}
    if args.vars:
        if args.vars.lower().endswith((".yaml",".yml")):
            import yaml
            with open(args.vars, "r", encoding="utf-8") as f:
                template_params = yaml.safe_load(f) or {}
        else:
            with open(args.vars, "r", encoding="utf-8") as f:
                template_params = json.load(f)

    resp = site_claim(client, args.device_id, args.site, args.template, template_params)
    print(json.dumps(resp, indent=2))

if __name__ == "__main__":
    main()