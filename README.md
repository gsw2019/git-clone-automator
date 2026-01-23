# git-clone-automator

Look how far we've come. What was once meant to be just a minor script to slightly speed up grading, has now grown into a decent project and learning experience. 

The initial goal was to automate the cloning of student repositories containing Eclipse projects to a local machine. Simple enough, given we had student GitHub usernames and the organization name. But of course, other issues arose, and with them, ideas of quality-of-life features.

---

## Features

### deadline (active*)
- specify a deadline date, indicating to checkout the most recent commit prior to that date

### .project wizard (passive*)
- ensures the .project file has minimal working requirements. If not, replaces with a basic template

### .classpath wizard (passive)
- ensures the .classpath has minimal working requirements. If not, replaces with a basic template

### src directory wizard (passive)
- checks if a src directory exists. If not, creates one and moves all .java files into it respecting their packages.

### rename Eclipse project (passive)
- changes the project name to the students repo name, thus making them all unqiue and able to be imported into Eclipse simultaneously

### informative logs (passive)
- prints to the console information about each clone and any unsuitable Eclipse project structure

<p>
<small>*active = user must toggle the feature on CL</small>
</p>

<p>
<small>*passive = feature is automatically applied</small>
</p>

---

## Setup

1. **Clone repository and enter it**

       git clone https://github.com/gsw2019/git-clone-automator.git
       cd git-clone-automator

2. **Create Python virtual environment**

       python3 -m venv .venv

3. **Activate venv**

   - macOS/Linux:
   
         source .venv/bin/activate

   - Windows:

         .venv\Scripts\activate

4. **Install dependencies** (currently only 2):

       pip install -r requirements.txt

5. **Set environment variables**

    - create a .env file in root directory
    - use .env.example as a template

---

## Usage

### Invocation

`python3 git_clone_script.py [-h] [-num ASGN_NUM] [-name ASGN_NAME] [-d ASGN_DEADLINE] [-f ASGN_TESTS] ASGN_TYPE
`

### Examples

Most recent commit:

`python3 git_clone_script.py project -num 1`

Last commit prior to Sept 9th, 2025 12:00 AM: 

`python3 git_clone_script.py project -num 1 -d 2025-09-09`

last commit prior to Jan 27th, 2026 12:00 AM:

`python3 git_clone_script.py project -num 1 -name mastermind -d 2026-01-27`

last commit prior to Jan 24th, 2026 12:00 AM:

`python3 git_clone_script.py lab -num 1 -d 2026-01-24`

Last commit prior to Dec 9th, 2025 12:00AM:

`python3 git_clone_script.py BoardGames -d 2025-12-09`

---

## TODO

Check out Kanban Board under projects if interested. Should be public. 

---

## License

This project is licensed under the [MIT License](https://opensource.org/license/MIT).

See the [LICENSE](LICENSE) file for details.

---

## Author

Garret Wilson

[LinkedIn](https://www.linkedin.com/in/garretwilson-mcb-cs/) • [GitHub](https://github.com/gsw2019)

