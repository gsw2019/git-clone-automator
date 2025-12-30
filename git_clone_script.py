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


# --------------------------------------
# USER: set user-specific globals
# --------------------------------------

# path of .csv file that contains student GitHub usernames
# expected format: student, username
# USERNAMES = "student_github_usernames.csv"
USERNAMES = "proj5_student_github_usernames.csv"
# USERNAMES = "proj6_student_github_usernames.csv"

# path to destination for storing repos
TARGET_DIR = "student_repos"

# path to basic .project file
PROJECT_FILE = "project_file.txt"

# path to basic .classpath file
CLASSPATH_FILE = "classpath_file.txt"


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

    :param date: string of a date from CL args
    :return: boolean
    """
    # check datetime can be parsed
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        print("Invalid ISO 8601 date for [--deadline DEADLINE]. Format: YYYY-MM-DD")
        return False


def build_base_url(args):
    """String builds the URL that will be used to clone each repository.

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


def is_valid_classpath_file(classpath_file):
    """Ensures the .classpath file has a minimum working format

    :param classpath_file: path to the .classpath file
    :return: True if .classpath is okay, False otherwise
    """
    try:
        tree = ET.parse(classpath_file)
        root = tree.getroot()

        # loop over all <classpathentry> tags and look for known issue attributes
        for tag in root.findall("classpathentry"):
            type_of_entry = tag.get("kind")

            if type_of_entry == "lib":
                print(f"bad .classpath file: classpathentry tag with attribute and value as kind=lib")
                return False

        return True

    except ET.ParseError as e:
        print(f"could not parse .classpath file. {e.msg.capitalize()}")
        return False


def is_valid_project_file(project_file):
    """Ensures the .project file has a minimum working format

    observed issues:
        - has <buildSpec> tag, but is missing child <buildCommand>
        - has <natures> tag, but is missing child <nature>
        - has git merge conflict remnants thus the ElementTree parser fails

    :param project_file: path to the .project file
    :return: True if .project is okay, False otherwise
    """
    try:
        tree = ET.parse(project_file)
        root = tree.getroot()

        # .// tells the XML parser to search recursively for tag (called an XPath)
        # to avoid warnings must compare to None instead of checking truthy or falsy
        if root.find(".//buildCommand") is None:
            print("bad .project file: missing buildCommand tag")
            return False
        if root.find(".//nature") is None:
            print("bad .project file: missing nature tag")
            return False

        return True

    except ET.ParseError as e:
        print(f"could not parse .project file: {e.msg.capitalize()}")
        return False


def find_src_dir(student_repo_local):
    """Checks if the project has a src folder. Isn't required to be top-level

    :param student_repo_local: Path object, local path to student repo
    :return: string of the src dir local path
    """
    # search for first instance of src dir in student repo
    # if one exists will print path to stdout, otherwise prints nothing
    status = sp.run(["find", student_repo_local, "-type", "d", "-name", "src", "-print", "-quit"],
                    capture_output=True, text=True)
    if status.returncode != 0:
        print(f"error searching student repo for src dir: {status.returncode}")

    # want the src dir path from the project entry point
    if status.stdout != "":
        src_path = status.stdout
        repo_name = student_repo_local.name
        path_from_project = src_path.split(repo_name)[1].lstrip("/").strip()
        return path_from_project

    return status.stdout


def inject_classpath_file(student_repo_local, src_dir="src"):
    """Injects a basic .classpath file into student repo. the file is configured to looks for local
    machines JRE and Junit5 library

    :param src_dir: the path from repo root of an existing src dir
    :param student_repo_local: Path object, local path to student repo
    :return: None
    """
    new_classpath_file = f"{student_repo_local}/.classpath"

    status = sp.run(['cp', CLASSPATH_FILE, new_classpath_file])
    if status.returncode != 0:
        print(f"error injecting .classpath file: {status.returncode}")

    if src_dir != "src":
        set_classpath_src(new_classpath_file, src_dir)

    print("injecting a .classpath file into student repo")


def set_classpath_src(classpath_file, src):
    """Set the path to src files from .classpath file. Only call when injecting basic
    .classpath

    :param classpath_file: .classpath file in student repo
    :param src: path from repo root to src files
    :return: None
    """
    tree = ET.parse(classpath_file)
    root = tree.getroot()

    for tag in root.findall("classpathentry"):
        type_of_entry = tag.get("kind")

        if type_of_entry == "src":
            tag.set("path", src)
            break

    tree.write(classpath_file, encoding="UTF-8", xml_declaration=True)


def inject_project_file(student_repo_local):
    """Injects a basic .project file into student repo. Name tag is blank

    :param student_repo_local: Path object, local path to student repo
    :return: None
    """
    new_project_file = f"{student_repo_local}/.project"
    status = sp.run(['cp', PROJECT_FILE, new_project_file])

    if status.returncode != 0:
        print(f"error injecting .project file {status.returncode}")

    print("injecting a .project file into student repo")


def rename_project(project_file, repo_name):
    """Renames the students Eclipse project to their repo name. Edits the .project file
    using XML parser package

    :param project_file: path to the .project file
    :param repo_name: name of the local repo
    :return: None
    """
    # use XML parsing and editing tool (.project is XML)
    # Only rename after checking project file. Don't need try-except for parsing here
    tree = ET.parse(project_file)
    root = tree.getroot()
    # change <name> tag, first instance is project name
    name_tag = root.find("name")
    name_tag.text = repo_name
    tree.write(project_file, encoding="UTF-8", xml_declaration=True)
    print(f"successfully renamed project to {repo_name}")


def create_src_dir(student_repo_local):
    """If src directory doesn't exist, creates a src directory in students repo with all packages and
    puts .java files in their respective packages

    :param student_repo_local: Path object, local path to student repo
    :return: path to new local src dir
    """
    # create the src dir in students repo
    new_src_dir = f"{student_repo_local}/src"
    status = sp.run(['mkdir', new_src_dir])
    if status.returncode != 0:
        print(f"error creating src directory: {status.returncode}")
        return

    print("created a src directory")

    # find all the .java files in their repo
    # stdout will be the full paths from the target dir
    java_files = sp.run(["find", student_repo_local, "-name", "*.java"],
                        capture_output=True, text=True, check=True).stdout.splitlines()

    # TODO: main file usually doesnt have a package declaration. Currently getting left out of src

    packages = []       # keep a running list so don't duplicate packages
    # check if any .java files declare packages
    for file in java_files:
        file_lines = open(file).readlines()
        has_package = False

        for line in file_lines:
            # avoid comment lines
            if line.startswith("//") or line.startswith("*") or line.startswith("/*") or line.startswith("/**") or line.startswith("*/"):
                continue

            # found package declaration
            if line.find("package") != -1:
                has_package = True
                package_name = line.split(" ")[1].strip().rstrip(";")    # get word after 'package' and remove semicolon
                new_package_dir = f"{new_src_dir}/{package_name}"

                # if its already been created, just add file to it
                if package_name in packages:
                    status = sp.run(["mv", file, f"{new_package_dir}"])
                    if status.returncode != 0:
                        print(f"error moving {file} to {new_package_dir}: {status.returncode}")

                    break

                packages.append(package_name)

                # create package in src
                status = sp.run(["mkdir", new_package_dir])
                if status.returncode != 0:
                    print(f"error creating package {new_package_dir}: {status.returncode}")

                # move .java file to its respective package
                status = sp.run(["mv", file, new_package_dir])
                if status.returncode != 0:
                    print(f"error moving {file} to {new_package_dir}: {status.returncode}")

                break

        if not has_package:
            status = sp.run(["mv", file, new_src_dir])
            if status.returncode != 0:
                print(f"error moving {file} to {new_src_dir}: {status.returncode}")

    return new_src_dir


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
            student_repo_local = Path(f"{TARGET_DIR}/{repo_name}")

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
                status = sp.run(["git", "-C", student_repo_local, "checkout", commit_hash])
                if status.returncode != 0:
                    print(f"checkout failed: {status.returncode}")

            # define expected project contents
            project_file = Path(f"{student_repo_local}/.project")       # should always be top-level
            classpath_file = Path(f"{student_repo_local}/.classpath")   # should always be top-level
            src_dir = find_src_dir(student_repo_local)                  # because how checking if src is not top level

            # record project state
            project_state = {
                "project file": project_file.exists(),
                "classpath file": classpath_file.exists()
            }

            # determine what is missing
            missing_content = [item for item, present in project_state.items() if not present]
            missing_statement = f"project is missing: {", ".join(missing_content)}"

            print("\n")
            # missing some minimal requirements
            if 0 < len(missing_content) < len(project_state):
                print(missing_statement)
                for item_name in project_state:
                    # is missing
                    if item_name in missing_content:
                        if item_name == "project file":
                            inject_project_file(student_repo_local)
                        elif item_name == "classpath file":
                            if src_dir != "":
                                inject_classpath_file(student_repo_local, src_dir=src_dir)
                            # no .classpath and no src, so must make both
                            else:
                                inject_classpath_file(student_repo_local)
                                create_src_dir(student_repo_local)
                    # not missing, but still need to check if okay
                    else:
                        if item_name == "project file" and not is_valid_project_file(project_file):
                            inject_project_file(student_repo_local)
                        elif item_name == "classpath file" and not is_valid_classpath_file(classpath_file):
                            # no info from .classpath file, but can assume it aligned with whatever src_dir is
                            inject_classpath_file(student_repo_local, src_dir=src_dir)
            # missing all minimum requirements
            elif len(missing_content) == len(project_state):
                print(missing_statement)
                inject_project_file(student_repo_local)
                if src_dir != "":
                    inject_classpath_file(student_repo_local, src_dir=src_dir)
                else:
                    inject_classpath_file(student_repo_local)
                    create_src_dir(student_repo_local)
            # okay project, but still need to look at .classpath and .project
            elif len(missing_content) == 0:
                if not is_valid_project_file(project_file):
                    inject_project_file(student_repo_local)
                if not is_valid_classpath_file(classpath_file):
                    inject_classpath_file(student_repo_local, src_dir=src_dir)

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
