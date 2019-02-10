import argparse
import logging
from shutil import copyfile

from crate_anon.nlp_web.constants import SETTINGS
from crate_anon.nlp_web.security import hash_password

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Is file locking needed?

users_filename = SETTINGS['users_file']

with open(users_filename, 'r') as user_file:
    user_lines = user_file.readlines()
user_elements = [x.split(',') for x in user_lines]
USERS = {x[0]: x[1].strip() for x in user_elements}

def add_user(username: str, password: str) -> None:
    if username in USERS:
        proceed = input("User {} already exists. Overwrite "
                       "(change password)? [yes/no] ".format(username))
        if proceed.lower() == "yes":
            change_password(username, password)
            return
        else:
            return
    with open(users_filename, 'a') as user_file:
        user_file.write("{},{}\n".format(username,
                                  hash_password(password)))
    log.info("User {} added.".format(username))

def rm_user(username: str) -> None:
    user_found = False
    # Create a backup in case something goes wrong during writing
    backup_filename = users_filename + "~"
    copyfile(users_filename, backup_filename)
    try:
        with open(users_filename, 'w') as user_file:
            for user in USERS:
                if user != username:
                    user_file.write("{},{}\n".format(user, USERS[user]))
                else:
                    user_found = True
    except IOError:
        log.error("An error occured in opening the file {}. If the "
                  "integrity of this file is compromised, the backup is "
                  "{}.".format(users_filename, backup_filename))
        raise
    if user_found:
        log.info("User {} removed.".format(username))
    else:
        log.info("User {} not found.".format(username))

def change_password(username: str, password: str) -> None:
    user_found = False
    # Create a backup in case something goes wrong during writing
    backup_filename = users_filename + "~"
    copyfile(users_filename, backup_filename)
    try:
        with open(users_filename, 'w') as user_file:
            for user in USERS:
                if user != username:
                    user_file.write("{},{}\n".format(user, USERS[user]))
                else:
                    user_found = True
                    user_file.write("{},{}\n".format(username,
                                    hash_password(password)))
    except IOError:
        log.error("An error occured in opening the file {}. If the "
                  "integrity of this file is compromised, the backup is "
                  "{}.".format(users_filename, backup_filename))
        raise
    if user_found:
        log.info("Password changed for user {}.".format(username))
    else:
        log.info("User {} not found.".format(username))

def main() -> None:
    """
    Command-line entry point.
    """
    description = "Manage users for the CRATE nlp_web server."

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    arg_group = parser.add_mutually_exclusive_group()
    arg_group.add_argument("--adduser", nargs=2, metavar=("USERNAME", "PASSWORD"),
                        help="Add a user and associated password.")
    arg_group.add_argument("--rmuser", nargs=1, metavar="USERNAME",
                        help="Remove a user by specifying their username.")
    arg_group.add_argument("--changepw", nargs=2, metavar=("USERNAME", "PASSWORD"),
                        help="Change a user's password.")
    args = parser.parse_args()

    if not args.adduser and not args.rmuser and not args.changepw:
        log.error("One option required: '--aduser', '--rmuser' or '--changepw'.")
        return

    if args.rmuser:
        username = args.rmuser[0]
        proceed = input("Confirm remove user: {} ? [yes/no] ".format(
            username))
        if proceed.lower() == "yes":
            rm_user(username)
        else:
            log.info("User remove aborted.")
    elif args.adduser:
        username = args.adduser[0]
        password = args.adduser[1]
        add_user(username, password)
    elif args.changepw:
        username = changepw[0]
        new_password = changepw[1]
        proceed = input("Confirm change password for user: {} ? "
                        "[yes/no] ".format(username))
        if proceed.lower() == "yes":
            change_password(username, new_password)
        else:
            log.info("Password change aborted.")
