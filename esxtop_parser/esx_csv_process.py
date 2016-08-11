#!/usr/bin/env python

import re
import os
import argparse
import subprocess


parser = argparse.ArgumentParser(description='esxtop csv file parser')
parser.add_argument("-d", action="store", default="20", help="Samples interval")
parser.add_argument("-n", action="store", default="2500", type=int, help="Samples count")
parser.add_argument("-c", action="store", default="none", help="Specify esxtop configure file")
parser.add_argument("--nic", action="store", default="none", help="vmnic name")
parser.add_argument("--vm", action="store", default="none", help="Virtual Machine host list")
parser.add_argument("--entity", action="store", default="none", help="Specify entity file")
parser.add_argument("--logstash", action="store", default="none", help="Generate logstash configure flag")
parser.add_argument("--path", action="store", default="\\tmp\\", help="csv file path")
args_list = parser.parse_args()

delay = args_list.d
count = args_list.n
vm_list = args_list.vm.split(",")
nic_list = args_list.nic.split(",")
logstash_config = args_list.logstash
esxtop_config = args_list.c
entity_config = args_list.entity
config_path = args_list.path

OLD_ENTITY_FILE = "rackhd_esxtop.entity.origin"
ENTITY_FILE = "rackhd_esxtop.entity" if (entity_config == "none") else entity_config
LOGSTASH_CONFIG_FILE = "rackhd_esxtop.logstash" if (logstash_config == "none") else logstash_config
ESXTOP_CONFIG_FILE = "rackhd_esxtop60rc" if (esxtop_config == "none") else esxtop_config
###########################################################################
##This portion is to edit esxtop entity to reduce esxtop output size
###########################################################################
if entity_config == "none":
    cmd_entity = "esxtop --export-entity " + OLD_ENTITY_FILE
    subprocess.call(cmd_entity, shell=True)
    f_old_entity = open(OLD_ENTITY_FILE, "r")
    f_new_entity = open(ENTITY_FILE, "w")
    ## flag = 1,2,3,4,5 stands for SchedGroup, Adapter, Device, NetPort, InterruptCookie sections respectively
    flag = 0
    ## Process "helper", "drivers", "ft" and "vmotion" will be dropped, "system" and "idle" is kept
    process_anti_patten = re.compile("\d+ ([A-Za-z\-\_]+\.\d+|helper|drivers|ft|vmotion)", re.I)
    network_anti_patten = re.compile("\d+ (Management|Shadow .+|vmk\d+)", re.I)
    for line in f_old_entity.readlines():
        stripped_line = line.replace("\n", "")
        if stripped_line in ["SchedGroup", "Adapter", "Device", "NetPort", "InterruptCookie"]:
            flag += 1
            if flag == 1 or flag == 4:
                f_new_entity.write(line)
        elif flag == 1 and not process_anti_patten.match(stripped_line):
            f_new_entity.write(line)
        elif flag == 4 and not network_anti_patten.match(stripped_line):
            f_new_entity.write(line)
    f_old_entity.close()
    f_new_entity.close()
    os.remove(OLD_ENTITY_FILE)


###########################################################################
##This portion is to filter necessary headings of ESXi performance
###########################################################################
cmd_test = "esxtop --import-entity {} -b -n {} -d {} -c {}".format(ENTITY_FILE, 1, 2, ESXTOP_CONFIG_FILE)
output = subprocess.check_output(cmd_test, shell=True)
output = output.split("\n")[0]

old_heading_list = output.split(",")

patten_list = [
    re.compile(".*PDH-CSV.*UTC.*", re.I),
    #re.compile(".*Memory\\\\Memory Overcommit \(1 Minute Avg\)", re.I),
    re.compile(".*Memory\\\\(Machine|Kernel|NonKernel|Free) MBytes", re.I),
    re.compile(".*Physical Cpu Load\\\\Cpu Load \(1 Minute Avg\)", re.I),
    re.compile(".*Physical Cpu\(_Total\)\\\\\% (Processor|Util|Core Util) Time", re.I),
]

#if --vm is used, only specified vms will be monitored
if vm_list[0] != "none":
    for vm in vm_list:
        #cpu_string = ".*Group Cpu\(\d+\:{}\)\\\\\% (Used|Run|System|Wait|Ready|Idle)".format(vm)
        cpu_string = ".*Group Cpu\(\d+\:{}\)\\\\\% (Used|Run|System)".format(vm)
        mem_string = ".*Group Memory\(\d+\:{}\)\\\\(Memory|Memory Granted|Memory Consumed|Target) Size MBytes".format(vm)
        patten_list.append(re.compile(cpu_string, re.I))
        patten_list.append(re.compile(mem_string, re.I))
        if nic_list[0] == "none":
            #if -n is not used, nics for all vms will be monitored
            net_string = ".*Network Port\(vSwitch\d+.+\:{}\)\\\\(MBits|Packets) (Transmitted|Received)\/sec".format(vm)
            patten_list.append(re.compile(net_string, re.I))
#if --vm is not used, all vms will be monitored
else:
    cpu_string = ".*Group Cpu\(\d+\:[\w_-]+\)\\\\\% (Used|Run|System)"
    mem_string = ".*Group Memory\(\d+\:[\w_-]+\)\\\\(Memory|Memory Granted|Memory Consumed|Target) Size MBytes"
    patten_list.append(re.compile(cpu_string, re.I))
    patten_list.append(re.compile(mem_string, re.I))
    if nic_list[0] == "none":
        #if -n is not used, all vmnics will be monitored
        net_string = ".*Network Port\(vSwitch\d\:\d+\:vmnic\d{1,2}\)\\\\(MBits|Packets) (Transmitted|Received)\/sec"
        patten_list.append(re.compile(net_string, re.I))

#if --nic is used, only specified nics will be monitored
if nic_list[0] != "none":
    for nic in nic_list:
        net_string = ".*Network Port\(vSwitch\d\:\d+\:{}\)\\\\(MBits|Packets) (Transmitted|Received)\/sec".format(nic)
        patten_list.append(re.compile(net_string, re.I))

target_index_list = []
new_heading_list = []
string_convert_list = []
for (key, data) in enumerate(old_heading_list):
    #print data
    for patten in patten_list:
        if patten.match(data):
            #print data
            target_index_list.append(key+1)
            convert_data = data.replace("\\\\localhost\\", "").replace("\\", "_").replace(" ", "-")
            string_convert_list.append(convert_data + " => \"float\"")
            new_heading_list.append(convert_data.replace("\"", ""))

###########################################################################
## This portion is to create awk script
## to filter necessary data according headings
###########################################################################
awk_str = ""
iterate = len(target_index_list)
for i in range(iterate-1):
    awk_str = awk_str + " $" + str(target_index_list[i]) + "\",\""
awk_str = '{\'print' + awk_str + " $" + str(target_index_list[iterate-1]) + '\'}'
cmd_esxtop = "esxtop --import-entity {} -b -n {} -d {} -c {}" \
             "| grep -v localhost | awk -F \",\" {} > esxtop.csv"\
    .format(ENTITY_FILE, str(count), delay, ESXTOP_CONFIG_FILE, awk_str)


###########################################################################
##This portion is to generate logstash configure file
###########################################################################
f = open(LOGSTASH_CONFIG_FILE, "w")
new_heading_list[0] = "_timestamp"
del string_convert_list[0]
converting_list = "\n            ".join(string_convert_list)
headings = str(new_heading_list)
logstash_string = \
    'input {\n' \
    '    file {\n' \
    '        path => ["./esxtop.csv"]\n' \
    '        start_position => "beginning"\n' \
    '        ignore_older => 0\n' \
    '        sincedb_path => "/dev/null"\n' \
    '    }\n' \
    '}\n' \
    '\n' \
    'filter {\n' \
    '    csv {\n' \
    '        columns => ' + headings + '\n' \
    '        separator => ","\n' \
    '        convert => {\n            ' + converting_list + '}\n' \
    '    }\n' \
    '    date {\n' \
    '        locale => "en"\n' \
    '        timezone => "Asia/Hong_Kong"\n' \
    '        match => [ "_timestamp", "MM/dd/yyyy HH:mm:ss" ]\n' \
    '        target => ["timestamp"]\n' \
    '        remove_field => ["_timestamp"]\n' \
    '    }\n' \
    '}\n' \
    '\n' \
    'output{\n' \
    '    elasticsearch\n' \
    '    {\n' \
    '       hosts => ["localhost:9200"]\n' \
    '       codec => "json"\n' \
    '       index => "esxtop"\n' \
    '    }\n' \
    '}'
f.write(logstash_string)
f.close()


i = 0
while i < 10:
    subprocess.call(cmd_esxtop, shell=True)
    print cmd_esxtop
    f = open("esxtop.csv", "rU")
    line_count = 0
    for line in f:
        line_count += 1
    print line_count
    if line_count < count:
        old_count = count
        count = count - line_count
        cmd_esxtop = cmd_esxtop.replace("-n " + str(old_count), "-n " + str(count)).replace(">", ">>")
        i += 1
    else:
        break


#os.remove(ENTITY_FILE)
