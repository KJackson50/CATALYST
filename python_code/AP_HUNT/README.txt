How to run it
python ap_hunter.py --inventory inventory.csv --out C:\temp\aphunt_out --workers 16 --timeout 30

Make sure to change the contents of the inventory.csv file for the switches you want to work on



SUSPECT T/S
show interfaces status | include Gi1/0/X
show power inline Gi1/0/X
show mac address-table interface Gi1/0/X
test cable-diagnostics tdr interface Gi1/0/X
show cable-diagnostics tdr interface Gi1/0/X
show lldp neighbors interface Gi1/0/X detail
show cdp neighbors interface Gi1/0/X detail
show ip dhcp snooping binding | include Gi1/0/X
conf t
 interface Gi1/0/X
  power inline never
  wait 10
  power inline auto
 end

RESULTS
No PoE, no link	- Unplugged / cable fault	Inspect patching
PoE on, no link	- AP dead / bad cable pair	Replace or reseat
PoE on, link up, no MAC	- AP boot-looping / wrong VLAN	Check DHCP + controller
PoE on, MAC not AP vendor	- Wrong device on port	Update documentation
PoE on, MAC + LLDP OK	- Healthy AP	No action