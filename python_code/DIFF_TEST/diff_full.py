# Step 5: Parse + Diff
suspect_ports = []

# Read file contents
with open("power.txt") as p_file:
    power_output = p_file.read()

with open("lldp.txt") as l_file:
    lldp_output = l_file.read()

# Identify PoE ports that are "on" or "delivering power"
for line in power_output.splitlines():
    if line and ("on" in line.lower() or "deliver" in line.lower()):
        port = line.split()[0]
        # If port not found in LLDP output → suspect
        if port not in lldp_output:
            suspect_ports.append(port)

print("Suspect Ports:", suspect_ports)
