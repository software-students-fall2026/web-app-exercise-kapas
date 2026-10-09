The files in this directory contain a git hook that will ensure you only write single-line commit messages.
A single-line message may be followed by trailers such as "Co-Authored-By: Name <email>", which AI coding tools add.

The hook is activated by the setup script that the project instructions require every team member to run after cloning. To run it, from the main repository directory command shell:
    python3 .automations/setup.py # Mac/Linux
    python .automations/setup.py # Windows

The setup script also checks your git name and email, and explains how to approve the hooks your instructor uses to track AI coding agents in this repository.
