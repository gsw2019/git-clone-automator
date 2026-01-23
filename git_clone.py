"""
@author         Garret Wilson

Description:    Automates the process of cloning student GitHub repos with Eclipse projects to local machine.

Requirements:   Create a .env file following the template in .env.example
                Install dependencies in requirements.txt

Bonus Features: Renames student projects to their repo name so can simultaneously import all projects into Eclipse.
                Ensures project has minimal working structure. If not, fixes issues and rebuilds the project.

Invocation:     Must provide at least assignment type on command line.
                Can optionally provide an assignment number.
                Can optionally provide an assignment name.
                Can optionally provide an assignment deadline date in ISO 8601 format (YYYY-MM-DD).
                Example:    python3 git_clone.py project -num 1                                  ->  most recent commit
                Example:    python3 git_clone.py project -num 1 -d 2025-09-09                    ->  last commit prior to Sept 9th, 2025 12:00 AM
                Example:    python3 git_clone.py project -num 1 -name mastermind -d 2026-01-27   ->  last commit prior to Jan 27th, 2026 12:00 AM
                Example:    python3 git_clone.py lab -num 1 -d 2026-01-24                        ->  last commit prior to Jan 24th, 2026 12:00 AM
                Example:    python3 git_clone.py BoardGames -d 2025-12-09                        ->  last commit prior to Dec 9th, 2025 12:00 AM
"""


import subprocess as sp
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import argparse
from dotenv import dotenv_values


def get_args():
    """Ensures the user has minimal required arguments and they adhere to expected types

    :return: a populated namespace object with attributes defined by add_argument methods
    """
    # use library tool to get CL arguments
    # if invoked inappropriately will show a helpful usage message
    parser = argparse.ArgumentParser()
    parser.add_argument("ASGN_TYPE", type=str)                                                       # positional arg
    parser.add_argument("-num", "--number", dest="ASGN_NUM", type=int, help="assignment number")     # optional arg
    parser.add_argument("-name", "--name", dest="ASGN_NAME", type=str, help="assignment name")       # optional arg
    parser.add_argument("-d", "--deadline", dest="ASGN_DEADLINE", help="deadline date in ISO 8601")  # optional arg
    parser.add_argument("-f", "--file", dest="ASGN_TESTS", help="path to TA test suite")             # optional arg

    cl_args = parser.parse_args()      # default comes from sys.argv

    # check date if provided
    if getattr(cl_args, "ASGN_DEADLINE") is not None and not is_valid_date(getattr(cl_args, "ASGN_DEADLINE")):
        print(parser.print_help())
        exit(1)

    return cl_args


def is_valid_date(date):
    """Ensures the deadline date provided by the user is in ISO 8601 format and the
    date is within the semester range

    :param date: string of a date from CL args
    :return: True if okay date, False otherwise
    """
    # just check datetime can be parsed
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        print("Invalid ISO 8601 date for [-d ASGN_DEADLINE]. Format: YYYY-MM-DD")
        return False


def build_base_url(args, root_url):
    """String builds the URL that will be used to clone each repository.

    :param args: a namespace object with attributes defined from command line args
    :param root_url: the prefix url for the organization
    :return: a string URL
    """
    asgn_type = getattr(args, "ASGN_TYPE")  # at the least, have this
    asgn_num = getattr(args, "ASGN_NUM")
    asgn_name = getattr(args, "ASGN_NAME")

    # fill asgn name with dashes if it has spaces? Dashes seem to be GitHub standard. Potential case
    if asgn_name:
        asgn_name = asgn_name.replace(" ", "-")

    base_url = ""
    if asgn_num is None and asgn_name is None:
        base_url = f"{root_url}{asgn_type}-[USERNAME].git"
    elif asgn_name is None and asgn_num is not None:
        base_url = f"{root_url}{asgn_type}-{asgn_num}-[USERNAME].git"
    elif asgn_name is not None and asgn_num is None:
        base_url = f"{root_url}{asgn_type}-{asgn_name}-[USERNAME].git"        # probably not possible? final project?
    elif asgn_name is not None and asgn_num is not None:
        base_url = f"{root_url}{asgn_type}-{asgn_num}-{asgn_name}-[USERNAME].git"

    return base_url


def get_names_usernames(names_usernames_file):
    """Reads all the name, username pairs in the .csv specified in .env file

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

    observed issues:
        - has local paths to .jars
        - has git merge conflict remnants thus the ElementTree parser fails

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
                print('bad .classpath file: classpathentry tag with attribute and value pair: kind="lib"')
                return False

        return True

    except ET.ParseError as e:
        print(f"could not parse .classpath file: {e.msg.capitalize()}")
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

        # .// tells the XML parser to search recursively for tag (XPath)
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

    :param student_repo_local: Path object, path to student repo from target dir
    :return: string of the src dir local path
    """
    # search for first instance of src dir in student repo
    # if one exists will print path to stdout, otherwise prints nothing
    status = sp.run(["find", student_repo_local, "-type", "d", "-name", "src", "-print", "-quit"],
                    capture_output=True, text=True)
    if status.returncode != 0:
        print(f"error searching student repo for src dir: {status.returncode}")
        return

    # want the src dir path starting right after the project entry point
    if status.stdout != "":
        src_path = status.stdout        # path starts from cwd, the find just started in student_repo_local
        repo_name = student_repo_local.name
        path_from_project = src_path.split(repo_name)[1].lstrip("/").strip()
        return path_from_project

    return status.stdout


def inject_classpath_file(student_repo_local, default_classpath_file, src_dir="src"):
    """Injects a basic .classpath file into student repo. the file is configured to look for local
    machines JRE, Junit5 library, and JavaFX user library

    :param student_repo_local: Path object, local path to student repo
    :param default_classpath_file: path to default .classpath file
    :param src_dir: the path from repo root of an existing src dir. Defaults to src if not passed
    :return: None
    """
    new_classpath_file = f"{student_repo_local}/.classpath"

    status = sp.run(['cp', default_classpath_file, new_classpath_file])
    if status.returncode != 0:
        print(f"error injecting .classpath file: {status.returncode}")
        return

    if src_dir != "src":
        set_classpath_src(new_classpath_file, src_dir)

    print("injecting a .classpath file into student repo")


def set_classpath_src(classpath_file, src):
    """Set the path to src files from .classpath file. Only called when injecting basic
    .classpath so know its parsable

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


def get_classpath_src(classpath_file):
    """Get the path declared in .classpath that supposedly points to src files. Only called
    after known to be parsable

    :param classpath_file: .classpath file in student repo
    :return: path to src files found in .classpath
    """
    tree = ET.parse(classpath_file)
    root = tree.getroot()

    for tag in root.findall("classpathentry"):
        type_of_entry = tag.get("kind")

        if type_of_entry == "src":
            return tag.get("path")


def inject_project_file(student_repo_local, default_project_file):
    """Injects a basic .project file into student repo. Name tag is blank

    :param student_repo_local: Path object, local path to student repo
    :param default_project_file: path to default .project file
    :return: None
    """
    new_project_file = f"{student_repo_local}/.project"
    status = sp.run(['cp', default_project_file, new_project_file])

    if status.returncode != 0:
        print(f"error injecting .project file {status.returncode}")
        return

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
    print(f"renamed project to {repo_name}")


def create_src_dir(student_repo_local):
    """If src directory doesn't exist, creates a src directory in students repo at the top level with all
    packages and puts .java files in their respective packages

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
    # stdout will be the paths from the target dir
    java_files = sp.run(["find", student_repo_local, "-name", "*.java"],
                        capture_output=True, text=True, check=True).stdout.splitlines()

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
                    status = sp.run(["mv", file, new_package_dir])
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
    # --------------------------------------
    # set user-specific globals
    # --------------------------------------
    env_vars = dotenv_values('.env')

    # path of .csv file that contains student GitHub usernames
    # expected format: student, username
    usernames = env_vars.get("USERNAMES")

    # path to destination for storing repos
    target_dir = env_vars.get("TARGET_DIR")

    # path to basic .project file
    default_project_file = env_vars.get("PROJECT_FILE")

    # path to basic .classpath file
    default_classpath_file = env_vars.get("CLASSPATH_FILE")

    root_url = env_vars.get("ROOT_URL")

    # --------------------------------------------
    # gather info for clones and project renaming
    # --------------------------------------------
    args = get_args()

    asgn_deadline = getattr(args, 'ASGN_DEADLINE')
    if asgn_deadline is not None:
        asgn_deadline = datetime.strptime(asgn_deadline, "%Y-%m-%d")    # appends 00:00:00 onto the date

    # TODO: implement adding TA test suites if provided
    asgn_tests = getattr(args, "ASGN_TESTS")

    base_url = build_base_url(args, root_url)
    names_usernames = get_names_usernames(usernames)

    # --------------------------------------------
    # begin cloning
    # --------------------------------------------
    total_clones = 0

    for name, username in names_usernames:
        print("\n")
        print("=" * 80)
        result_url = base_url.replace("[USERNAME]", username)

        repo_start_index = result_url.rfind('/') + 1            # start after base url
        repo_end_index = result_url.rfind('.')                  # go until .git
        repo_name = result_url[repo_start_index:repo_end_index]

        # clone student repo
        # -C option specifies directory to mimic operating in
        # use run() because want to manually check the return code
        status = sp.run(["git", "-C", target_dir, "clone", result_url])

        # clone was successful
        if status.returncode == 0:
            student_repo_local = Path(f"{target_dir}/{repo_name}")

            if asgn_deadline is not None:
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
                    ["git", "-C", student_repo_local, "rev-list", "-n", "1", f"--before={asgn_deadline}",
                     default_branch],
                    text=True).strip()

                print(f"\n\n***CHECKING OUT LAST COMMIT PRIOR TO {asgn_deadline}***\n\n")
                status = sp.run(["git", "-C", student_repo_local, "checkout", commit_hash])
                if status.returncode != 0:
                    print(f"checkout failed: {status.returncode}")

            # define expected project contents
            project_file = Path(f"{student_repo_local}/.project")       # should always be top-level
            classpath_file = Path(f"{student_repo_local}/.classpath")   # should always be top-level
            src_dir = find_src_dir(student_repo_local)                  # function call because how checking if src is not top level

            # record project state
            project_state = {
                "project file": project_file.exists(),
                "classpath file": classpath_file.exists(),
                "src directory": src_dir
            }

            print("\n\nPROJECT STRUCTURE LOGS: ")

            # determine what is missing
            missing_content = [item for item, present in project_state.items() if not present or ""]
            missing_statement = f"project is missing: {", ".join(missing_content)}"

            # missing some minimal requirements
            if 0 < len(missing_content) < len(project_state):
                print(missing_statement)
                for item_name in project_state:
                    # is missing
                    if item_name in missing_content:
                        if item_name == "project file":
                            inject_project_file(student_repo_local, default_project_file)
                        elif item_name == "classpath file":
                            if src_dir != "":
                                inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)
                            else:
                                inject_classpath_file(student_repo_local, default_classpath_file)
                        elif item_name == "src directory":
                            # case where there is no src directory and classpath is set as such. Main class at top level
                            if is_valid_classpath_file(classpath_file) and get_classpath_src(classpath_file) == "":
                                pass
                            else:
                                create_src_dir(student_repo_local)
                    # not missing, but still need to check if okay
                    else:
                        if item_name == "project file" and not is_valid_project_file(project_file):
                            inject_project_file(student_repo_local, default_project_file)
                        elif item_name == "classpath file" and not is_valid_classpath_file(classpath_file):
                            # no info from .classpath file, but can assume it aligned with whatever src_dir is
                            inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)
            # missing all minimum requirements
            elif len(missing_content) == len(project_state):
                print(missing_statement)
                inject_project_file(student_repo_local, default_project_file)
                if src_dir != "":
                    inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)
                else:
                    inject_classpath_file(student_repo_local, default_classpath_file)
                    create_src_dir(student_repo_local)
            # okay project, but still need to look at .classpath and .project
            elif len(missing_content) == 0:
                if not is_valid_project_file(project_file):
                    inject_project_file(student_repo_local, default_project_file)
                if not is_valid_classpath_file(classpath_file):
                    inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)

            # always executed after checking .project, so we know it's parsable by the time reach here
            rename_project(project_file, repo_name)

            total_clones += 1

        else:
            print("\n")
            print(f"student name(s): {name}")
            print(f"student(s) GitHub username: {username}")

    print("\n\n" + "=" * 80)
    print(f"\n{total_clones} student repos were cloned into {target_dir}\n\n")


if __name__ == "__main__":
    main()
