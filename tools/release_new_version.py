#!/usr/bin/env python

"""
tools/release_new_version.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

"""

import argparse
from datetime import datetime
import logging
import os
from pathlib import Path
from subprocess import CalledProcessError, PIPE, run
import re
import sys
from typing import Iterable, List, Optional, Tuple

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from rich_argparse import ArgumentDefaultsRichHelpFormatter
from semantic_version import Version

from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

EXIT_FAILURE = 1

ROOT_TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.join(ROOT_TOOLS_DIR, "..")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")

REBUILD_DOCS = os.path.join(DOCS_DIR, "rebuild_docs.py")
DOCS_SOURCE_DIR = os.path.join(DOCS_DIR, "source")

CHANGELOG = os.path.join(DOCS_SOURCE_DIR, "changelog.rst")
NLP_HELP_FILE = os.path.join(DOCS_SOURCE_DIR, "nlp", "_crate_nlp_help.txt")
VERSION_FILE = os.path.join(PROJECT_ROOT, "crate_anon", "version.py")
DOCKER_ENV_FILE = os.path.join(PROJECT_ROOT, "docker", "dockerfiles", ".env")

log = logging.getLogger(__name__)


# https://stackoverflow.com/questions/1871549/determine-if-python-is-running-inside-virtualenv
def in_virtualenv() -> bool:
    """
    Are we running inside a Python virtual environment?
    """
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def valid_date(date_string: str) -> datetime.date:
    """
    Converts a string like "2020-12-31" to a date, or raises.
    """
    # https://stackoverflow.com/questions/25470844/specify-date-format-for-python-argparse-input-arguments  # noqa: E501
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        message = f"Not a valid date: '{date_string}'"
        raise argparse.ArgumentTypeError(message)


class MissingVersionException(Exception):
    pass


class VersionReleaser:
    docker_version_search = (
        # (               1               )( 2 )( 3)( 4 )( 5)( 6 )(7)"
        r"(^CRATE_DOCKER_IMAGE_TAG=crate:)(\d+)(\.)(\d+)(\.)(\d+)($)"
    )
    docker_version_replace = r"\g<1>{major}\g<3>{minor}\g<5>{patch}\g<7>"

    nlp_help_version_search = (
        r"(^NLP manager. Version )(\d+)(\.)(\d+)(\.)(\d+)"
    )

    def __init__(
        self,
        new_version: Version,
        release_date: datetime.date,
        update_versions: bool,
    ) -> None:
        self.new_version = new_version
        self._progress_version = None
        self.release_date = release_date
        self._released_versions = None
        self.update_versions = update_versions
        self.errors = []

    def run_with_check(self, args: List[str]) -> None:
        """
        Run a command with arguments. Raise :exc:`CalledProcessError` if the
        exit code was not zero.
        """
        run(args, check=True)

    @property
    def progress_version(self) -> Optional[Version]:
        """
        Return the version number in the changelog marked "IN PROGRESS", or
        ``None``.
        """
        if self._progress_version is None:
            regex = r"^\*\*(\d+)\.(\d+)\.(\d+), in progress\*\*$"
            with open(CHANGELOG, "r") as f:
                for line in f.readlines():
                    m = re.match(regex, line)
                    if m is not None:
                        self._progress_version = Version(
                            major=int(m.group(1)),
                            minor=int(m.group(2)),
                            patch=int(m.group(3)),
                        )

        return self._progress_version

    @property
    def released_versions(self) -> List[Tuple[Version, datetime]]:
        """
        Returns a list of ``(version, date_released)`` tuples from the
        changelog.
        """
        if self._released_versions is None:
            self._released_versions = self._get_released_versions()

        return self._released_versions

    def _get_released_versions(self) -> List[Tuple[Version, datetime]]:
        regex = r"^\*\*(\d+)\.(\d+)\.(\d+), (\d{4})-(\d{2})-(\d{2})\*\*$"

        released_versions = []

        with open(CHANGELOG, "r") as f:
            for line in f.readlines():
                m = re.match(regex, line)
                if m is not None:
                    released_version = Version(
                        major=int(m.group(1)),
                        minor=int(m.group(2)),
                        patch=int(m.group(3)),
                    )

                    date_string = f"{m.group(4)} {m.group(5)} {m.group(6)}"
                    try:
                        release_date = datetime.strptime(
                            date_string, "%Y %m %d"
                        ).date()
                    except ValueError:
                        raise ValueError(
                            f"Couldn't parse date when processing "
                            f"this line:\n{line}"
                        )

                    released_versions.append((released_version, release_date))

        return released_versions

    def check_quick_links(self) -> None:
        ref_regex = r"- :ref:`(\d{4}) <changelog_(\d{4})>`$"
        refs = []

        with open(CHANGELOG, "r") as f:
            for line in f.readlines():
                m = re.match(ref_regex, line)
                if m is not None:
                    refs.append((m.group(1), m.group(2)))

        release_year = str(self.release_date.year)
        if (release_year, release_year) not in refs:
            self.errors.append(f"No :ref: for {release_year} in changelog")

        target_regex = r"\.\. _changelog_(\d{4})\:$"
        year_regex = r"(\d{4})$"

        targets = []
        headings = []

        with open(CHANGELOG, "r") as f:
            year_heading = None
            for line in f.readlines():
                m = re.match(target_regex, line)
                if m is not None:
                    target_year = m.group(1)
                    if (target_year, target_year) not in refs:
                        self.errors.append(
                            f"No :ref: for year {target_year} in changelog"
                        )
                    targets.append((target_year, target_year))

                if year_heading is not None and line == "~~~~\n":
                    if (year_heading, year_heading) not in refs:
                        self.errors.append(
                            f"No :ref:  for year {year_heading} in "
                            "changelog"
                        )
                    if year_heading != target_year:
                        self.errors.append(
                            f"{year_heading} appeared after {target_year} in "
                            "changelog"
                        )
                    headings.append((year_heading, year_heading))

                m = re.match(year_regex, line)
                if m is not None:
                    year_heading = m.group(1)
                else:
                    year_heading = None

            if targets != refs or headings != refs:
                self.errors.append(":ref: years:")
                self.errors.append([r[0] for r in refs])
                self.errors.append("target years:")
                self.errors.append([t[0] for t in targets])

                self.errors.append("year headings:")
                self.errors.append([h[0] for h in headings])
                self.errors.append(
                    "Mismatch between :ref: years, target years "
                    "and year headings"
                )

    def check_version(self) -> None:
        if self.new_version == self.progress_version:
            self.errors.append(
                f"The desired version ({self.new_version}) "
                "matches the current IN PROGRESS version in the changelog. "
                "You probably want to mark the version in the changelog as "
                "released"
            )

        current_version = Version(CRATE_VERSION)
        if current_version == self.new_version:
            return

        if self.update_versions:
            return self.update_file(
                VERSION_FILE,
                r'^CRATE_VERSION = "(\d+)\.(\d+)\.(\d+)"',
                f'CRATE_VERSION = "{self.new_version}"',
            )

        self.errors.append(
            f"The current version ({current_version}) "
            "does not match the desired version "
            f"({self.new_version})"
        )

    def check_date(self) -> None:
        current_date = datetime.strptime(CRATE_VERSION_DATE, "%Y-%m-%d").date()
        if current_date == self.release_date:
            return

        if self.update_versions:
            new_date = self.release_date.strftime("%Y-%m-%d")

            return self.update_file(
                VERSION_FILE,
                r'^CRATE_VERSION_DATE = "(\d{4})-(\d{2})-(\d{2})"',
                f'CRATE_VERSION_DATE = "{new_date}"',
            )

        self.errors.append(
            "The release date in version.py "
            f"({current_date}) does not match the desired "
            f"release date ({self.release_date})"
        )

    def check_docker_version(self) -> None:
        current_docker_version = self.get_docker_version()
        if current_docker_version == self.new_version:
            return

        if self.update_versions:
            return self.update_file(
                DOCKER_ENV_FILE,
                self.docker_version_search,
                self.docker_version_replace.format(
                    major=self.new_version.major,
                    minor=self.new_version.minor,
                    patch=self.new_version.patch,
                ),
            )

        self.errors.append(
            f"The current docker version ({current_docker_version}) "
            "does not match the desired version "
            f"({self.new_version})"
        )

    def get_docker_version(self) -> Version:
        """
        Return the CRATE Docker image version
        """
        with open(DOCKER_ENV_FILE, "r") as f:
            for line in f.readlines():
                m = re.match(self.docker_version_search, line)
                if m is not None:
                    return Version(
                        major=int(m.group(2)),
                        minor=int(m.group(4)),
                        patch=int(m.group(6)),
                    )

        raise MissingVersionException(
            f"Could not find version in {DOCKER_ENV_FILE}"
        )

    def update_file(self, filename: str, search: str, replace: str) -> None:
        print(f"Updating {filename}...")
        with open(filename, "r") as f:
            content = f.read()
            new_content = re.sub(
                search, replace, content, count=1, flags=re.MULTILINE
            )

        with open(filename, "w") as f:
            f.write(new_content)

    def check_uncommitted_changes(self) -> None:
        # https://stackoverflow.com/questions/3878624/how-do-i-programmatically-determine-if-there-are-uncommitted-changes  # noqa: E501
        os.chdir(PROJECT_ROOT)
        run(["git", "update-index", "--refresh"])
        try:
            self.run_with_check(["git", "diff-index", "--quiet", "HEAD", "--"])
        except CalledProcessError:
            self.errors.append("There are uncommitted changes")

    def check_unpushed_changes(self) -> None:
        git_log = run(
            ["git", "log", "origin/master..HEAD"], stdout=PIPE
        ).stdout.decode("utf-8")
        if len(git_log) > 0:
            self.errors.append("There are unpushed or unmerged changes")

    def check_release_tag(self) -> None:
        release_tag = self.get_release_tag()

        tags = run(["git", "tag"], stdout=PIPE).stdout.decode("utf-8").split()

        if release_tag not in tags:
            self.errors.append(f"Could not find a git tag '{release_tag}'")

    def check_unpushed_tags(self) -> None:
        output = run(
            ["git", "push", "--tags", "--dry-run"], stderr=PIPE
        ).stderr.decode("utf-8")
        if "Everything up-to-date" not in output:
            self.errors.append("There are unpushed tags")

    def check_package_installed(self, package: str) -> None:
        try:
            self.run_with_check(["pip", "show", "--quiet", package])
        except CalledProcessError:
            self.errors.append(
                (
                    f"'{package}' is not installed. "
                    f"To release to PyPI: pip install {package}"
                )
            )

    def perform_checks(self) -> None:
        latest_version, latest_date = self.released_versions[-1]
        if self.progress_version is None:
            print(
                (
                    "No version is marked as IN PROGRESS in the changelog. "
                    "Normally that would be the next unreleased version"
                )
            )

        if latest_version != self.new_version:
            self.errors.append(
                f"The latest version in the changelog ({latest_version}) "
                f"does not match '{self.new_version}'"
            )

        if latest_date != self.release_date:
            self.errors.append(
                "The date of the latest version in the changelog "
                f"({latest_date}) does not match '{self.release_date}'"
            )

        self.check_quick_links()

        self.check_version()
        self.check_docker_version()
        self.check_date()

        if len(self.errors) == 0:
            self.check_docs()

        self.check_uncommitted_changes()
        self.check_unpushed_changes()
        self.check_release_tag()
        self.check_unpushed_tags()
        self.check_package_installed("wheel")
        self.check_package_installed("twine")

    def check_docs(self) -> None:
        # The GitHub docs workflow will do a more thorough check. This
        # will hopefully be enough.
        if self.get_nlp_help_file_version() != self.new_version:
            self.rebuild_docs()

    def get_nlp_help_file_version(self) -> Version:
        with open(NLP_HELP_FILE, "r") as f:
            for line in f.readlines():
                m = re.match(self.nlp_help_version_search, line)
                if m is not None:
                    return Version(
                        major=int(m.group(2)),
                        minor=int(m.group(4)),
                        patch=int(m.group(6)),
                    )

    def rebuild_docs(self) -> None:
        self.run_with_check([REBUILD_DOCS, "--warnings_as_errors"])

    def release(self) -> None:
        self.remove_old_pypi_builds()
        os.chdir(PROJECT_ROOT)

        # "bdist_wheel" removed from below to allow GitHub dependencies
        # Currenly fhirclient is on a fork
        self.run_with_check(["python", "setup.py", "sdist"])
        pypi_packages = [str(f) for f in self.get_pypi_builds()]
        print("Uploading to PyPI...")
        self.run_with_check(["twine", "upload"] + pypi_packages)

    def get_release_tag(self) -> str:
        return f"v{self.new_version}"

    def get_pypi_builds(self) -> Iterable[Path]:
        """
        Iterates through old PyPI upload files
        """
        return Path(DIST_DIR).glob("crate-anon-*")

    def remove_old_pypi_builds(self) -> None:
        """
        Deletes old PyPI upload files (e.g. ``crate-anon-*.tar.gz``).
        """
        for f in self.get_pypi_builds():
            f.unlink()


def main() -> None:
    """
    Do useful things to build and release CRATE.
    """
    if not in_virtualenv():
        log.error("release_new_version.py must be run inside virtualenv")
        sys.exit(EXIT_FAILURE)

    if sys.version_info < (3, 10):
        log.error("You must run this script with Python 3.10 or later")
        sys.exit(EXIT_FAILURE)

    parser = argparse.ArgumentParser(
        description="Release CRATE to various places",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    parser.add_argument(
        "--version",
        type=str,
        required=True,
        help="New version number (x.y.z)",
    )
    parser.add_argument(
        "--release-date",
        type=valid_date,
        default=datetime.now().date(),
        help="Release date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--update-versions",
        action="store_true",
        default=False,
        help="Update any incorrect version numbers",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        default=False,
        help="If all checks pass, build and release",
    )
    args = parser.parse_args()

    releaser = VersionReleaser(
        new_version=Version(args.version),
        release_date=args.release_date,
        update_versions=args.update_versions,
    )
    releaser.perform_checks()

    if len(releaser.errors) > 0:
        for error in releaser.errors:
            print(error)
        if not args.update_versions:
            # TODO: Don't display this message if the versions are already
            # updated
            print(
                "Run the script with --update-versions to automatically "
                "update version numbers"
            )
        sys.exit(EXIT_FAILURE)

    if args.release:
        # OK to proceed to the next step
        releaser.release()
        return

    print("All checks passed. You can run the script again with --release")


if __name__ == "__main__":
    main_only_quicksetup_rootlogger()
    main()
