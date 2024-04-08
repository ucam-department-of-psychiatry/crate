#!/usr/bin/env python

"""
crate_anon/nlp_manager/write_gate_auto_install_xml.py

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

**Script to write a GATE automatic installation script.**

"""

import argparse

from rich_argparse import ArgumentDefaultsRichHelpFormatter

DEFAULT_FILENAME = "/tmp/gate_auto_install.xml"
DEFAULT_VERSION = "9.0.1"
DEFAULT_GATEDIR = "/crate/gate"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write a GATE automatic XML installation script",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    parser.add_argument(
        "--filename",
        default=DEFAULT_FILENAME,
        help="Output XML filename",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help="Gate version number",
    )
    parser.add_argument(
        "--gatedir",  # consistent with build_gate_java_interface.py
        default=DEFAULT_GATEDIR,
        help="Where to install GATE",
    )

    args = parser.parse_args()

    with open(args.filename, "w") as f:
        f.write(
            f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>

<!--
    {args.filename}

    Created by running the GATE installer manually, e.g. with

        java -jar gate-developer-{args.version}-installer.jar -console

    and then saying yes to "Generate an automatic installation script".
    Then editing that script.

    To use it, we do:

        java -jar myinstaller.jar <auto_install_file>

    The target directory does not need to exist in advance.
-->

<AutomatedInstallation langpack="eng">
    <com.izforge.izpack.panels.htmlinfo.HTMLInfoPanel id="HTMLInfoPanel_0"/>
    <com.izforge.izpack.panels.htmllicence.HTMLLicencePanel id="HTMLLicencePanel_1"/>
    <com.izforge.izpack.panels.target.TargetPanel id="TargetPanel_2">
        <!-- Edited: -->
        <installpath>{args.gatedir}</installpath>
    </com.izforge.izpack.panels.target.TargetPanel>
    <com.izforge.izpack.panels.packs.PacksPanel id="PacksPanel_3">
        <pack index="0" name="Core" selected="true"/>
        <pack index="1" name="User guide" selected="true"/>
        <pack index="2" name="Developer documentation" selected="false"/>
    </com.izforge.izpack.panels.packs.PacksPanel>
    <com.izforge.izpack.panels.install.InstallPanel id="InstallPanel_4"/>
    <com.izforge.izpack.panels.shortcut.ShortcutPanel id="ShortcutPanel_5">
        <createMenuShortcuts>false</createMenuShortcuts>
        <programGroup>GATE Developer {args.version}</programGroup>
        <createDesktopShortcuts>false</createDesktopShortcuts>
        <createStartupShortcuts>false</createStartupShortcuts>
        <shortcutType>user</shortcutType>
    </com.izforge.izpack.panels.shortcut.ShortcutPanel>
    <com.izforge.izpack.panels.finish.FinishPanel id="FinishPanel_6"/>
</AutomatedInstallation>
"""  # noqa: E501
        )


if __name__ == "__main__":
    main()
