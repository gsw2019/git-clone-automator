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
from argparse import ArgumentParser
from datetime import datetime
from multiprocessing.managers import Namespace
from pathlib import Path
import xml.etree.ElementTree as ET
import argparse
from subprocess import CompletedProcess
from typing import TextIO
from dotenv import dotenv_values


def get_args() -> Namespace:
    """Ensures the user has minimal required arguments and they adhere to expected types

    :return: a populated namespace object with attributes defined by add_argument methods
    """
    # use library tool to get CL arguments
    # if invoked inappropriately will show a helpful usage message
    parser: ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("ASGN_TYPE", type=str)                                                       # positional arg
    parser.add_argument("-num", "--number", dest="ASGN_NUM", type=int, help="assignment number")     # optional arg
    parser.add_argument("-name", "--name", dest="ASGN_NAME", type=str, help="assignment name")       # optional arg
    parser.add_argument("-d", "--deadline", dest="ASGN_DEADLINE", help="deadline date in ISO 8601")  # optional arg
    parser.add_argument("-f", "--file", dest="ASGN_TESTS", help="path to TA test suite")             # optional arg

    cl_args: Namespace = parser.parse_args()      # default comes from sys.argv

    # check date if provided
    if cl_args.ASGN_DEADLINE is not None and not is_valid_date(cl_args.ASGN_DEADLINE):
        print(parser.print_help())
        exit(1)

    return cl_args


def is_valid_date(date: str) -> bool:
    """Ensures the deadline date provided by the user is in ISO 8601 format and the date is within the
    semester range

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


def build_base_url(args: Namespace, root_url: str) -> str:
    """String builds the URL that will be used to clone each repository.

    :param args: a namespace object with attributes defined from command line args
    :param root_url: the prefix url for the organization
    :return: a string URL
    """
    asgn_type: str = args.ASGN_TYPE  # at the least, have this
    asgn_num: str = args.ASGN_NUM
    asgn_name: str = args.ASGN_NAME

    # fill asgn name with dashes if it has spaces? Dashes seem to be GitHub standard. Potential case
    if asgn_name:
        asgn_name = asgn_name.replace(" ", "-")

    base_url: str = ""
    if asgn_num is None and asgn_name is None:
        base_url = f"{root_url}{asgn_type}-[USERNAME].git"
    elif asgn_name is None and asgn_num is not None:
        base_url = f"{root_url}{asgn_type}-{asgn_num}-[USERNAME].git"
    elif asgn_name is not None and asgn_num is None:
        base_url = f"{root_url}{asgn_type}-{asgn_name}-[USERNAME].git"        # probably not possible? final project?
    elif asgn_name is not None and asgn_num is not None:
        base_url = f"{root_url}{asgn_type}-{asgn_num}-{asgn_name}-[USERNAME].git"

    return base_url


def get_names_usernames(names_usernames_file: Path) -> list[tuple[str, str]]:
    """Reads all the name, username pairs in the .csv specified in .env file

    :param names_usernames_file: the path to the .csv file of student GitHub usernames
    :return: a list of tuples each in the form (name, username)
    """
    names_usernames_file: TextIO = open(names_usernames_file, "r")
    names_usernames: list[tuple[str, str]] = []

    # skips .csv header line
    for line in names_usernames_file.readlines()[1:]:
        line_elements: list[str] = line.strip().split(",")

        # if no name or username is recorded, skip it
        if len(line_elements) != 2 or line_elements[0].strip() == "" or line_elements[1].strip() == "":
            continue

        name, username = line_elements[0].strip(), line_elements[1].strip()
        names_usernames.append((name, username))

    names_usernames_file.close()

    return names_usernames


def is_valid_classpath_file(classpath_file: Path) -> bool:
    """Ensures the .classpath file has a minimum working format

    observed issues:
        - has local paths to .jars
        - has git merge conflict remnants thus the ElementTree parser fails

    :param classpath_file: path to the .classpath file
    :return: True if .classpath is okay, False otherwise
    """
    try:
        tree: ET.ElementTree = ET.parse(classpath_file)
        root: ET.Element = tree.getroot()

        # loop over all <classpathentry> tags and look for known issue attributes
        for tag in root.findall("classpathentry"):
            type_of_entry: str = tag.get("kind")

            if type_of_entry == "lib":
                print('bad .classpath file: classpathentry tag with attribute and value pair: kind="lib"')
                return False

        return True

    except ET.ParseError as e:
        print(f"could not parse .classpath file. Error code: {e.code}, {e.msg.capitalize()}")
        return False


def is_valid_project_file(project_file) -> bool:
    """Ensures the .project file has a minimum working format

    observed issues:
        - has <buildSpec> tag, but is missing child <buildCommand>
        - has <natures> tag, but is missing child <nature>
        - has git merge conflict remnants thus the ElementTree parser fails

    :param project_file: path to the .project file
    :return: True if .project is okay, False otherwise
    """
    try:
        tree: ET.ElementTree = ET.parse(project_file)
        root: ET.Element = tree.getroot()

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
        print(f"could not parse .project file. Error code: {e.code}, {e.msg.capitalize()}")
        return False


def find_src_dir(student_repo_local) -> str | None:
    """Checks if the project has a src folder. Isn't required to be top-level

    Function only returns None when the search fails

    :param student_repo_local: Path object, path to student repo from target dir
    :return: string of the src dir local path or None
    """
    # search for first instance of src dir in student repo
    try:
        # rglob to recursively search for src dir
        for src_dir in student_repo_local.rglob('src'):
            if src_dir.is_dir():
                return str(src_dir.relative_to(student_repo_local))
    except OSError as e:
        print(f"error searching student repo for src dir. Error code: {e.errno}, {e.strerror}")
        return None

    return ""


def inject_classpath_file(student_repo_local: Path, default_classpath_file: Path, src_dir: str="src") -> None:
    """Injects a basic .classpath file into student repo. the file is configured to look for local
    machines JRE, Junit5 library, and JavaFX user library

    :param student_repo_local: Path object, local path to student repo
    :param default_classpath_file: path to default .classpath file
    :param src_dir: the path from repo root of an existing src dir. Defaults to src if not passed
    :return: None
    """
    new_classpath_file: Path = student_repo_local / ".classpath"
    try:
        default_classpath_file.copy(new_classpath_file)     # returns path to target
    except OSError as e:
        print(f"error injecting .classpath file. Error code: {e.errno}, {e.strerror}")
        return

    if src_dir != "src":
        set_classpath_src(new_classpath_file, src_dir)

    print("injecting a .classpath file into student repo (build path error, deductible)")


def set_classpath_src(classpath_file: Path, src: str) -> None:
    """Set the path to src files from .classpath file. Only called when injecting basic
    .classpath so know its parsable

    :param classpath_file: .classpath file in student repo
    :param src: path from repo root to src files
    :return: None
    """
    tree: ET.ElementTree = ET.parse(classpath_file)
    root: ET.Element = tree.getroot()

    for tag in root.findall("classpathentry"):
        type_of_entry: str = tag.get("kind")

        if type_of_entry == "src":
            tag.set("path", src)
            break

    tree.write(classpath_file, encoding="UTF-8", xml_declaration=True)


def get_classpath_src(classpath_file: Path) -> str:
    """Get the path declared in .classpath that supposedly points to src files. Only called
    after known to be parsable

    :param classpath_file: .classpath file in student repo
    :return: path to src files found in .classpath
    """
    tree: ET.ElementTree = ET.parse(classpath_file)
    root: ET.Element = tree.getroot()

    for tag in root.findall("classpathentry"):
        type_of_entry: str = tag.get("kind")

        if type_of_entry == "src":
            return tag.get("path")

    return ""


def inject_project_file(student_repo_local: Path, default_project_file: Path) -> None:
    """Injects a basic .project file into student repo. Name tag is blank

    :param student_repo_local: Path object, local path to student repo
    :param default_project_file: path to default .project file
    :return: None
    """
    new_project_file: Path = student_repo_local / ".project"
    try:
        default_project_file.copy(new_project_file)
    except OSError as e:
        print(f"error injecting .project file. Error code {e.errno}, {e.strerror}")
        return

    print("injecting a .project file into student repo (build path error, deductible)")


def rename_project(project_file: Path, repo_name: str) -> None:
    """Renames the students Eclipse project to their repo name. Edits the .project file
    using XML parser package

    :param project_file: path to the .project file
    :param repo_name: name of the local repo
    :return: None
    """
    # use XML parsing and editing tool (.project is XML)
    # Only rename after checking project file. Don't need try-except for parsing here
    tree: ET.ElementTree = ET.parse(project_file)
    root: ET.Element = tree.getroot()
    # change <name> tag, first instance is project name
    name_tag: ET.Element[str] = root.find("name")
    name_tag.text = repo_name
    tree.write(project_file, encoding="UTF-8", xml_declaration=True)
    print(f"renamed project to {repo_name}")


def create_src_dir(student_repo_local: Path, src_dir_path: str = "src") -> Path | None:
    """Called after determining a src directory doesn't exist. Creates a src directory and subdirectories (packages) in
    students repo at the top level. if srd_dir_path is passed, will create src there.

    Function only returns None when fails to make src dir or fails to search for .java files

    :param student_repo_local: Path object, local path to student repo
    :param src_dir_path: expected path of src directory
    :return: path to new local src dir or None
    """
    # create a top level src dir in students repo
    if src_dir_path != "src":
        new_src_dir: Path = student_repo_local / src_dir_path
    else:
        new_src_dir: Path = student_repo_local / "src"

    try:
        new_src_dir.mkdir()
    except OSError as e:
        print(f"error creating src directory. Error code: {e.errno}, {e.strerror}")
        return None

    print("created a src directory (build path or compilation error, deductible)")

    # find all the .java files in the repo
    try:
        # rglob to recursively search for java files
        # must cast to list so is a snap shot of rglob()
        java_files: list[Path] = list(student_repo_local.rglob("*.java"))
    except OSError as e:
        print(f"error searching student repo for .java files. Error code: {e.errno}, {e.strerror}")
        return None

    packages: list[str] = []       # keep a running list so don't duplicate packages
    # check if any .java files declare packages
    for file in java_files:
        file_lines: list[str] = open(file).readlines()
        has_package: bool = False

        for line in file_lines[:50]:    # only check first 50 lines...no reason package declaration is anywhere else
            # avoid comment lines
            if line.startswith("//") or line.startswith("*") or line.startswith("/*") or line.startswith("/**") or line.startswith("*/"):
                continue

            # found package declaration
            if line.find("package") != -1:
                has_package = True
                package_name: str = line.split(" ")[1].strip().rstrip(";")    # get word after 'package' and remove semicolon
                new_package_dir: Path = new_src_dir / package_name

                # if its already been created, just add file to it
                if package_name in packages:
                    try:
                        file.move_into(new_package_dir)
                    except OSError as e:
                        print(f"error moving {file} to {new_package_dir}. Error code: {e.errno}, {e.strerror}")

                else:
                    packages.append(package_name)

                    # create package in src
                    try:
                        new_package_dir.mkdir()
                    except OSError as e:
                        print(f"error creating package {new_package_dir}. Error code: {e.errno}, {e.strerror}")

                    # move .java file to its respective package
                    try:
                        file.move_into(new_package_dir)
                    except OSError as e:
                        print(f"error moving {file} to {new_package_dir}. Error code: {e.errno}, {e.strerror}")

        # had no package declaration
        if not has_package:
            try:
                file.move_into(new_src_dir)
            except OSError as e:
                print(f"error moving {file} to {new_src_dir}. Error code: {e.errno}, {e.strerror}")

    return new_src_dir


def main() -> None:
    # --------------------------------------
    # set user-specific globals
    # --------------------------------------
    env_vars: dict[str, str | None] = dotenv_values('.env')

    # path of .csv file that contains student GitHub usernames
    # expected format: student, username
    usernames: Path = Path(env_vars.get("USERNAMES"))

    # path to destination for storing repos
    target_dir: Path = Path(env_vars.get("TARGET_DIR"))

    # path to basic .project file
    default_project_file: Path = Path(env_vars.get("PROJECT_FILE"))

    # path to basic .classpath file
    default_classpath_file: Path = Path(env_vars.get("CLASSPATH_FILE"))

    root_url: str = env_vars.get("ROOT_URL")

    # --------------------------------------------
    # gather info for clones and project renaming
    # --------------------------------------------
    args: Namespace = get_args()

    asgn_deadline: str = args.ASGN_DEADLINE
    if asgn_deadline is not None:
        asgn_deadline: datetime = datetime.strptime(asgn_deadline, "%Y-%m-%d")    # appends 00:00:00 onto the date

    # TODO: implement adding TA test suites if provided
    # asgn_tests: Path = Path(args.ASGN_TESTS)

    base_url: str = build_base_url(args, root_url)
    names_usernames: list[tuple[str, str]] = get_names_usernames(usernames)

    # --------------------------------------------
    # begin cloning
    # --------------------------------------------
    total_clones: int = 0

    for name, username in names_usernames:
        print("\n")
        print("=" * 80)
        result_url: str = base_url.replace("[USERNAME]", username)

        repo_start_index: int = result_url.rfind('/') + 1            # start after base url
        repo_end_index: int = result_url.rfind('.')                  # go until .git
        repo_name: str = result_url[repo_start_index:repo_end_index]

        # clone student repo
        # -C option specifies directory to mimic operating in
        # use run() because want to manually check the return code
        status: CompletedProcess = sp.run(["git", "-C", target_dir, "clone", result_url])

        # clone was successful
        if status.returncode == 0:
            student_repo_local: Path = target_dir / repo_name

            if asgn_deadline is not None:
                # need to ensure we have the correct default branch name
                # stdout should be something like one of these:
                #   refs/remotes/origin/master
                #   refs/remotes/origin/main
                default_branch: str = sp.check_output(
                    ["git", "-C", student_repo_local, "symbolic-ref", "refs/remotes/origin/HEAD"],
                    text=True).strip().split("/")[-1]

                # get the last commit prior to deadline
                # key git command: rev-list
                # should have a commit hash if repo was created, even if no pushes by student
                commit_hash: str = sp.check_output(
                    ["git", "-C", student_repo_local, "rev-list", "-n", "1", f"--before={asgn_deadline}",
                     default_branch],
                    text=True).strip()

                print(f"\n\n***CHECKING OUT LAST COMMIT PRIOR TO {asgn_deadline}***\n\n")
                status: CompletedProcess = sp.run(["git", "-C", student_repo_local, "checkout", commit_hash])
                if status.returncode != 0:
                    print(f"checkout failed: {status.returncode}")

            print("\n\nPROJECT STRUCTURE LOGS: ")

            # define expected project contents
            project_file: Path = student_repo_local / ".project"            # should always be top-level
            classpath_file: Path = student_repo_local / ".classpath"        # should always be top-level
            src_dir: str | None = find_src_dir(student_repo_local)                  # function call because how checking if src is not top level

            # record project state
            project_state: dict[str, bool | str] = {
                "project file": project_file.exists(),
                "classpath file": classpath_file.exists(),
                "src directory": src_dir
            }

            # determine what is missing
            missing_content: list[str] = [item for item, present in project_state.items() if not present or ""]
            missing_statement: str = f"project is missing: {", ".join(missing_content)}"

            # TODO: try Python match case
            match project_state:
                # 1) .project, .classpath, src
                case { "project file": True, "classpath file": True, "src directory": n} if n:
                    if not is_valid_project_file(project_file):
                        inject_project_file(student_repo_local, default_project_file)
                    if not is_valid_classpath_file(classpath_file):
                        inject_classpath_file(student_repo_local, default_classpath_file, src_dir=n)

                # 2) .project, .classpath, no src
                case { "project file": True, "classpath file": True, "src directory": n} if n == "":
                    if not is_valid_project_file(project_file):
                        inject_project_file(student_repo_local, default_project_file)
                    if not is_valid_classpath_file(classpath_file):
                        inject_classpath_file(student_repo_local, default_classpath_file)
                        create_src_dir(student_repo_local)
                        break
                    if get_classpath_src(classpath_file) != "":
                        create_src_dir(student_repo_local, get_classpath_src(classpath_file))

                # 3) .project, .classpath, error searching for src
                case { "project file": True, "classpath file": True, "src directory": n} if n is None:
                    if not is_valid_project_file(project_file):
                        inject_project_file(student_repo_local, default_project_file)
                    if not is_valid_classpath_file(classpath_file):
                        inject_classpath_file(student_repo_local, default_classpath_file)

                # 4) .project, no .classpath, src
                case { "project file": True, "classpath file": False, "src directory": n } if n:
                    if not is_valid_project_file(project_file):
                        inject_project_file(student_repo_local, default_project_file)
                    inject_classpath_file(student_repo_local, default_classpath_file, src_dir=n)

                # 5) .project, no .classpath, no src
                case { "project file": True, "classpath file": False, "src directory": n } if n == "":
                    if not is_valid_project_file(project_file):
                        inject_project_file(student_repo_local, default_project_file)
                    inject_classpath_file(student_repo_local, default_classpath_file)
                    create_src_dir(student_repo_local)

                # 6) .project, no .classpath, error searching for src
                case { "project file": True, "classpath file": False, "src directory": n } if n is None:
                    if not is_valid_project_file(project_file):
                        inject_project_file(student_repo_local, default_project_file)
                    inject_classpath_file(student_repo_local, default_classpath_file)

                # 7) no .project, .classpath, src
                case { "project file": False, "classpath file": True, "src directory": n } if n:
                    inject_project_file(student_repo_local, default_project_file)
                    inject_classpath_file(classpath_file, default_classpath_file, src_dir=n)

                # 8) no .project

            # # missing some minimal requirements
            # if 0 < len(missing_content) < len(project_state):
            #     print(missing_statement)
            #     for item_name in project_state:
            #         # is missing
            #         if item_name in missing_content:
            #             if item_name == "project file":
            #                 inject_project_file(student_repo_local, default_project_file)
            #             elif item_name == "classpath file":
            #                 if src_dir is not None and src_dir != "":
            #                     inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)
            #                 else:
            #                     inject_classpath_file(student_repo_local, default_classpath_file)
            #                     create_src_dir(student_repo_local)
            #                     missing_content.remove("src directory")
            #             elif item_name == "src directory":
            #                 if is_valid_classpath_file(classpath_file) and get_classpath_src(classpath_file) != "":
            #                     curr_src_dir: str = get_classpath_src(classpath_file)
            #                     create_src_dir(student_repo_local, src_dir_path=curr_src_dir)
            #         # not missing, but still need to check if okay
            #         else:
            #             if item_name == "project file" and not is_valid_project_file(project_file):
            #                 inject_project_file(student_repo_local, default_project_file)
            #             elif item_name == "classpath file" and not is_valid_classpath_file(classpath_file):
            #                 if src_dir is not None and src_dir != "":
            #                     inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)
            #                 else:
            #                     inject_classpath_file(student_repo_local, default_classpath_file)
            #                     create_src_dir(student_repo_local)
            #                     missing_content.remove("src directory")
            #
            # # missing all minimum requirements
            # elif len(missing_content) == len(project_state):
            #     print(missing_statement)
            #     inject_project_file(student_repo_local, default_project_file)
            #     inject_classpath_file(student_repo_local, default_classpath_file)
            #     create_src_dir(student_repo_local)
            #
            # # okay project, but still need to look at .classpath and .project
            # elif len(missing_content) == 0:
            #     if not is_valid_project_file(project_file):
            #         inject_project_file(student_repo_local, default_project_file)
            #     if not is_valid_classpath_file(classpath_file):
            #         if src_dir is not None and src_dir != "":
            #             inject_classpath_file(student_repo_local, default_classpath_file, src_dir=src_dir)
            #         else:
            #             inject_classpath_file(student_repo_local, default_classpath_file)
            #             create_src_dir(student_repo_local)

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
