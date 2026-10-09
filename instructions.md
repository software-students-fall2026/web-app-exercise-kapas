# Web Application Exercise

A little exercise to build a web application following an agile process.

## Technology stack

We will use a Python-centric web application technology stack, consisting of:

- HTML & CSS for the front-end
- A Python back-end using [flask](https://flask.palletsprojects.com/en/2.2.x/)
- A MongoDB database connected to the Python back-end using [pymongo](https://pymongo.readthedocs.io/en/stable/)

Credentials for connecting to the database must be stored in a [.env](https://knowledge.kitchen/content/courses/software-engineering/slides/flask-pymongo/#combined) file.

- This file must not be included in version control, since it contains sensitive private data.
- Share this file among teammates (and admins/managers) using the team's messenger system.
- Use the [`dotenv`](https://pypi.org/project/python-dotenv/) or similar module to retrieve values from this file within code.
- Include an `env.example` file in the repository that shows the format of the `.env` file that should be created, but includes only dummy data instead of the real values for each environmental variable.

If your application requires user authentication, use the [`flask-login`](https://pypi.org/project/Flask-Login/) module, which makes it relatively simple to implement user accounts.

## Design

The design of this web application must be suitable for use on a mobile phone. The design need not be responsive and the design need not look great on a tablet or desktop/laptop computer.

You are not required to produce wireframes, design mockups, or a clickable prototype for this application. However, you are encouraged to do so if you wish.

The application must consist of at least 6 different screens.

- at least 2 of these must display data retrieved from the database.
- at least 1 of these must allow the user to add data to the database.
- at least 1 of these must allow the user to edit data in the database.
- at least 1 of these must allow the user to delete data from the database.
- at least 1 of these must allow the user to search for data in the database.

## Agile development

Teams must work following an "agile" methodology. While there are exist variety of ways teams often implement so-called agile development, in our case, this means specifically the following:

### Team communication channel

Teams must create a public channel in the course messaging app to use for team communication

- teams are expected to self-organize and create and join the channel themselves
- name the channel after your team, e.g. `team-7`.

### Product vision statement

Teams must write a product vision statement for their web application and place it in the `README.md` file. This should be one-sentence description of the project.

### User stories

To begin, teams must develop a set of user stories that define the product they are building.

- user stories should be written in the form "As a `[user type]`, I want `[some goal]` so that `[some reason]`."
- user stories should be created as Issues in the team's GitHub repository.

A link to the Issues page should be included in the `README.md` file.

### Document the steps necessary to run the software

The `README.md` file must include any steps that are necessary to clone, configure, and run the software. These steps must be exhaustive so that anyone who views the project on GitHub has all the information they might need to get the software running on their own local machine.

### Incremental work

The project will consist of two sprints, i.e. increments of work, each of which will last for one week.

- towards the end of the first sprint (but no later than 2 days after the completion of the first sprint), teams must have scheduled a meeting with a stakeholder (i.e. professor, tutor, or grader) to demo and solicit feedback on the work done so far.
- at the end of the second sprint, teams should be prepared to demo the project to a wider audience if requested.

### Task boards

- for each sprint, teams must maintain a "task board" where they track the progress of their user stories - see example screenshot below.
- task boards should be created as Projects in the team's GitHub repository - one for each sprint.
- prefix the name of each project with the team name or number, followed by the sprint number, e.g. "`Team 7 - Sprint 1`", "`Team 7 - Sprint 2`", etc.

A link to the Projects page should be included in the `README.md` file.

![simple task board](images/github-user-story-status-board.png)

### Daily standups

Teams must hold 3 or more "daily" standup meetings per week.

- these meetings must last no longer than 10 minutes
- during these meetings, each team member must answer three questions:
  - what have I done since last meeting?
  - what am I working on now?
  - what problems are blocking me for continuing?
- at the conclusion of each daily standup, one team member must create a single post in the team's channel in the course messaging app that documents each member's answers to each of these questions.
- any blocking problems must be immediately addressed by the team; if the team cannot solve it internally, it must be brought to the attention of the manager (i.e. the professor).

### GitHub repository

Team members are required to work from a single GitHub shared repository.

To create it, exactly one member of the team - decide among yourselves who - clicks the `Fork` button on this repository to make a copy of it in their own GitHub account. That member then gives the rest of the team access to it: in the new repository's `Settings` tab, under `Collaborators and teams`, add each teammate and the course admins by their GitHub usernames. Everyone else clones that one shared repository.

After cloning the team repository, every team member must run the setup script once from the repository's main directory, and again in any new clone:

```bash
python3 .automations/setup.py   # Mac/Linux
python .automations/setup.py    # Windows
```

Fix any problems it reports, then approve the hooks in each AI coding tool you have in this environment, as the script describes.

- all team members are expected to contribute to the main code of the project.
- each team member must be able to push and pull to and from the shared repository.
- each member's code and workflow contributions will be tracked, so team members must use their own accounts when making code changes.
- code changes must be done in branches in the team's own repository, not in the `main`/`master` branch and not in further forks or copies of it. Only the one team repository exists, and everyone works within it.
- when a code change is complete, the branch should be pushed to GitHub and a pull request should be created using GitHub's interface. Another team member must approve the pull request and merge it into the `main`/`master` branch if it is good code. All team members are expected to share the burden of reviewing and merging pull requests opened by teammates.
- because the team's repository is itself a fork of this one, GitHub will set the `base repository` of a new pull request to this repository rather than to your team's. Change it back to your own team's repository, and check that the branch beside it is your team's `main`/`master` branch. Otherwise you are asking the instructor to merge your work, and your teammates will not be able to review or merge it.

### Submitting

The project must be submitted by pushing to the team's GitHub repository. The `main`/`master` branch will be considered the final code. Share the web address of the team's repository using the messaging app specified by your instructor. Any `.env` files must be submitted to admins/managers via the team's messenger channel.

Teams do not need to deploy the application to a server. It must simply work when run locally. However, if an online deployment is desired, we recommend hosting it with [Digital Ocean](https://m.do.co/c/4d1066078eb0) (referral link with discount code).
