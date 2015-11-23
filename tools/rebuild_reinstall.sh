#!/bin/bash

# Exit on any error
set -e

THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
SOURCE_ROOT=`readlink -m "$THIS_SCRIPT_DIR/.."`
PACKAGE_DIR="$SOURCE_ROOT/built_packages"

PACKAGE=crate
VERSION_MAIN=$(head -n 1 "$SOURCE_ROOT/VERSION.txt")
VERSION_DEB="${VERSION_MAIN}-1"
DEB_PACKAGE_FILE=$PACKAGE_DIR/${PACKAGE}_${VERSION_DEB}_all.deb

sudo apt-get --yes remove $PACKAGE
$THIS_SCRIPT_DIR/make_package.sh
sudo gdebi --non-interactive $DEB_PACKAGE_FILE
