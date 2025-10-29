from typing import Dict, Any
from .dnac_client import DNACClient

def site_claim(client: DNACClient, device_id: str, site_name: str, template_name: str = None, template_params: Dict[str, Any]=None) -> Dict[str, Any]:
    # Claim a PnP device to a site (optionally with Day-0 template).
    # Endpoint: /dna/intent/spl/v1/onboarding/pnp-device/site-claim
    payload: Dict[str, Any] = {
        "deviceId": device_id,
        "siteName": site_name,
    }
    if template_name:
        payload["templateName"] = template_name
        payload["templateParams"] = template_params or {}
    return client.post("/dna/intent/spl/v1/onboarding/pnp-device/site-claim", payload)