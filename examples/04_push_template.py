#!/usr/bin/env python
# Find a template by name and (dry-run) show how you would deploy.
import argparse, json
from src.config import Settings
from src.dnac_client import DNACClient
from src.templates_api import list_projects, list_templates_in_project, deploy_template_to_devices

def find_template_by_name(client, name: str):
    projects = list_projects(client)
    for p in projects:
        proj = list_templates_in_project(client, p.get("id"))
        for t in (proj.get("templates") or []):
            if t.get("name") == name:
                return t
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True, help="Template name")
    parser.add_argument("--device-id", required=True, help="Target device ID")
    parser.add_argument("--force", action="store_true", help="Force push even if deployed before")
    parser.add_argument("--apply", action="store_true", help="Actually deploy (default is dry-run)")
    args = parser.parse_args()

    s = Settings()
    client = DNACClient(s.dnac_url, s.username, s.password, verify=s.verify_ssl, timeout=s.timeout, proxies=s.proxies())

    t = find_template_by_name(client, args.template)
    if not t:
        raise SystemExit(f"Template not found: {args.template}")

    target = [{"id": args.device_id, "type": "MANAGED_DEVICE_IP", "params": {}}]

    if args.apply:
        resp = deploy_template_to_devices(client, t["id"], target, force_push=args.force)
        print(json.dumps(resp, indent=2))
    else:
        print("DRY RUN: would deploy templateId", t["id"], "to", target)

if __name__ == "__main__":
    main()