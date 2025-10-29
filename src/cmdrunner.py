from typing import List, Dict, Any
from .dnac_client import DNACClient

def run_read_cli_commands(client: DNACClient, device_uuids: List[str], commands: List[str]) -> Dict[str, Any]:
    # Submit a Command Runner read request.
    # Endpoint: /dna/intent/api/v1/network-device-poller/cli/read-request
    body = {
        "commands": commands,
        "deviceUuids": device_uuids,
        "timeout": 30
    }
    return client.post("/dna/intent/api/v1/network-device-poller/cli/read-request", body)