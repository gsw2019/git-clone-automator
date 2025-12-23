# git-clone-automator

Look how far we've come. What was once meant to be just a minor script to slightly speed up grading, has now grown into a decent project and learning experience. 

The initial goal was to automate the cloning of student repositories containing Eclipse projects to your local machine. Simple enough, given we had student GitHub usernames and the organization name. But of course, other issues arose, and with them, ideas of quality-of-life features.

---

## Features

### deadline (active*)
- specify a deadline date, indicating to checkout the most recent commit prior to that date

### .project wizard (passive*)
- ensures the .project file has minimal working requirements. If not, replaces with a basic template

### .classpath wizard (passive)
- ensures the .classpath has minimal working requirements. If not, replaces with a basic template

### src directory wizard (passive)
- checks if a src directory exists. If not, creates one and moves all .java files into it

### rename Eclipse project (passive)
- changes the project name to the students repo name, thus making them all unqiue and able to be imported into Eclipse simultaneously

### informative logs (passive)
- prints to the console information about each clone and any unsuitable Eclipse project structure



*active = user must toggle the feature on CL

*passive = feature is automatically applied

---

## Usage

Once this repository has been cloned and the .csv file of names, usernames has been populated, the program is ready to execute. 

**Note:** If any files from the repository were moved or renamed, make sure to update paths for the user-specific globals in the .py file.

Most recent commit:

`python3 git_clone_script.py project 1`

Last commit prior to Sept 9th, 2025 12:00 AM: 

`python3 git_clone_script.py project 1 -d 2025-09-09`

Last commit prior to Sept 21st, 2025 12:00 AM:

`python3 git_clone_script.py lab 2 --deadline 2025-09-21`

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

