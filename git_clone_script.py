"""
File:           git_clone_script.py
Author:         Garret Wilson
Description:    Automates the process of cloning student Git repos to your machine.

                Assumes a .csv with student names and usernames exists locally
                    • w/ header line
                Assumes a .txt with minimal .project requirements exists locally.
                Assumes a .txt with minimal .classpath requirements exists locally.
                    • points to machines JRE
                    • points to Junit5
                    • points to JavaFX that is set up in user libraries

                User needs to set their user-specific globals.

                User needs to set their semester-specific date ranges.

                Must provide at least assignment type and assignment number on command line.
                Can add deadline date and time in ISO 8601 format (YYYY-MM-DD or YYYY-MM-DD:HH), If hour is not
                    provided, defaults to 00:00:00.
                Example:    python3 git_clone_script.py  project 1               ->  most recent commit
                Example:    python3 git_clone_script.py  project 1 2025-09-09    ->  last commit prior to Sept 9th, 2025 12:00 AM
                Example:    python3 git_clone_script.py  lab 2 2025-09-20:19     ->  last commit prior to Sept 20th, 2025 7:00 PM

                Renames student projects to their repo name so can simultaneously import all projects into Eclipse.
                Ensures project has minimal working structure. If not, adds the needed files and rebuilds the project.
"""

import sys
import subprocess as sp
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

# ----------------------------------
# USER: set user-specific globals
# ----------------------------------

# path to destination for storing repos
TARGET_DIR = "student_repos"

# path of .csv file that contains student GitHub usernames
# expected format: student, username
# USERNAMES = "student_github_usernames.csv"
USERNAMES = "student_github_usernames_proj5.csv"
# USERNAMES = "student_github_usernames_proj6.csv"

# path to basic .project file
PROJECT_FILE = "project_file.txt"

# path to basic .classpath file
CLASSPATH_FILE = "classpath_file.txt"

# -------------------------------------
# USER: set semester-specific globals
# -------------------------------------

SEM_YEAR = 2025
SEM_MONTH_START = 9
SEM_MONTH_END = 12


def is_valid_date():
    """Ensures the deadline date provided by the user is in ISO 8601 format and the
    date is within the semester range

    :return: boolean
    """
    date_elements = sys.argv[3].split("-")
    num_date_elements = len(date_elements)

    # ensure year and month are within semester range
    if num_date_elements == 3 and int(date_elements[0]) != SEM_YEAR:
        print(f"Year is not of current semester ({SEM_YEAR})")
        return False
    if num_date_elements == 3 and (int(date_elements[1]) < SEM_MONTH_START or int(date_elements[1]) > SEM_MONTH_END):
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


# --------------------------------------------------------
# set assignment-specific globals from command line args
# --------------------------------------------------------

ASGN_TYPE = ""
ASGN_NUMBER = ""
ASGN_DEADLINE = ""

num_args = num_valid_args()

if num_args == 2:
    ASGN_TYPE = sys.argv[1]
    ASGN_NUMBER = sys.argv[2]
    # common pieces of URL for all students
    BASE_URL = f"https://github.com/CSc-335-Fall-2025/{ASGN_TYPE}-{ASGN_NUMBER}-[USERNAME].git"
    # BASE_URL = f"https://github.com/CSc-335-Fall-2025/-[USERNAME].git"
elif num_args == 3:
    ASGN_TYPE = sys.argv[1]
    ASGN_NUMBER = sys.argv[2]

    # know its valid, just assign correct one
    try:
        ASGN_DEADLINE = datetime.strptime(sys.argv[3], "%Y-%m-%d")
    except ValueError:
        ASGN_DEADLINE = datetime.strptime(sys.argv[3], "%Y-%m-%d:%H")

    # common pieces of URL for all students
    BASE_URL = f"https://github.com/CSc-335-Fall-2025/{ASGN_TYPE}-{ASGN_NUMBER}-[USERNAME].git"
    # BASE_URL = f"https://github.com/CSc-335-Fall-2025/-[USERNAME].git"
else:
    exit(1)

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
# clone students' repo states to target directory (prior to deadline, if provided),
# rename projects, and fix project structure if needed
# --------------------------------------------------------------------------------------

def rename_project():
    """
    renames the students Eclipse project to their repo name. Edits the .project file
    using XML parser package

    :return: None
    """
    # use XML parsing and editing tool (.project is XML)
    # should only rename after checking project file. Don't need try-except here
    tree = ET.parse(project_file)
    root = tree.getroot()
    # change <name> tag, first instance is project name
    name_tag = root.find("name")
    name_tag.text = repo_name
    tree.write(project_file, encoding="UTF-8", xml_declaration=True)
    print(f"successfully renamed project to {repo_name}")


def inject_project_file():
    """
    injects a basic .project file into student repo. Name tag is blank

    :return: None
    """
    new_project_file = f"{student_repo_local}/.project"
    # need 'a' arg because we know the file doesn't exist (no second arg defaults to 'r')
    open(new_project_file, 'a').close()
    sp.run(['cp', PROJECT_FILE, new_project_file])
    print("injecting a .project file into student repo")


def inject_classpath_file():
    """
    injects a basic .classpath file into student repo. Looks for local machines JRE and Junit5 library

    :return: None
    """
    new_classpath_file = f"{student_repo_local}/.classpath"
    open(new_classpath_file, 'a').close()
    sp.run(['cp', CLASSPATH_FILE, new_classpath_file])
    print("injecting a .classpath file into student repo")


def create_src_dir():
    """
    if src folder doesn't exist, creates a src folder in students repo and moves all .java files
    to it

    # TODO: if rebuild and make a src file, check for package declarations in .java files and build them too

    :return: None
    """
    # create the src folder in students repo
    new_src_folder = f"{student_repo_local}/src"
    sp.run(['mkdir', new_src_folder])

    # find all the .java files in their repo
    # stdout will be the paths
    java_files = sp.run(["find", student_repo_local, "-name", "*.java"],
                        capture_output=True, text=True, check=True)

    # move each .java file to src folder
    for java_file in java_files.stdout.splitlines():
        sp.run(["mv", java_file, new_src_folder], check=True)

    print("created a src folder")


def check_project_file():
    """
    ensures the .project file has a minimum working format. If format is invalid,
    will inject the basic project file.

    observed issues:
        - has <buildSpec> tag, but is missing child <buildCommand>
        - has <natures> tag, but is missing child <nature>
        - has git merge conflict remnants thus the ElementTree parser fails

    :return: None
    """
    try:
        tree = ET.parse(project_file)
        root = tree.getroot()

        # .// tells the XML parser to search recursively for tag (XPath)
        # to avoid warnings must compare to None instead of checking truthy or falsy
        if root.find(".//buildCommand") is None or root.find(".//nature") is None:
            print("inappropriate .project file")
            inject_project_file()
            return

    except ET.ParseError as e:
        print(f"could not parse .project file: {e.msg.capitalize()}")
        inject_project_file()


def check_classpath_file():
    """
    ensures the .classpath file has a minimum working format. If format is invalid,
    will inject the basic classpath file

    observed issues:
        - many <classpathentry> tags with a kind="lib" attribute. Seems not using user libraries
        - has git merge conflict remnants thus the ElementTree parser fails

    :return: None
    """
    try:
        tree = ET.parse(classpath_file)
        root = tree.getroot()

        # loop over all <classpathentry> tags and look for kind="lib" attribute
        for tag in root.findall("classpathentry"):
            for attribute, value in tag.attrib.items():
                if attribute == "kind" and value == "lib":
                    print("inappropriate .classpath file")
                    inject_classpath_file()
                    return

    except ET.ParseError as e:
        print(f"could not parse .classpath file. {e.msg.capitalize()}")
        inject_classpath_file()


total_clones = 0

# each iteration the globals are getting reset before the parameterless functions that use them are called
# could just pass them to functions to begin looking a bit more modular and facilitate better understandability
for name, username in names_usernames:
    print("\n")
    print("=" * 80)
    result_url = BASE_URL.replace("[USERNAME]", username)
    repo_name = ASGN_TYPE + "-" + ASGN_NUMBER + "-" + username

    # clone student repo
    # -C option specifies directory to mimic operating in
    # use run() because want to manually check the return code
    status = sp.run(["git", "-C", TARGET_DIR, "clone", result_url])

    # clone was successful
    if status.returncode == 0:
        student_repo_local = f"{TARGET_DIR}/{repo_name}"

        if ASGN_DEADLINE != "":
            # need to ensure we have the correct default branch name
            # stdout should be something like one of these:
            #   refs/remotes/origin/master
            #   refs/remotes/origin/main
            default_branch = sp.check_output(
                ["git", "-C", student_repo_local, "symbolic-ref", "refs/remotes/origin/HEAD"],
                text=True).strip().split("/")[-1]

            # get the last commit prior to deadline if provided
            # key git command: rev-list
            # should have a commit hash if repo was created, even if no pushes by student
            commit_hash = sp.check_output(
                ["git", "-C", student_repo_local, "rev-list", "-n", "1", f"--before={ASGN_DEADLINE}", default_branch],
                text=True).strip()

            print(f"\n\n***CHECKING OUT LAST COMMIT PRIOR TO {ASGN_DEADLINE}***\n\n")
            sp.run(["git", "-C", student_repo_local, "checkout", commit_hash])

        # TODO: number of cases that could be associated with project structure. Always room for more robustness

        # define vital project contents
        project_file = Path(f"{student_repo_local}/.project")
        classpath_file = Path(f"{student_repo_local}/.classpath")
        src_dir = Path(f"{student_repo_local}/src")

        # record project state
        project_state = {project_file.name: project_file.exists(),
                         classpath_file.name: classpath_file.exists(),
                         src_dir.name: src_dir.exists()}

        # determine what is missing
        missing_content = [item for item, present in project_state.items() if not present]
        missing_statement = f"project is missing: {", ".join(missing_content)}"

        print("\n")
        # missing some minimal requirements
        if 0 < len(missing_content) < len(project_state):
            print(missing_statement)
            for item_name in project_state:
                if item_name in missing_content:
                    if item_name == project_file.name:
                        inject_project_file()
                    elif item_name == classpath_file.name:
                        inject_classpath_file()
                    elif item_name == src_dir.name:
                        create_src_dir()
                else:
                    if item_name == project_file.name:
                        check_project_file()
                    elif item_name == classpath_file.name:
                        check_classpath_file()
                    elif item_name == src_dir.name:
                        if not src_dir.exists():
                            create_src_dir()
        # missing all minimum requirements
        elif len(missing_content) == len(project_state):
            print(missing_statement)
            inject_project_file()
            inject_classpath_file()
            create_src_dir()
        # okay project, but still need to look at .classpath and .project and ensure has src dir
        elif len(missing_content) == 0:
            check_project_file()
            check_classpath_file()
            if not src_dir.exists():
                create_src_dir()

        # always executed after checking .project, so we know it's parsable by the time reach here
        rename_project()

        total_clones += 1

    else:
        print(f"student name: {name}")
        print(f"student GitHub username: {username}")

print("\n\n" + "=" * 80)
print(f"\n{total_clones} student repos were cloned into {TARGET_DIR}\n\n")
