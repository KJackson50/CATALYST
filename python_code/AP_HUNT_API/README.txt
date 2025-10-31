How to run
py ap_hunt.py


Simulation
🔐 Catalyst Center Login
Enter your Catalyst password:
[+] Authentication successful.

[+] Loaded 3 switches from switches.txt

[>] Processing switch: SW-CORE-01
    [i] Found UUID: 9a89c110-7b6e-4bff-b5e1-19c72da1e02a
    [>] Task started: 6dcd7b00-19e0-11ef-a4f6-b3ac2c9c1234
    [~] Waiting for Catalyst Center to finish...
    [✓] Output ready.
    [!] 2 suspect ports found.

[>] Processing switch: SW-IDF-03
    [i] Found UUID: 1cd01ad0-7d3a-49cc-9c2b-f4568e4e6781
    [✓] No suspect ports found.

[+] Text summary written to ap_hunt_results.txt
[+] CSV summary written to ap_hunt_results.csv

✅ AP Hunt completed successfully.


=== Switch: SW-CORE-01 ===
Suspect Ports:
Gi1/0/12
Gi1/0/17

=== Switch: SW-IDF-03 ===
No suspect ports found.
