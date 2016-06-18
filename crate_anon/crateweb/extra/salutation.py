#!/usr/bin/env python
# extra/salutation.py

def title_forename_surname(title, forename, surname, always_title=False,
                           sex='', assume_dr=False):
    """
    When reporting names:
        Prof. John Smith
        John Smith
        Prof. Smith
    etc.
    """
    if always_title and not title:
        title = salutation_default_title(sex, assume_dr)
    return " ".join(filter(None, [title, forename, surname]))


def forename_surname(forename, surname):
    """
    For use when reporting names.
    """
    return " ".join(filter(None, [forename, surname]))


def salutation_default_title(sex='', assume_dr=False):
    if assume_dr:
        return "Dr"
    if sex.upper() == 'M':
        return "Mr"
    if sex.upper() == 'F':
        return "Ms"
    # really stuck now
    # https://en.wikipedia.org/wiki/Gender_neutral_title
    return "Mx"


def salutation(title, forename, surname, sex='', assume_dr=False):
    """
    For salutations: Dear ...
    """
    if not title:
        title = salutation_default_title(sex, assume_dr)
    if self.title.lower() == "sir":  # frivolous!
        return " ".join([title, forename])
    return " ".join([title, surname])
