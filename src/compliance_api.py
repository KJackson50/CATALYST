from typing import Dict, Any
from .dnac_client import DNACClient

def get_compliance_status(client: DNACClient, category: str = "RUNNING_CONFIG") -> Dict[str, Any]:
    # Fetch overall compliance status. Category can vary with version/capabilities.
    return client.get(f"/dna/intent/api/v1/compliance/{category}/summary")