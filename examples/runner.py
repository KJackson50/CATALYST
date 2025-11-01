import time

# Define your command and target device UUIDs
commands = ["show version"]
device_uuids = ["device-uuid-1", "device-uuid-2"]

body = {"commands": commands, "deviceUuids": device_uuids}
resp = requests.post(f"{DNAC}/dna/intent/api/v1/network-device-poller/cli/read-request",
                     headers=headers, json=body, verify=False)

task_id = resp.json()["response"]["taskId"]
print("Task submitted:", task_id)

# Poll task result
time.sleep(5)
task_resp = requests.get(f"{DNAC}/dna/intent/api/v1/task/{task_id}",
                         headers=headers, verify=False)
print(task_resp.json())
