#!/usr/bin/env python

from netmiko import ConnectHandler

net_connect = ConnectHandler(**vpcs)
#net_connect.find_prompt()

config_commands = ["set pc name <the server's Name>",
                    'ip dhcp',
                    'save'                    ]
for cmd in config_commands:
    output = net_connect.send_command(cmd)
    print(output)

output_show = net_connect.send_command('show ip')
print(output_show)

net_connect.disconnect()