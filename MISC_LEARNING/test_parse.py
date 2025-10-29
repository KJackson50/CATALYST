import json
import csv

with open(r'C:\CATALYST\device_test_json.json') as json_file:
    data = json.load(json_file)

#Extract hostnames
hostnames = [device.get('hostname') for device in data.get('response',[]) if 'hostname' in device]

#save to csv
with open(r'C:\CATALYST\device_hostnames.csv', mode='w', newline='') as csv_file:
    writer = csv.writer(csv_file)
    writer.writerow(['Hostname'])
    for hostname in hostnames:
        writer.writerow([hostname])

print (f"Saved {len(hostnames)} hostnames to C:\\CATALYST\\device_hostnames.csv")


#for device in data.get('response',[]):
    #print(device.get('hostname'))


#print(data['response'][111]['hostname'])