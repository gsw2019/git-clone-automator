"""
File:           git_clone_script.py
Author:         Garret Wilson
Description:    Automates the process of cloning student Git repos to your machine.

                Assumes the .csv has a header row detailing column names.

                Each user needs to set their user-specific globals.

                Each user needs to set their semester-specific date ranges.

                Must provide at least assignment type and assignment number on command line.
                Can optionally add deadline date and time in ISO 8601 format (YYYY-MM-DD or YYYY-MM-DD:HH).
                Strict order.
                If hour is not provided, defaults to 00:00:00
                Example:    python3 git_clone_script.py  project 1              ->  most recent commit
                Example:    python3 git_clone_script.py  project 1 2025-09-09   ->  last commit prior to Sept 9th, 2025 12:00 AM
                Example:    python3 git_clone_script.py  lab 2 2025-09-20:19    ->  last commit prior to Sept 20th, 2025 7:00 PM

                Renames student projects to their repo name so can import into Eclipse simultaneously.
"""


import sys
import subprocess as sp
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


def is_valid_date():
    """Ensures the deadline date provided by the user is in ISO 8601 format and the
    date is within the semester range

    :return: boolean
    """
    date_elements = sys.argv[3].split("-")

    # ensure year and month are within semester range
    if int(date_elements[0]) != SEM_YEAR:
        print(f"Year is not of current semester ({SEM_YEAR})")
        return False
    if int(date_elements[1]) < SEM_MONTH_START or int(date_elements[1]) > SEM_MONTH_END:
        print(f"Month out of range ({SEM_MONTH_START} to {SEM_MONTH_END})")
        return False

    try:
        datetime.strptime(sys.argv[3], "%Y-%m-%d")
        return True
    except ValueError:
        try:
            datetime.strptime(sys.argv[3], "%Y-%m-%d:%H")
            return True
        except ValueError:
            print("invalid ISO 8601 date for [ASGN_DEADLINE]. Format: YYYY-MM-DD or YYYY-MM-DD:HH")
            return False


def num_valid_args():
    """Ensures the user has entered an allowed number of arguments and they adhere to expected
    types

    :return: int
    """
    usage_statement = "Usage: python3 git_clone_script.py <ASGN_TYPE> <ASGN_NUMBER> [ASGN_DEADLINE]"

    # check if exactly 2 arguments were entered correctly (assignment type & assignment number)
    if len(sys.argv[1:]) == 2:
        if not sys.argv[1].isalpha() or not sys.argv[2].isnumeric():
            print(usage_statement)
            exit(1)
        return 2

    # check if exactly 3 arguments were entered correctly (assignment type & assignment number & assignment deadline)
    elif len(sys.argv[1:]) == 3:
        if not sys.argv[1].isalpha() or not sys.argv[2].isnumeric() or not is_valid_date():
            print(usage_statement)
            exit(1)
        return 3

    # invalid number of arguments
    elif len(sys.argv[1:]) < 2 or len(sys.argv[1:]) > 3:
        print(usage_statement)
        return len(sys.argv[1:])


# ----------------------------------
# set semester-specific globals
# ----------------------------------

SEM_YEAR = 2025
SEM_MONTH_START = 9
SEM_MONTH_END = 12


# ----------------------------------
# set assignment-specific globals
# ----------------------------------

ASGN_TYPE = ""
ASGN_NUMBER = ""
ASGN_DEADLINE = ""

num_args = num_valid_args()

if num_args == 2:
    ASGN_TYPE = sys.argv[1]
    ASGN_NUMBER = sys.argv[2]
    # common pieces of URL for all students
    BASE_URL = f"https://github.com/CSc-335-Fall-2025/{ASGN_TYPE + "-" + ASGN_NUMBER}-[USERNAME].git"
elif num_args == 3:
    ASGN_TYPE = sys.argv[1]
    ASGN_NUMBER = sys.argv[2]

    # know its valid, just assign correct one
    try:
        ASGN_DEADLINE = datetime.strptime(sys.argv[3], "%Y-%m-%d")
    except ValueError:
        ASGN_DEADLINE = datetime.strptime(sys.argv[3], "%Y-%m-%d:%H")

    # common pieces of URL for all students
    BASE_URL = f"https://github.com/CSc-335-Fall-2025/{ASGN_TYPE + "-" + ASGN_NUMBER}-[USERNAME].git"
else:
    exit(1)


# ---------------------------
# set user-specific globals
# ---------------------------

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

    # if no name or username is recorded, skip it
    if len(line_elements) != 2 or line_elements[0].strip() == "" or line_elements[1].strip() == "":
        continue

    name, username = line_elements[0].strip(), line_elements[1].strip()
    names_usernames.append((name, username))


# --------------------------------------------------------------------------------------
# clone students' repo state prior to deadline to target directory and rename projects
# --------------------------------------------------------------------------------------

total_clones = 0

for name, username in names_usernames:
    print("\n")
    print("==================================================================")
    result_url = BASE_URL.replace("[USERNAME]", username)
    repo_name = ASGN_TYPE + "-" + ASGN_NUMBER + "-" + username

    # -C option specifies directory to mimic operating in
    # use run() because want to manually check the return code
    status = sp.run(["git", "-C", TARGET_DIR, "clone", result_url])

    # clone was successful
    if status.returncode == 0:
        # get the last commit prior to deadline
        # key git command: rev-list
        # should have a commit hash if repo was created, even if no pushes by student
        commit_hash = sp.check_output(["git", "-C", f"{TARGET_DIR}/{repo_name}", "rev-list", "-n", "1", f"--before={ASGN_DEADLINE}", "master"],
                                      text=True).strip()

        print(f"\n***CHECKING OUT LAST COMMIT PRIOR TO {ASGN_DEADLINE}***\n")
        sp.run(["git", "-C", f"{TARGET_DIR}/{repo_name}", "checkout", commit_hash])

        # change the project name
        project_file = Path(f"{TARGET_DIR}/{repo_name}/.project")
        if project_file.exists():
            # use XML parsing and editing tool (.project is XML)
            tree = ET.parse(project_file)
            root = tree.getroot()
            # change <name> tag
            name_tag = root.find("name")
            name_tag.text = repo_name
            tree.write(project_file, encoding="UTF-8", xml_declaration=True)
            print("")
            print(f"successfully renamed project to {repo_name}")
        else:
            print(f".project file not found in {repo_name}")

        total_clones += 1

    else:
        print(f"student name: {name}")

print("\n\n==================================================================")
print(f"{total_clones} student repos were cloned into {TARGET_DIR}\n\n")
