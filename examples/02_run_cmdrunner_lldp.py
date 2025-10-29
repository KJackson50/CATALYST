#!/usr/bin/env python
# Run LLDP neighbors via Command Runner for a device.
import argparse
from src.config import Settings
from src.dnac_client import DNACClient
from src.cmdrunner import run_read_cli_commands
from src.jobs import wait_for_task

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, help="Device UUID")
    args = parser.parse_args()

    s = Settings()
    client = DNACClient(
        base_url=s.dnac_url, username=s.username, password=s.password,
        verify=s.verify_ssl, timeout=s.timeout, proxies=s.proxies()
    )

    job = run_read_cli_commands(client, [args.device], ["show lldp neighbors detail"])
    task_id = job.get("response", {}).get("taskId") or job.get("taskId")
    if not task_id:
        raise SystemExit(f"Unexpected response: {job}")

    result = wait_for_task(client, task_id, timeout_s=300)
    print("Task result:", result)

if __name__ == "__main__":
    main()