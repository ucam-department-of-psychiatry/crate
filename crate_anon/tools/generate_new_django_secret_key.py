#!/usr/bin/env python3
# tools/generate_new_django_secret_key.py

# See django.core.management.commands.startproject.Command.handle

from django.utils.crypto import get_random_string


def main():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    key = get_random_string(50, chars)
    print(key)


if __name__ == '__main__':
    main()
