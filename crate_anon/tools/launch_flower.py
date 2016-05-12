#!/usr/bin/env python

import subprocess

from crate_anon.crateweb.config.constants import CELERY_APP_NAME


def main():
    cmdargs = [
        "celery",
        "-A", CELERY_APP_NAME,
        "flower"
    ]
    print("Launching Flower: {}".format(cmdargs))
    subprocess.call(cmdargs)


if __name__ == '__main__':
    main()
