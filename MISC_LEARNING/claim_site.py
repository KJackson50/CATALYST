#!/usr/bin/env python3
import argparse, json, sys, time
from typing import Dict, Any, List, Optional
import requests

requests.packages.urllib3.disable_warnings()

def _die(msg): print(f"[!] {msg}", file=sys.stderr); sys.exit(1)

class CatalystCenter:
    def __init__(self, base: str, username: str, password: str, verify_ssl: bool=False):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.verify = verify_ssl
        self.token = None
        self.username = username
        self.password = password

    def auth(self):
        r = self.s.post(f"{self.base}/dna/system/api/v1/auth/token",
                        auth=(self.username, self.password), timeout=30)
        if not r.ok:
            _die(f"Auth failed {r.status_code}: {r.text}")
        self.token = r.json().get("Token")
        if not self.token:
            _die("Auth succeeded but no token in response")
        self.s.headers.update({"X-Auth-Token": self.token})

    # ----- lookups -----
    def get_sites(self) -> List[Dict[str, Any]]:
        r = self.s.get(f"{self.base}/dna/intent/api/v1/sites", timeout=60)
        r.raise_for_status()
        return r.json()

    def find_site_id(self, name_hierarchy: str) -> str:
        """
        Match exact nameHierarchy (e.g., 'Global/Orlando/Building A/Floor 3')
        Use the exact hierarchy string you see in the GUI.
        """
        for s in self.get_sites():
            if s.get("nameHierarchy") == name_hierarchy or s.get("groupNameHierarchy") == name_hierarchy:
                return s["id"]
        _die(f"Site not found by nameHierarchy: {name_hierarchy}")

    def get_pnp_devices(self) -> List[Dict[str, Any]]:
        r = self.s.get(f"{self.base}/dna/intent/api/v1/onboarding/pnp-device", timeout=60)
        r.raise_for_status()
        return r.json()

    def find_pnp_id_by_serial(self, serial: str) -> str:
        for d in self.get_pnp_devices():
            if d.get("serialNumber") and d["serialNumber"].strip().upper() == serial.strip().upper():
                return d["id"]
        _die(f"PnP device with serial {serial} not found in PnP inventory")

    def get_templates(self) -> List[Dict[str, Any]]:
        r = self.s.get(f"{self.base}/dna/intent/api/v1/template-programmer/template", timeout=60)
        r.raise_for_status()
        return r.json()

    def find_template_id_by_name(self, name: str) -> str:
        for t in self.get_templates():
            if t.get("name") == name:
                return t["id"]
        _die(f"Template named '{name}' not found")

    def get_images(self) -> List[Dict[str, Any]]:
        r = self.s.get(f"{self.base}/dna/intent/api/v1/images", timeout=60)
        r.raise_for_status()
        return r.json()

    def find_image_id_by_name(self, name_or_version: str) -> str:
        for img in self.get_images():
            if img.get("name") == name_or_version or img.get("version") == name_or_version:
                return img["id"]
        _die(f"Image '{name_or_version}' not found")

    # ----- actions -----
    def preview_site_config(self, device_id: str, site_id: str, claim_type: str="Default") -> Dict[str, Any]:
        body = {"deviceId": device_id, "siteId": site_id, "type": claim_type}
        r = self.s.post(f"{self.base}/dna/intent/api/v1/onboarding/pnp-device/site-config-preview",
                        json=body, timeout=120)
        if not r.ok:
            _die(f"Preview failed {r.status_code}: {r.text}")
        return r.json() if r.text else {"status": r.status_code}

    def site_claim(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self.s.post(f"{self.base}/dna/intent/api/v1/onboarding/pnp-device/site-claim",
                        json=payload, timeout=120)
        if r.status_code in (200, 201, 202):
            try:
                return r.json()
            except Exception:
                return {"status": r.status_code, "text": r.text}
        _die(f"Claim failed {r.status_code}: {r.text}")

    def get_task(self, task_id: str) -> Dict[str, Any]:
        r = self.s.get(f"{self.base}/dna/intent/api/v1/task/{task_id}", timeout=60)
        r.raise_for_status()
        return r.json()

    def poll_task(self, task_id: str, timeout_s: int=600, interval: int=5) -> Dict[str, Any]:
        print(f"[i] Polling task {task_id} for up to {timeout_s}s...")
        t0 = time.time()
        last = {}
        while True:
            last = self.get_task(task_id)
            progress = last.get("response", {}).get("progress") or last.get("progress")
            is_err = last.get("isError") or last.get("response", {}).get("isError")
            if progress:
                print(f"  - {progress}")
            if is_err:
                _die(f"Task error: {json.dumps(last, indent=2)}")
            if last.get("endTime") or last.get("response", {}).get("endTime"):
                print("[i] Task completed.")
                return last
            if time.time() - t0 > timeout_s:
                _die(f"Task timeout after {timeout_s}s: {json.dumps(last, indent=2)}")
            time.sleep(interval)

def parse_kv_list(pairs: Optional[List[str]]) -> List[Dict[str, str]]:
    """
    Convert ["k=v","x=y"] -> [{"key":"k","value":"v"},{"key":"x","value":"y"}]
    """
    if not pairs: return []
    out = []
    for p in pairs:
        if "=" not in p:
            _die(f"Bad param format '{p}'. Use key=value")
        k, v = p.split("=", 1)
        out.append({"key": k, "value": v})
    return out

def main():
    ap = argparse.ArgumentParser(description="Claim a PnP device to a Site in Catalyst Center.")
    ap.add_argument("--base", required=True, help="https://<CC_FQDN_or_IP>")
    ap.add_argument("--user", required=True)
    ap.add_argument("--pass", dest="password", required=True)
    ap.add_argument("--site", required=True, help="Exact nameHierarchy (e.g., 'Global/Orlando/Building A/Floor 3')")
    ap.add_argument("--serial", required=True, help="Device serial in PnP")
    ap.add_argument("--type", default="Default",
                    choices=["Default","StackSwitch","AccessPoint","Sensor","CatalystWLC","MobilityExpress"],
                    help="Claim type (device category)")
    ap.add_argument("--hostname", help="Set device hostname during claim")
    # Template / params
    ap.add_argument("--template-name", help="Template name (to auto-resolve templateId)")
    ap.add_argument("--template-id", help="Template UUID (skip name lookup)")
    ap.add_argument("--param", action="append", help="Template param key=value (repeatable)")
    # Image
    ap.add_argument("--image-name", help="Image name or version (to auto-resolve imageId)")
    ap.add_argument("--image-id", help="Image UUID")
    ap.add_argument("--skip-image", action="store_true", help="Skip imaging step")
    # AP / WLC extras
    ap.add_argument("--rf-profile", help="AP rfProfile string (AccessPoint only)")
    ap.add_argument("--static-ip", help="Mgmt IP (WLC/EWC types)")
    ap.add_argument("--subnet-mask")
    ap.add_argument("--gateway")
    ap.add_argument("--vlan-id")
    ap.add_argument("--ip-interface-name")
    # Preview / no-claim
    ap.add_argument("--preview-only", action="store_true", help="Preview site config and exit")
    ap.add_argument("--poll", action="store_true", help="Poll task status if a taskId is returned")

    args = ap.parse_args()
    cc = CatalystCenter(args.base, args.user, args.password)
    cc.auth()

    site_id = cc.find_site_id(args.site)
    device_id = cc.find_pnp_id_by_serial(args.serial)

    if args.preview_only:
        prev = cc.preview_site_config(device_id, site_id, claim_type=args.type)
        print(json.dumps(prev, indent=2))
        return

    # Build payload
    payload = {"deviceId": device_id, "siteId": site_id, "type": args.type}
    if args.hostname:
        payload["hostname"] = args.hostname

    # Image
    image_info = {}
    if args.skip_image:
        image_info = {"skip": True}
    elif args.image_id or args.image_name:
        image_id = args.image_id or cc.find_image_id_by_name(args.image_name)
        image_info = {"imageId": image_id, "skip": False}
    if image_info:
        payload["imageInfo"] = image_info

    # Template config
    if args.template_id or args.template_name or args.param:
        cfg: Dict[str, Any] = {}
        if args.template_id or args.template_name:
            cfg["configId"] = args.template_id or cc.find_template_id_by_name(args.template_name)
        params = parse_kv_list(args.param)
        if params:
            cfg["configParameters"] = params
        if cfg:
            payload["configInfo"] = cfg

    # AP specifics
    if args.type == "AccessPoint" and args.rf_profile:
        payload["rfProfile"] = args.rf_profile

    # WLC specifics
    if args.type in ("CatalystWLC", "MobilityExpress"):
        if args.static_ip and args.subnet_mask and args.gateway:
            payload.update({
                "staticIP": args.static_ip,
                "subnetMask": args.subnet_mask,
                "gateway": args.gateway
            })
        if args.vlan_id: payload["vlanId"] = args.vlan_id
        if args.ip_interface_name: payload["ipInterfaceName"] = args.ip_interface_name

    print("[i] Claim payload:")
    print(json.dumps(payload, indent=2))

    resp = cc.site_claim(payload)
    print("[i] Claim response:")
    print(json.dumps(resp, indent=2))

    # Optional: poll task if available
    task_id = None
    # taskId can appear in different shapes; try a few:
    if isinstance(resp, dict):
        task_id = resp.get("taskId") or resp.get("response", {}).get("taskId") or resp.get("id")
    if args.poll and task_id:
        cc.poll_task(task_id)

if __name__ == "__main__":
    main()
