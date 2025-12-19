"""
@author         Garret Wilson

Description:    Automates the process of cloning student Git repos to local machine.

Requirements:   Assumes a .csv with student names and usernames exists locally.
                    • with header line
                Assumes a .txt with minimal .project requirements exists locally.
                Assumes a .txt with minimal .classpath requirements exists locally.
                    • points to local machines JRE, JUnit 5, and JavaFX (expected to be user library)
                User needs to set their user-specific and semester-specific globals.

Bonus Features: Renames student projects to their repo name so can simultaneously import all projects into Eclipse.
                Ensures project has minimal working structure. If not, adds the needed files and rebuilds the project.

Invocation:     Must provide at least assignment type on command line.
                Can also provide an assignment number.
                Can optionally provide a deadline date in ISO 8601 format (YYYY-MM-DD)
                Example:    python3 git_clone_script.py project 1                   ->  most recent commit
                Example:    python3 git_clone_script.py project 1 -d 2025-09-09     ->  last commit prior to Sept 9th, 2025 12:00 AM
                Example:    python3 git_clone_script.py lab 2 -d 2025-09-21         ->  last commit prior to Sept 21st, 2025 12:00 AM
                Example:    python3 git_clone_script.py BoardGames -d 2025-12-09    ->  last commit prior to Dec 9th, 2025 12:00AM
"""


import subprocess as sp
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import argparse


# -------------------------------------------------------
# USER: set user-specific and semester-specific globals
# -------------------------------------------------------

# path of .csv file that contains student GitHub usernames
# expected format: student, username
# USERNAMES = "student_github_usernames.csv"
# USERNAMES = "proj5_student_github_usernames.csv"
USERNAMES = "proj6_student_github_usernames.csv"

# path to destination for storing repos
TARGET_DIR = "student_repos"

# path to basic .project file
PROJECT_FILE = "project_file.txt"

# path to basic .classpath file
CLASSPATH_FILE = "classpath_file.txt"

SEM_YEAR = 2025
SEM_MONTH_START = 9
SEM_MONTH_END = 12


def get_args():
    """Ensures the user has minimal required arguments and they adhere to expected types

    :return: a populated namespace object with attributes defined by add_argument methods
    """
    # use library tool to get CL arguments
    # if invoked inappropriately will show a helpful usage message
    parser = argparse.ArgumentParser()
    parser.add_argument("ASGN_TYPE", type=str)                                  # positional arg
    parser.add_argument("ASGN_NUMBER", nargs="?", type=int, default=None)       # positional arg
    parser.add_argument("-d", "--deadline", help="deadline date in ISO 8601")   # optional arg
    parser.add_argument("-f", "--file", help="path to TA test suite")           # optional arg
    cl_args = parser.parse_args()      # default comes from sys.argv

    # check date if provided
    if getattr(cl_args, "deadline") is not None and not is_valid_date(getattr(cl_args, "deadline")):
        print(parser.print_help())
        exit(1)

    return cl_args


def is_valid_date(date):
    """Ensures the deadline date provided by the user is in ISO 8601 format and the
    date is within the semester range

    :return: boolean
    """
    date_elements = date.split("-")
    num_date_elements = len(date_elements)

    # ensure year and month are within semester range
    if num_date_elements == 3 and int(date_elements[0]) != SEM_YEAR:
        print(f"Year is not of current semester ({SEM_YEAR})")
        return False
    if num_date_elements == 3 and (int(date_elements[1]) < SEM_MONTH_START or int(date_elements[1]) > SEM_MONTH_END):
        print(f"Month out of range ({SEM_MONTH_START} to {SEM_MONTH_END})")
        return False

    # check datetime can be parsed
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        print("Invalid ISO 8601 date for [--deadline DEADLINE]. Format: YYYY-MM-DD")
        return False


def build_base_url(args):
    """String building the URL that will be used to clone each repository.

    :param args: a namespace object with attributes defined from command line args
    :return: a string URL
    """
    asgn_type = getattr(args, "ASGN_TYPE")
    asgn_num = getattr(args, "ASGN_NUMBER")

    base_url = ""
    if asgn_num is None:
        base_url = f"https://github.com/CSc-335-Fall-2025/{asgn_type}-[USERNAME].git"
    else:
        base_url = f"https://github.com/CSc-335-Fall-2025/{asgn_type}-{asgn_num}-[USERNAME].git"

    return base_url


def get_names_usernames(names_usernames_file):
    """Reads all the name, username pairs in the .csv specified in this file

    :param names_usernames_file: the path to the .csv file of student GitHub usernames
    :return: a list of tuples each in the form (name, username)
    """
    names_usernames_file = open(names_usernames_file, "r")
    names_usernames = []

    # skips .csv header line
    for line in names_usernames_file.readlines()[1:]:
        line_elements = line.strip().split(",")

        # if no name or username is recorded, skip it
        if len(line_elements) != 2 or line_elements[0].strip() == "" or line_elements[1].strip() == "":
            continue

        name, username = line_elements[0].strip(), line_elements[1].strip()
        names_usernames.append((name, username))

    return names_usernames


def rename_project(project_file, repo_name):
    """Renames the students Eclipse project to their repo name. Edits the .project file
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


def inject_project_file(student_repo_local):
    """Injects a basic .project file into student repo. Name tag is blank

    :return: None
    """
    new_project_file = f"{student_repo_local}/.project"
    status = sp.run(['cp', PROJECT_FILE, new_project_file])

    if status.returncode == 0:
        print("injecting a .project file into student repo")
    else:
        print("failed injecting .project file")


def inject_classpath_file(student_repo_local):
    """Injects a basic .classpath file into student repo. the file is configured to looks for local
    machines JRE and Junit5 library

    :return: None
    """
    new_classpath_file = f"{student_repo_local}/.classpath"
    status = sp.run(['cp', CLASSPATH_FILE, new_classpath_file])

    if status.returncode == 0:
        print("injecting a .classpath file into student repo")
    else:
        print("failed injecting .classpath file")


def create_src_dir(student_repo_local):
    """If src folder doesn't exist, creates a src folder in students repo and moves all .java files to it

    # TODO: if rebuild and make a src file, check for package declarations in .java files and build them too

    :return: None
    """
    # create the src folder in students repo
    new_src_folder = f"{student_repo_local}/src"
    status = sp.run(['mkdir', new_src_folder])

    if status.returncode == 0:
        # find all the .java files in their repo
        # stdout will be the paths
        java_files = sp.run(["find", student_repo_local, "-name", "*.java"],
                            capture_output=True, text=True, check=True)

        # move each .java file to src folder
        for java_file in java_files.stdout.splitlines():
            sp.run(["mv", java_file, new_src_folder], check=True)

        print("created a src folder")
    else:
        print("failed creating src directory")


def is_valid_project_file(project_file):
    """Ensures the .project file has a minimum working format

    observed issues:
        - has <buildSpec> tag, but is missing child <buildCommand>
        - has <natures> tag, but is missing child <nature>
        - has git merge conflict remnants thus the ElementTree parser fails

    :return: True if .project is okay, False otherwise
    """
    try:
        tree = ET.parse(project_file)
        root = tree.getroot()

        # .// tells the XML parser to search recursively for tag (called an XPath)
        # to avoid warnings must compare to None instead of checking truthy or falsy
        if root.find(".//buildCommand") is None or root.find(".//nature") is None:
            print("inappropriate .project file")
            return False

        return True

    except ET.ParseError as e:
        print(f"could not parse .project file: {e.msg.capitalize()}")
        return False


def is_valid_classpath_file(classpath_file):
    """Ensures the .classpath file has a minimum working format

    observed issues:
        - many <classpathentry> tags with a kind="lib" attribute. Seems not using user libraries
        - has git merge conflict remnants thus the ElementTree parser fails

    :return: True if .classpath is okay, False otherwise
    """
    try:
        tree = ET.parse(classpath_file)
        root = tree.getroot()

        # loop over all <classpathentry> tags and look for kind="lib" attribute
        for tag in root.findall("classpathentry"):
            for attribute, value in tag.attrib.items():
                if attribute == "kind" and value == "lib":
                    print("inappropriate .classpath file")
                    return False

        return True

    except ET.ParseError as e:
        print(f"could not parse .classpath file. {e.msg.capitalize()}")
        return False


def main():
    # --------------------------------------------
    # Gather info for clones and project renaming
    # --------------------------------------------
    args = get_args()
    ASGN_TYPE = getattr(args, "ASGN_TYPE")
    ASGN_NUMBER = getattr(args, "ASGN_NUMBER")

    ASGN_DEADLINE = getattr(args, 'deadline')
    if ASGN_DEADLINE is not None:
        ASGN_DEADLINE = datetime.strptime(ASGN_DEADLINE, "%Y-%m-%d")    # appends 00:00:00 onto the date

    ASGN_TEST = getattr(args, "file")

    base_url = build_base_url(args)
    names_usernames = get_names_usernames(USERNAMES)

    # --------------------------------------------
    # Begin cloning
    # --------------------------------------------
    total_clones = 0

    for name, username in names_usernames:
        print("\n")
        print("=" * 80)
        result_url = base_url.replace("[USERNAME]", username)

        if ASGN_NUMBER is not None:
            repo_name = f"{ASGN_TYPE}-{ASGN_NUMBER}-{username}"
        else:
            repo_name = f"{ASGN_TYPE}-{username}"

        # clone student repo
        # -C option specifies directory to mimic operating in
        # use run() because want to manually check the return code
        status = sp.run(["git", "-C", TARGET_DIR, "clone", result_url])

        # clone was successful
        if status.returncode == 0:
            student_repo_local = f"{TARGET_DIR}/{repo_name}"

            if ASGN_DEADLINE is not None:
                # need to ensure we have the correct default branch name
                # stdout should be something like one of these:
                #   refs/remotes/origin/master
                #   refs/remotes/origin/main
                default_branch = sp.check_output(
                    ["git", "-C", student_repo_local, "symbolic-ref", "refs/remotes/origin/HEAD"],
                    text=True).strip().split("/")[-1]

                # get the last commit prior to deadline
                # key git command: rev-list
                # should have a commit hash if repo was created, even if no pushes by student
                commit_hash = sp.check_output(
                    ["git", "-C", student_repo_local, "rev-list", "-n", "1", f"--before={ASGN_DEADLINE}",
                     default_branch],
                    text=True).strip()

                print(f"\n\n***CHECKING OUT LAST COMMIT PRIOR TO {ASGN_DEADLINE}***\n\n")
                sp.run(["git", "-C", student_repo_local, "checkout", commit_hash])

            # TODO: number of cases that could be associated with project structure. Always room for more robustness

            # define vital project contents
            project_file = Path(f"{student_repo_local}/.project")
            classpath_file = Path(f"{student_repo_local}/.classpath")
            src_dir = Path(f"{student_repo_local}/src")

            # record project state
            project_state = {
                project_file.name: project_file.exists(),
                classpath_file.name: classpath_file.exists(),
                src_dir.name: src_dir.exists()
            }

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
                            inject_project_file(student_repo_local)
                        elif item_name == classpath_file.name:
                            inject_classpath_file(student_repo_local)
                        elif item_name == src_dir.name:
                            create_src_dir(student_repo_local)
                    else:
                        if item_name == project_file.name and not is_valid_project_file(project_file):
                            inject_project_file(student_repo_local)
                        elif item_name == classpath_file.name and not is_valid_classpath_file(classpath_file):
                            inject_classpath_file(student_repo_local)
                        elif item_name == src_dir.name:
                            if not src_dir.exists():
                                create_src_dir(student_repo_local)
            # missing all minimum requirements
            elif len(missing_content) == len(project_state):
                print(missing_statement)
                inject_project_file(student_repo_local)
                inject_classpath_file(student_repo_local)
                create_src_dir(student_repo_local)
            # okay project, but still need to look at .classpath and .project and ensure has src dir
            elif len(missing_content) == 0:
                if not is_valid_project_file(project_file):
                    inject_project_file(student_repo_local)
                if not is_valid_classpath_file(classpath_file):
                    inject_classpath_file(student_repo_local)
                if not src_dir.exists():
                    create_src_dir(student_repo_local)

            # always executed after checking .project, so we know it's parsable by the time reach here
            rename_project(project_file, repo_name)

            total_clones += 1

        else:
            print(f"student name(s): {name}")
            print(f"student(s) GitHub username: {username}")

    print("\n\n" + "=" * 80)
    print(f"\n{total_clones} student repos were cloned into {TARGET_DIR}\n\n")


if __name__ == "__main__":
    main()
