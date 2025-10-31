    # Step 5: Parse + Diff
suspect_ports = []
power_output = "power.txt"

    # Identify PoE ports that are "on" or "delivering power"
for line in power_output.splitlines():
        if line and ("on" in line.lower() or "deliver" in line.lower()):
            port = line.split()[0]
            # If port not in LLDP output → suspect
            if port not in lldp_output:
                suspect_ports.append(port)

    # Step 6: Save Results
if suspect_ports:
        print(f"    [!] {len(suspect_ports)} suspect ports found.")
        text_output.append(f"\n=== Switch: {hostname} ===\nSuspect Ports:\n" +
                           "\n".join(suspect_ports))
        for p in suspect_ports:
            results_summary.append({"Switch": hostname, "Port": p})
else:
        print("    [✓] No suspect ports found.")
        text_output.append(f"\n=== Switch: {hostname} ===\nNo suspect ports found.\n")

print("")