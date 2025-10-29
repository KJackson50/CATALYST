from typing import Dict, Any, List
from .dnac_client import DNACClient

def list_projects(client: DNACClient) -> List[Dict,]:
    return client.paginate("/dna/intent/api/v1/template-programmer/project")

def list_templates_in_project(client: DNACClient, project_id: str) -> Dict[str, Any]:
    return client.get(f"/dna/intent/api/v1/template-programmer/project/{project_id}")

def deploy_template_to_devices(client: DNACClient, template_id: str, targets: List[Dict[str, Any]], force_push: bool = False) -> Dict[str, Any]:
    # Deploy a template by templateId to a list of target devices.
    # targets example: [{"id": "<deviceId>", "type": "MANAGED_DEVICE_IP", "params": {...}}]
    body = {
        "templateId": template_id,
        "forcePushTemplate": force_push,
        "targetInfo": targets,
    }
    return client.post("/dna/intent/api/v1/template-programmer/template/deploy", body)