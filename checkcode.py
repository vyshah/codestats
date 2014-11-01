#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import os
import csv
import smtplib
import sys
from datetime import datetime
from optparse import OptionParser

#e-mail things
mail_server = "172.31.254.14"
mail_sender = "nsssmoke@ca.metsci.com"
mail_recipients_default = ["shahv@ca.metsci.com"]
mail_subject = "Static Code Analyzer Update"

#where log files should be output
output_path=os.path.abspath(os.getcwd())

#command line option/argument parsing
usage = "\n(case 1 - first execution): checkcode.py -r -d <directory path> " \
        "[-c] [-e] [-v] [-a address 1,address 2,...] \n\n" \
        "(case 2 - daily usage): " \
        "checkcode.py -d <directory path> [-c] [-e] [-v] " \
        "[-a address 1,address 2,...]"

parser = OptionParser(usage=usage)
parser.add_option("-r", "--reference", action="store_true", dest="reference",
        default=False, help="create a new reference (run this the first time)")
parser.add_option("-c", "--compare", action="store_true", dest="compare",
        default=False, help="include a diff comparing today's result to the \
                reference")
parser.add_option("-e", "--email", action="store_false", dest="email",
        default=True, help="don't send email alerts (on by default)")
parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
        default=False, help="print status messages to stdout while checking")
parser.add_option("-d", "--directory", action="store", type="string",
        dest="directory", default="", help="specify " \
                "code directory (must provide)")
parser.add_option("-a", "--addresses", action="store",
        default="",
        dest="mail_recipients", help="specify mailing addresses (see usage " \
                "for format - no spaces after commas)")
(options, args) = parser.parse_args()

#basic error checking
if options.directory == "":
    print("\nerror: Must provide path to code directory! (see usage)\n")
    parser.print_help()
    sys.exit(1)

if options.reference and options.compare:
    parser.error("Cannot create a new reference and compare to reference "\
            "at the same time! Try running with -r first, then with -c.")

if not options.reference and not os.path.exists(os.path.join(output_path,
"reference")):
    print("\nerror: No reference folder exists. Have you tried running the " \
            "program with the -r option first?\n")
    parser.print_help()
    sys.exit(1)

code_path = options.directory
if options.mail_recipients == "":
    mail_recipients = mail_recipients_default
else:
    mail_recipients = options.mail_recipients.split(",")

#version control the log files using the day
week = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
weekday = datetime.today().weekday()
prevday = weekday - 1
today = "ref_" if options.reference else week[weekday] + "_"
lastday = week[prevday] + "_"

#filenames
error_log="cppcheck_log.txt"
error_table="error_table.csv"
error_diff="error_diff.txt"
error_ref_diff="error_ref_diff.txt"
error_summary="error_summary.csv"

#check to see if older output files exist
noPrev = False
if not options.reference:
    while not os.path.exists(os.path.join(output_path, lastday + error_table)):
        if prevday == 0:
            prevday = 6
        else:
            prevday -= 1

        if prevday == weekday:
            print ("\nwarning: The script hasn't been run for at least a week."\
                    " Only the reference file will be used for comparison.")
            noPrev = True
            break
        else:
            lastday = week[prevday] + "_"

if options.reference:
    output_path = os.path.join(output_path, "reference")
    if not os.path.exists(output_path): os.makedirs(output_path)

#run cppcheck
output_opt = "" if options.verbose else "-q"
with open(os.path.join(output_path, today + error_log), 'w') as err_log:
    try:
        subprocess.call(["cppcheck",
            "--enable=all", output_opt,
            "--template={file}//{severity}//{id}//{message}//{line}",
        code_path], stderr=err_log)
    except:
        print("\nerror: File not found. Have you installed Cppcheck"\
                " yet? If so, the directory"\
                " provided to the program does not exist. Check the pathname"\
                " and try again.")
        sys.exit(1)

#alphabetically ordered "sets" of filenames, directory names, and codes to form
#axes of pivot tables
err_table = []
file_names = []
sample_dict = {}
issue_dict = {}
count_dict = {}

#turn the cppcheck output into a readable nested list
err_log = open(os.path.join(output_path, today + error_log), 'r')
for line in err_log:

    #each element is a list itself
    #"toomanyconfigs" error means cppcheck does not support more than 12
    #ifndefs, nothing left to do
    err_table_entry = line.rstrip('\n').split('//')
    if os.path.splitext(err_table_entry[0])[1] not in {".cpp", ".h", "", \
            ".C", ".c"} or err_table_entry[2] == "toomanyconfigs":
        continue

    if err_table_entry[0] == '':
        sample_dict[err_table_entry[2]] = "N/A"
        issue_dict[err_table_entry[2]] = err_table_entry[3]

    #save a line number and message for each error to get code sample later
    if err_table_entry[2] not in sample_dict.keys() and err_table_entry[0] !='':
        with open(err_table_entry[0], 'r') as code:
            for linenum, codeline in enumerate(code, 1):
                if linenum == int(err_table_entry[4]):
                    sample_dict[err_table_entry[2]] = codeline
        issue_dict[err_table_entry[2]] = "\"" + err_table_entry[3] + "\""

    #for each error type, count each instance
    if err_table_entry[2] not in count_dict.keys():
        count_dict[err_table_entry[2]] = 1
    else:
        count_dict[err_table_entry[2]] += 1

    #replace full path with [directory, filename]
    err_table_entry[0] = os.path.basename(err_table_entry[0])

    #update axes sets
    file_names.append(err_table_entry[0])

    #add entry to table
    err_table.append(err_table_entry)
err_log.close()

#each line of code contains ";\n" at the end. This is removed
#so the file can use ; as a delimiter
for example in sample_dict.keys():
    sample_dict[example] = sample_dict[example].strip(";\n")

#eliminate duplicates and sort alphabetically, err_codes is
#a sorted list of all error names
file_names = sorted(list(set(file_names)))
err_codes = sorted(sample_dict.keys())

#initialize ptables
file_ptable = \
        [[0 for i in range(len(err_codes))] for j in range (len(file_names))]

#fill in pivot tables simultaneously by reading error log
for err in err_table:
    file_ptable[file_names.index(err[0])] \
            [err_codes.index(err[2])] += 1

#substitute blank file/dir names for certain errors
if file_names[0] == '': file_names[0] = "No Particular File"

#produce flat table csv files from pivot tables
with open(os.path.join(output_path, today + error_table), 'wb') as csvfile:
    filewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting = \
            csv.QUOTE_MINIMAL)
    filewriter.writerow(["File", "Error", "Instances"])
    for filename in file_ptable:
        for err_count in filename:
            if err_count != 0:
                filewriter.writerow([file_names[file_ptable.index(filename)], \
                        err_codes[filename.index(err_count)], err_count])

#skip diff when making new reference
noDiff = False
if not options.reference and not noPrev:
    with open(os.path.join(output_path, today + error_diff), 'w') as diff:
        try:
            subprocess.call(["fc", \
                    os.path.join(output_path, lastday + error_table), \
                    os.path.join(output_path, today + error_table)], \
                    stdout=diff)
        except:
            try:
                subprocess.call(["diff", \
                        os.path.join(output_path, lastday + error_table), \
                        os.path.join(output_path, today + error_table)], \
                        stdout=diff)
            except:
                print ("\nwarning: No diff tool found! "\
                        "Diff output will be empty.")
                print "ref case"
                noDiff = True

#remove last week's reference diff
if os.path.exists(os.path.join(output_path, today + error_ref_diff)):
    os.remove(os.path.join(output_path, today + error_ref_diff))

#reference diff
if options.compare or noPrev:
    with open(os.path.join(output_path,today + error_ref_diff),'w') as ref_diff:
        try:
            subprocess.call(["fc", \
                    os.path.join(output_path,"reference","ref_" + error_table),\
                    os.path.join(output_path,today + error_table)], \
                    stdout=ref_diff)
        except:
            try:
                subprocess.call(["diff", \
                        os.path.join(output_path,\
                        "reference","ref_" + error_table), \
                        os.path.join(output_path,today + error_table)], \
                        stdout=ref_diff)
            except:
                print ("\nwarning: No diff tool found! " \
                        "Diff output will be empty.")

#make csv file with summary of all present errors
if options.reference:
    with open(os.path.join(output_path, today + error_summary), 'w') as csvfile:
        errwriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting =\
                csv.QUOTE_MINIMAL)
        errwriter.writerow(["Error", "Total Count", "Example", "Issue"])
        for err_name in err_codes:
            errwriter.writerow([err_name, count_dict[err_name],
                sample_dict[err_name], issue_dict[err_name]])

    #no need to continue further if this is a reference case
    sys.exit(0)

if options.email:
    if noDiff:
        msg = "Neither fc nor diff are installed on the smoke machine."
    elif noPrev:
        msg = "Warning: The script hasn't run for at least a week."
    elif os.path.getsize(os.path.join(output_path,today + error_diff)) == 0:
        msg = "There seem to be no changes in the number of errors since "+\
                "yesterday."
    else:
        with open(os.path.join(output_path, today + error_diff), 'r') as diff:
            msg = "The number of bugs in the codebase has changed since " + \
                    "yesterday. Here is the diff output:" + '\n\n' + diff.read()

    header = ("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n"
        % (mail_sender, ', '.join(mail_recipients), mail_subject))
    msg = header + msg
    table_file = file(os.path.join(output_path, today + error_table))
    server = smtplib.SMTP(mail_server)
    server.sendmail(mail_sender, mail_recipients, msg)
    server.quit()

