from pathlib import Path
import json
import sys

# /C:/Users/206889554/OneDrive - uniparks/Projects/CAT CENTER/CATALYST/api/testing/info.py
"""
Read devices.json and extract device name and management IP from the top-level 'response' key.
"""


# candidate keys to look for (common variations)
NAME_KEYS = ("deviceName", "device_name", "name", "hostname", "device", "Device Name")
MGMT_KEYS = ("managementip", "management_ip", "managementIp", "mgmtIp", "mgmt_ip", "managementaddress", "ip")


def _pick_value(obj: dict, candidates):
    for k in candidates:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    # try case-insensitive match
    lower_map = {kk.lower(): vv for kk, vv in obj.items()}
    for k in candidates:
        if k.lower() in lower_map and lower_map[k.lower()] not in (None, ""):
            return lower_map[k.lower()]
    return None


def get_devices_info(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    data = json.loads(path.read_text(encoding="utf-8"))

    # If the JSON wraps results under 'response', use it; otherwise use top-level list/dict
    records = None
    if isinstance(data, dict) and "response" in data:
        records = data["response"]
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # maybe the dict itself represents a single device
        records = [data]
    else:
        raise ValueError("Unexpected JSON structure in devices file")

    results = []
    for entry in records:
        if not isinstance(entry, dict):
            continue
        name = _pick_value(entry, NAME_KEYS) or ""
        mgmt = _pick_value(entry, MGMT_KEYS) or ""
        results.append({"device_name": name, "management_ip": mgmt})
    return results


if __name__ == "__main__":
    # usage: python info.py [path/to/devices.json]
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "devices.json"
    try:
        devices = get_devices_info(path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(devices, indent=2))