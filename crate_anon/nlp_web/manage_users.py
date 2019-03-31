#!/usr/bin/env python

r"""
crate_anon/nlp_web/manage_users.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

Manages the user authentication file for CRATE's implementation of an NLPRP
server.

"""

import argparse
import logging
from shutil import copyfile
from typing import Dict

from crate_anon.nlp_web.constants import SETTINGS
from crate_anon.nlp_web.security import hash_password

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

USERS_FILENAME = SETTINGS['users_file']


def get_users() -> Dict[str, str]:
    """
    Reads the user file and returns a dictionary mapping usernames to hashed
    passwords.
    """
    with open(USERS_FILENAME, 'r') as user_file:
        user_lines = user_file.readlines()
    user_elements = [x.split(',') for x in user_lines]
    users = {x[0]: x[1].strip() for x in user_elements}
    return users


def add_user(username: str, password: str) -> None:
    """
    Adds a username/password combination to the users file, hashing the
    password en route.
    """
    users = get_users()
    if username in users:
        proceed = input(f"User {username} already exists. "
                        f"Overwrite (change password)? [yes/no] ")
        if proceed.lower() == "yes":
            change_password(username, password)
            return
        else:
            return
    with open(USERS_FILENAME, 'a') as user_file:
        user_file.write(f"{username},{hash_password(password)}\n")
    log.info(f"User {username} added.")


def rm_user(username: str) -> None:
    """
    Removes a user from the user file.
    """
    user_found = False
    # Create a backup in case something goes wrong during writing
    backup_filename = USERS_FILENAME + "~"
    copyfile(USERS_FILENAME, backup_filename)
    users = get_users()
    try:
        with open(USERS_FILENAME, 'w') as user_file:
            for user in users:
                if user != username:
                    user_file.write(f"{user},{users[user]}\n")
                else:
                    user_found = True
    except IOError:
        log.error(
            f"An error occured in opening the file {USERS_FILENAME}. If the "
            f"integrity of this file is compromised, the backup is "
            f"{backup_filename}.")
        raise
    if user_found:
        log.info(f"User {username} removed.")
    else:
        log.info(f"User {username} not found.")


def change_password(username: str, password: str) -> None:
    """
    Changes a user's password by rewriting the user file.
    """
    user_found = False
    # Create a backup in case something goes wrong during writing
    backup_filename = USERS_FILENAME + "~"
    copyfile(USERS_FILENAME, backup_filename)
    users = get_users()
    try:
        with open(USERS_FILENAME, 'w') as user_file:
            for user in users:
                if user != username:
                    user_file.write(f"{user},{users[user]}\n")
                else:
                    user_found = True
                    user_file.write(f"{username},{hash_password(password)}\n")
    except IOError:
        log.error(
            f"An error occured in opening the file {USERS_FILENAME}. If the "
            f"integrity of this file is compromised, the backup is "
            f"{backup_filename}.")
        raise
    if user_found:
        log.info(f"Password changed for user {username}.")
    else:
        log.info(f"User {username} not found.")


def main() -> None:
    """
    Command-line entry point.
    """
    description = "Manage users for the CRATE nlp_web server."

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    arg_group = parser.add_mutually_exclusive_group()
    arg_group.add_argument(
        "--adduser", nargs=2, metavar=("USERNAME", "PASSWORD"),
        help="Add a user and associated password.")
    arg_group.add_argument(
        "--rmuser", nargs=1, metavar="USERNAME",
        help="Remove a user by specifying their username.")
    arg_group.add_argument(
        "--changepw", nargs=2, metavar=("USERNAME", "PASSWORD"),
        help="Change a user's password.")
    args = parser.parse_args()

    if not args.adduser and not args.rmuser and not args.changepw:
        log.error(
            "One option required: '--aduser', '--rmuser' or '--changepw'.")
        return

    if args.rmuser:
        username = args.rmuser[0]
        proceed = input(f"Confirm remove user: {username} ? [yes/no] ")
        if proceed.lower() == "yes":
            rm_user(username)
        else:
            log.info("User remove aborted.")
    elif args.adduser:
        username = args.adduser[0]
        password = args.adduser[1]
        add_user(username, password)
    elif args.changepw:
        username = args.changepw[0]
        new_password = args.changepw[1]
        proceed = input(
            f"Confirm change password for user: {username} ? [yes/no] ")
        if proceed.lower() == "yes":
            change_password(username, new_password)
        else:
            log.info("Password change aborted.")
