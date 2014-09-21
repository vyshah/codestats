#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import os
import csv
from datetime import datetime, timedelta

#version control the log files using the date in a MMDDYY format
today = datetime.now().strftime('%m%d%y') + ".csv"
yesterday = (datetime.now() - timedelta(days=1)).strftime('%m%d%y') + ".csv"

#path to projects + choose where the logs should be stored
code_path='/home/vyshah/Projects/codestats/Hilo'
log_file='/home/vyshah/Projects/codestats/errorlog'
diff_file='/home/vyshah/Projects/codestats/errordiff'
dir_ptable_file='/home/vyshah/Projects/codestats/directories_ptable'
file_ptable_file='/home/vyshah/Projects/codestats/files_ptable'

#update today's logs
with open(log_file + today, "w") as err_log:
    subprocess.call(["cppcheck", "--enable=all", 
    "--template={file},{severity},{id},{message}",
    code_path], stderr=err_log)

#alphabetically ordered "sets" of filenames, directory names, and codes to form
#axes of pivot tables
err_table = []
file_names = []
dir_names = []
err_codes = []

#turn the cppcheck output into a readable nested list
err_log = open(log_file + today, "r")
for num, line in enumerate(err_log, 0):

    #each element is a list itself
    err_table.append(line.rstrip('\n').split(","))

    #replace full path with [directory, filename]
    err_table[num]. \
            insert(0, os.path.basename(os.path.dirname(err_table[num][0])))
    err_table[num][1] = os.path.basename(err_table[num][1])

    #update axes sets
    dir_names.append(err_table[num][0])
    file_names.append(err_table[num][1])
    err_codes.append(err_table[num][3])
err_log.close()

#eliminate duplicates and sort alphabetically
file_names = sorted(list(set(file_names)))
dir_names = sorted(list(set(dir_names)))
err_codes = sorted(list(set(err_codes)))

file_ptable = \
        [[0 for i in range(len(err_codes))] for j in range (len(file_names))]
dir_ptable = \
        [[0 for i in range(len(err_codes))] for j in range (len(dir_names))]

#fill in pivot tables simultaneously by reading error log
row = 0
for err in err_table:
    dir_ptable[dir_names.index(err_table[row][0])] \
            [err_codes.index(err_table[row][3])] += 1
    file_ptable[file_names.index(err_table[row][1])] \
            [err_codes.index(err_table[row][3])] += 1
    row += 1

#substitute blank file/dir names for certain errors
if file_names[0] == '': file_names[0] = "No Particular File"
if dir_names[0] == '': dir_names[0] = "No Particular Directory"

#convert pivot tables to csv files
with open(dir_ptable_file + today, 'wb') as csvfile:
    dirwriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting = \
            csv.QUOTE_MINIMAL)
    dirwriter.writerow(["Directories/Errors"] +  err_codes)
    rownum = 0
    for row in dir_ptable:
       dirwriter.writerow([dir_names[rownum]] +  row)
       rownum += 1

with open(file_ptable_file + today, 'wb') as csvfile:
    dirwriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting = \
            csv.QUOTE_MINIMAL)
    dirwriter.writerow(["Filenames/Errors"] +  err_codes)
    rownum = 0
    for row in file_ptable:
       dirwriter.writerow([file_names[rownum]] +  row)
       rownum += 1

#TODO: add table for total error count + code sample + suggestion
