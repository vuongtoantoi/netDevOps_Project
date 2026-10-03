#!/usr/bin/env python

from netmiko import ConnectHandler

net_connect = ConnectHandler(**vpcs)
#net_connect.find_prompt()

config_commands = ['set pc name fpt.vn',
                    'ip 111.111.111.10/24 111.111.111.1',
                    'ip dns 222.222.222.223',
                    'save'                    ]
for cmd in config_commands:
    output = net_connect.send_command(cmd)
    print(output)

output_show = net_connect.send_command('show ip')
print(output_show)

net_connect.disconnect()