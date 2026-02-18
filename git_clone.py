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

# non-standard lib packages
from dotenv import dotenv_values
from colorama import init, Fore, Style


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


def find_project_file(project_root: Path) -> tuple[Path | None, bool]:
    """Checks if the project has a .project file. Isn't required to be top-level

    Returns:
        (Path, True) - found
        (None, True) - not found
        (None, False) - error

    :param project_root: entry point to project
    :return: tuple that indicates the search status
    """
    try:
        for project_file in list(project_root.rglob(".project")):
            if project_file.is_file():
                return project_file, True

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to search repo for .project file. Error code: {e.errno}, {e.strerror}")
        return None, False

    return None, True


def find_classpath_file(project_root: Path) -> tuple[Path | None, bool]:
    """Checks if the project has a .classpath file. Isn't required to be top-level

    Returns:
        (Path, True) - found
        (None, True) - not found
        (None, False) - error

    :param project_root: entry point to project
    :return: tuple that indicates the search status
    """
    try:
        for classpath_file in list(project_root.rglob(".classpath")):
            if classpath_file.is_file():
                return classpath_file, True

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to search repo for .classpath file. Error code: {e.errno}, {e.strerror}")
        return None, False

    return None, True


def find_src_dir(project_root: Path) -> tuple[Path | None, bool]:
    """Checks if the project has a src folder. Isn't required to be top-level

    Returns:
        (Path, True) - found
        (None, True) - not found
        (None, False) - error

    :param project_root: entry point to project
    :return: tuple that indicates the search status
    """
    # search for first instance of src dir in student repo
    try:
        # rglob to recursively search for src dir
        for src_dir in list(project_root.rglob("src")):
            if src_dir.is_dir():
                # return relative here because if need to set in .classpath, don't want my local path
                return Path(src_dir.relative_to(project_root)), True

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to search repo for src dir. Error code: {e.errno}, {e.strerror}")
        return None, False

    return None, True


def find_java_file_folders(project_root: Path) -> set[Path] | None:
    """Finds all parent folders of java files

    :param project_root: entry point to project
    :return: a list of folders that contain java files
    """
    # should all be unique
    java_file_folders: set[Path] = set()

    try:
        for java_file in list(project_root.rglob("*.java")):
            if java_file.is_file():
                parent: Path = java_file.parent.relative_to(project_root)
                if parent.parts:
                    java_file_folders.add(Path(parent.parts[0]))    # parent folder isn't the root
                else:
                    java_file_folders.add(Path("."))    # parent folder is the root itself

        return java_file_folders

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to search repo for .java parent folders. Error code: {e.errno}, {e.strerror}")
        return None


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

            # local paths
            if type_of_entry == "lib":
                print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + 'bad .classpath file: classpathentry tag with attribute and value pair: kind="lib"')
                return False

            # bad JavaFX name or bad JRE pointer
            if type_of_entry == "con":
                path: str = tag.get("path")
                if "USER_LIBRARY" in path:
                    path_parts: list[str] = path.split('/')
                    if path_parts[1] != "JavaFX":
                        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + f"bad .classpath file: classpathentry tag with user library as {path_parts[1]}, not JavaFX")
                        return False
                elif "JRE_CONTAINER" in path:
                    path_parts: list[str] = path.split('/')
                    if len(path_parts) > 1:
                        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + f"bad .classpath file: classpathentry tag with JRE pointer to machine specific JDK")
                        return False

        return True

    except ET.ParseError as e:
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " +f"could not parse .classpath file. Error code: {e.code}, {e.msg.capitalize()}")
        return False


def is_valid_project_file(project_file: Path) -> bool:
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
            print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + "bad .project file: missing buildCommand tag")
            return False
        if root.find(".//nature") is None:
            print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + "bad .project file: missing nature tag")
            return False

        return True

    except ET.ParseError as e:
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + f"could not parse .project file. Error code: {e.code}, {e.msg.capitalize()}")
        return False


def inject_classpath_file(project_root: Path, default_classpath_file: Path, src_dir: Path = Path("src")) -> None:
    """Injects a basic .classpath file into student repo. the file is configured to look for local
    machines JRE, Junit5 library, and JavaFX user library

    :param project_root: entry point to project
    :param default_classpath_file: path to default .classpath file
    :param src_dir: the path from repo root of an existing src dir. Defaults to src if not passed
    :return: None
    """
    new_classpath_file: Path = project_root / ".classpath"
    try:
        default_classpath_file.copy(new_classpath_file)     # returns path to target
        print(Fore.RED + Style.BRIGHT + "[DEDUCTIBLE] " + "injecting a .classpath file into student repo")

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to inject .classpath file. Error code: {e.errno}, {e.strerror}")
        return

    if str(src_dir) != "src":
        set_classpath_src(new_classpath_file, src_dir)


def set_classpath_src(classpath_file: Path, src: Path) -> None:
    """Set the path to src files from .classpath file.

    :param classpath_file: .classpath file in student repo
    :param src: path from repo root to src files
    :return: None
    """
    try:
        tree: ET.ElementTree = ET.parse(classpath_file)
        root: ET.Element = tree.getroot()

        for tag in root.findall("classpathentry"):
            type_of_entry: str = tag.get("kind")

            if type_of_entry == "src":
                tag.set("path", str(src))
                print(Fore.RED + Style.BRIGHT + "[DEDUCTIBLE] " + f"set .classpath src path: {src}")
                tree.write(classpath_file, encoding="UTF-8", xml_declaration=True)
                return

        # didn't find any existing classpathentry with kind="src" so need to add one
        add_classpath_src(classpath_file, src)

    except ET.ParseError as e:
        # shouldn't ever reach here because already checked its parsable
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " +f"could not parse .classpath file. Error code: {e.code}, {e.msg.capitalize()}")


def add_classpath_src(classpath_file: Path, src: Path) -> None:
    """Add a new classpathentry tag with additional src path to .classpath file

    :param classpath_file: path to student repo .classpath file
    :param src: path from repo root to .java files
    :return: None
    """
    try:
        tree: ET.ElementTree = ET.parse(classpath_file)
        root: ET.Element = tree.getroot()

        new_src_path: ET.Element = ET.Element("classpathentry")
        new_src_path.set("kind", "src")
        new_src_path.set("path", str(src))
        root.append(new_src_path)

        tree.write(classpath_file, encoding="UTF-8", xml_declaration=True)
        print(Fore.RED + Style.BRIGHT + "[DEDUCTIBLE] " + f"added .classpath src path: {src}")

    except ET.ParseError as e:
        # shouldn't ever reach here because already checked its parsable
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " +f"could not parse .classpath file. Error code: {e.code}, {e.msg.capitalize()}")
        return None


def check_classpath_src_paths(project_root: Path, classpath_file: Path) -> None:
    """Ensures all folders that contain .java files are present in the .classpath file. If not,
    adds classpathentry tag to .classpath file

    :param project_root: local path to student repo
    :param classpath_file: .classpath file in student repo
    :return: None
    """
    java_file_folders: set[Path] = find_java_file_folders(project_root)
    current_src_folders: set[Path] = set()

    try:
        tree: ET.ElementTree = ET.parse(classpath_file)
        root: ET.Element = tree.getroot()

        for tag in root.findall("classpathentry"):
            type_of_entry: str = tag.get("kind")
            if type_of_entry == "src":
                current_src_folders.add(Path(tag.get("path")))

        if java_file_folders:
            for java_file_folder in java_file_folders:

                is_covered: bool = (
                    # already in .classpath
                    java_file_folder in current_src_folders or
                    # parent of java_file_folder covers it
                    java_file_folder.parent in current_src_folders or
                    # if src is "src" then "." is a parent thus looking covered. Avoid checking when java_file_folder is "."
                    # condition after `and` is checking if java_file_folder is included in a long src like src/controller/java
                    (java_file_folder != Path(".") and any(java_file_folder in src.parents for src in current_src_folders))
                )

                if not is_covered:
                    add_classpath_src(classpath_file, java_file_folder)
                    current_src_folders.add(java_file_folder)

    except ET.ParseError as e:
        # shouldn't ever reach here because already checked its parsable
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " +f"could not parse .classpath file. Error code: {e.code}, {e.msg.capitalize()}")


def get_classpath_src(classpath_file: Path) -> Path | None:
    """Get the path declared in .classpath that supposedly points to src files.

    :param classpath_file: .classpath file in student repo
    :return: path to src files found in .classpath
    """
    try:
        tree: ET.ElementTree = ET.parse(classpath_file)
        root: ET.Element = tree.getroot()

        for tag in root.findall("classpathentry"):
            type_of_entry: str = tag.get("kind")

            if type_of_entry == "src":
                path: str = tag.get("path")
                # want the actual src folder and not ones like test
                if "src" in path:
                    return Path(path)

        return Path("")

    except ET.ParseError as e:
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " +f"could not parse .classpath file. Error code: {e.code}, {e.msg.capitalize()}")
        return None


def inject_project_file(project_root: Path, default_project_file: Path) -> None:
    """Injects a basic .project file into student repo. Name tag is blank

    :param project_root: entry point to project
    :param default_project_file: path to default .project file
    :return: None
    """
    new_project_file: Path = project_root / ".project"
    try:
        default_project_file.copy(new_project_file)
        print(Fore.RED + Style.BRIGHT + "[DEDUCTIBLE] " + "injecting a .project file into student repo")

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to inject .project file. Error code: {e.errno}, {e.strerror}")


def create_src_dir(project_root: Path, src_dir_path: Path = Path("src")) -> Path | None:
    """Called after determining a src directory doesn't exist. Creates a src directory and subdirectories (packages) in
    students repo at the top level. if srd_dir_path is passed, will create src there.

    Function only returns None when fails to make src dir or fails to search for .java files

    :param project_root: entry point to project
    :param src_dir_path: expected path of src directory
    :return: path to new local src dir or None
    """
    # create a top level src dir in students repo
    if src_dir_path != Path("src"):
        new_src_dir: Path = project_root / src_dir_path
    else:
        new_src_dir: Path = project_root / "src"

    try:
        # creates parent directories if they don't exist
        new_src_dir.mkdir(parents=True, exist_ok=True)
        print(Fore.RED + Style.BRIGHT + "[DEDUCTIBLE] " + "created a src directory")

    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to create src directory. Error code: {e.errno}, {e.strerror}")
        return None

    # find all the .java files in the repo
    try:
        # rglob to recursively search for java files
        # must cast to list so is a snap shot of rglob()
        java_files: list[Path] = list(project_root.rglob("*.java"))
    except OSError as e:
        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to repo for .java files. Error code: {e.errno}, {e.strerror}")
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
                        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed moving {file} to {new_package_dir}. Error code: {e.errno}, {e.strerror}")

                else:
                    packages.append(package_name)

                    # create package in src
                    try:
                        new_package_dir.mkdir(exist_ok=True)
                    except OSError as e:
                        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to create package {new_package_dir}. Error code: {e.errno}, {e.strerror}")

                    # move .java file to its respective package
                    try:
                        file.move_into(new_package_dir)
                    except OSError as e:
                        print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to move {file} to {new_package_dir}. Error code: {e.errno}, {e.strerror}")

        # had no package declaration
        if not has_package:
            try:
                file.move_into(new_src_dir)
            except OSError as e:
                print(Fore.CYAN + Style.BRIGHT + "ERROR: " + f"failed to move {file} to {new_src_dir}. Error code: {e.errno}, {e.strerror}")

    return new_src_dir


def rename_project(project_file: Path, repo_name: str) -> None:
    """Renames the students Eclipse project to their repo name. Edits the .project file
    using XML parser package

    :param project_file: path to the .project file
    :param repo_name: name of the local repo
    :return: None
    """
    try:
        # use XML parsing and editing tool (.project is XML)
        # Only rename after checking project file. Don't need try-except for parsing here
        tree: ET.ElementTree = ET.parse(project_file)
        root: ET.Element = tree.getroot()
        # change <name> tag, first instance is project name
        name_tag: ET.Element[str] = root.find("name")
        name_tag.text = repo_name
        tree.write(project_file, encoding="UTF-8", xml_declaration=True)
        print(Fore.GREEN + Style.BRIGHT + "[OK] " + f"renamed project to {repo_name}")

    except ET.ParseError as e:
        print(Fore.YELLOW + Style.BRIGHT + "[WARNING] " + f"could not parse .project file. Error code: {e.code}, {e.msg.capitalize()}")


def main() -> None:
    # initialize colored logs
    init(autoreset=True)

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
        print("=" * 100)
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

                print(Fore.GREEN + Style.NORMAL + "\n\n===", end="")
                print(Fore.MAGENTA + Style.NORMAL + "> ", end="")
                print(Fore.BLUE + Style.BRIGHT + f"CHECKING OUT LAST COMMIT PRIOR TO {asgn_deadline}\n\n")

                status: CompletedProcess = sp.run(["git", "-C", student_repo_local, "checkout", commit_hash])
                if status.returncode != 0:
                    print(f"checkout failed: {status.returncode}")

            print(Fore.GREEN + Style.NORMAL + "\n\n===", end="")
            print(Fore.MAGENTA + Style.NORMAL + "> ", end="")
            print(Fore.BLUE + Style.BRIGHT + "PROJECT STRUCTURE LOGS:")

            # determine state of Eclipse project components
            project_file_state: tuple[Path | None, bool] = find_project_file(student_repo_local)
            classpath_file_state: tuple[Path | None, bool]  = find_classpath_file(student_repo_local)
            src_dir_state: tuple[Path | None, bool]  = find_src_dir(student_repo_local)

            project_file, project_file_search = project_file_state
            classpath_file, classpath_file_search = classpath_file_state
            src_dir, src_dir_search = src_dir_state

            # determine what is missing (None, True -> no path and search was successful)
            missing_content: list[str] = []
            if project_file is None and project_file_search is True:
                missing_content.append("project file")
            if classpath_file is None and classpath_file_search is True:
                missing_content.append("classpath file")
            if src_dir is None and src_dir_search is True:
                missing_content.append("src directory")

            missing_statement: str = Fore.YELLOW + Style.BRIGHT + "[WARNING] " + f"project is missing: {", ".join(missing_content)}"
            print(missing_statement) if len(missing_content) != 0 else None

            # .project file is independent of other components
            if project_file is not None and project_file_search == True:
                if not is_valid_project_file(project_file):
                    inject_project_file(student_repo_local, default_project_file)
                    # reset path after injection
                    project_file = find_project_file(student_repo_local)[0]
            elif project_file is None and project_file_search == True:
                inject_project_file(student_repo_local, default_project_file)
                project_file = find_project_file(student_repo_local)[0]

            # .project is considered the root of Eclipse projects
            project_root: Path = project_file.parent if project_file is not None else student_repo_local

            # if the project root is different from the repository root, re-search for src dir so its relative to the project
            if project_root != student_repo_local:
                src_dir_state = find_src_dir(project_root)
                src_dir, src_dir_search = src_dir_state

            # use match-case for src dir and .classpath entanglement
            match (classpath_file, classpath_file_search), (src_dir, src_dir_search):
                # 1) .classpath exists, src exists
                case (Path(), True), (Path(), True):
                    # print("case 1")
                    if not is_valid_classpath_file(classpath_file):
                        inject_classpath_file(project_root, default_classpath_file, src_dir=src_dir)
                        # reset path after injection
                        classpath_file = find_classpath_file(project_root)[0]
                    elif get_classpath_src(classpath_file) != src_dir:
                        set_classpath_src(classpath_file, src_dir)

                # 2) .classpath exists, src doesn't exists
                case (Path(), True), (None, True):
                    # print("case 2")
                    if not is_valid_classpath_file(classpath_file):
                        inject_classpath_file(project_root, default_classpath_file)
                        classpath_file = find_classpath_file(project_root)[0]
                        create_src_dir(project_root)
                    elif str(get_classpath_src(classpath_file)) != ".":
                        create_src_dir(project_root, get_classpath_src(classpath_file))

                # 3) .classpath exists, src search error
                case (Path(), True), (None, False):
                    # print("case 3")
                    if not is_valid_classpath_file(classpath_file):
                        inject_classpath_file(project_root, default_classpath_file)
                        classpath_file = find_classpath_file(project_root)[0]

                # 4) .classpath doesn't exist, src exist
                case (None, True), (Path(), True):
                    # print("case 4")
                    inject_classpath_file(project_root, default_classpath_file, src_dir=src_dir)
                    classpath_file = find_classpath_file(project_root)[0]

                # 5) .classpath doesn't exist, src search error
                case (None, True), (None, False):
                    # print("case 5")
                    inject_classpath_file(project_root, default_classpath_file)
                    classpath_file = find_classpath_file(project_root)[0]

                # 6) .classpath doesnt exist, src doesnt exist
                case (None, True), (None, True):
                    # print("case 6")
                    inject_classpath_file(project_root, default_classpath_file)
                    classpath_file = find_classpath_file(project_root)[0]
                    create_src_dir(project_root)

                # 7) .classpath search error, src state doesn't matter
                case (None, False), _:
                    # print("case 7")
                    pass

            # ensure all parent java folders are in the .classpath file
            check_classpath_src_paths(project_root, classpath_file)

            rename_project(project_file, repo_name)

            total_clones += 1

        else:
            print("\n")
            print(f"student name(s): {name}")
            print(f"student(s) GitHub username: {username}")

    print("\n\n" + "=" * 100)
    print(f"\n{total_clones} student repos were cloned into {target_dir}\n\n")


if __name__ == "__main__":
    main()
