#!/usr/bin/env python

import re
import csv
import argparse
import subprocess


parser = argparse.ArgumentParser(description='esxtop csv file parser')
parser.add_argument("-d", action="store", default="20", help="Samples interval")
parser.add_argument("-n", action="store", default="2500", help="Samples count")
parser.add_argument("--nic", action="store", default="none", help="vmnic name")
parser.add_argument("--vm", action="store", default="none", help="Virtual Machine host list")
parser.add_argument("--config", action="store_true", default=False, help="Generate logstash configure flag")
parser.add_argument("--path", action="store", default="none", help="Specify file path")
args_list = parser.parse_args()

delay = args_list.d
count = args_list.n
vm_list = args_list.vm.split(",")
nic_list = args_list.nic.split(",")
config_file = args_list.config
path = args_list.path

#system process is default included
#vm_list.append("system")


#"""
output = []
exampleCsv = open(path)
output = exampleCsv.readlines()
exampleCsv.close

output_items_0 = output[0].split(",")
output_items_1 = output[1].split(",")
output_items_2 = output[2].split(",")
#print output_items

print len(output_items_0)
print len(output_items_1)
print len(output_items_2)

for (index, item) in enumerate(output_items_1):
    print item
    #print output_items_1[index]
    #print output_items_2[index]
    #if item == "\"32768.00\"":
    #    print output_items_0[index]


#"""

