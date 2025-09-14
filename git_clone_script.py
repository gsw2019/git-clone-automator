"""
File:           git_clone_script.py
Author:         Garret Wilson
Description:    Automates the process of cloning student Git repos to your machine.

                Assumes the .csv has a header row detailing column names.

                Each user needs to set their user-specific globals.

                Must provide at least assignment type and assignment number on command
                line. Can optionally add deadline date. Strict order.
                Example:    python3 git_clone_script.py  project 1 09/08/2025

                Checkout the commit prior to deadline

                Renames student projects to their repo name so can import into Eclipse
                simultaneously
"""

import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


# ----------------------------------
# set assignment-specific globals
# ----------------------------------

ASGN_TYPE = ""
ASGN_NUMBER = ""

# TODO: get assignment deadline fom command line arguments. Make it optional
ASGN_DEADLINE = ""

# check if exactly 3 arguments were entered correctly
if len(sys.argv) == 3:
    if not sys.argv[1].isalpha() or not sys.argv[2].isnumeric():
        print("Usage: python3 git_clone_script.py <ASGN_TYPE> <ASGN_NUMBER>")
        exit(1)
    ASGN_TYPE = sys.argv[1]
    ASGN_NUMBER = sys.argv[2]
elif len(sys.argv) <= 2 or len(sys.argv) > 3:
    print("Usage: python3 git_clone_script.py <ASGN_TYPE> <ASGN_NUMBER>")
    exit(1)

# common pieces of URL for all students
BASE_URL = f"https://github.com/CSc-335-Fall-2025/{ASGN_TYPE + "-" + ASGN_NUMBER}-[USERNAME].git"


# ------------------------
# user-specific globals
# ------------------------

# path to destination for storing repos
TARGET_DIR = "student_repos"

# path of .csv file that contains student GitHub usernames
# expected format: student, username
USERNAMES = "student_github_usernames.csv"


# ---------------------------
# get usernames fromm .csv
# ---------------------------

names_usernames_file = open(USERNAMES, "r")
names_usernames = []

# skips .csv header line
for line in names_usernames_file.readlines()[1:]:
    line_elements = line.strip().split(",")

    # if no username is recorded, skip it
    if len(line_elements) < 2 or line_elements[1] == "":
        continue

    name, username = line_elements[0].strip(), line_elements[1].strip()
    names_usernames.append((name, username))


# ------------------------------------------------------------------------------------
# clone student repos state prior to deadline to target directory and rename projects
# ------------------------------------------------------------------------------------

total_clones = 0

for name, username in names_usernames:
    print("")
    result_url = BASE_URL.replace("[USERNAME]", username)
    repo_name = ASGN_TYPE + "-" + ASGN_NUMBER + "-" + username

    # -C option specifies directory to mimic operating in
    status = os.system(f"git -C {TARGET_DIR} clone {result_url}")

    # use os.WEXITSTATUS() because gives bash exit code
    # clone was successful
    if os.WEXITSTATUS(status) == 0:

        # get the last commit prior to deadline


        project_file = Path(f"{TARGET_DIR}/{repo_name}/.project")
        if project_file.exists():
            # use XML parsing and editing tool
            tree = ET.parse(project_file)
            root = tree.getroot()

            # change <name> tag
            name_tag = root.find("name")
            name_tag.text = repo_name
            tree.write(project_file, encoding="UTF-8", xml_declaration=True)
            print(f"successfully renamed project to {repo_name}")

        total_clones += 1
    else:
        print(f"student name: {name}")

print(f"\n\n{total_clones} student repos were cloned into {TARGET_DIR}")
