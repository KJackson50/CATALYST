import time
from typing import Optional
from .dnac_client import DNACClient

def wait_for_task(client: DNACClient, task_id: str, timeout_s: int = 300, poll_s: int = 3) -> dict:
    # Poll the task API until completion or timeout.
    end = time.time() + timeout_s
    while time.time() < end:
        data = client.get(f"/dna/intent/api/v1/task/{task_id}")
        progress = data.get("response", {})
        is_error = progress.get("isError")
        end_time = progress.get("endTime")
        if end_time or is_error:
            return progress
        time.sleep(poll_s)
    raise TimeoutError(f"Task {task_id} did not complete within {timeout_s}s")