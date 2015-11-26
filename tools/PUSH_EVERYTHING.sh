#!/bin/bash
#
# Script to push to master repositories

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
cd $DIR/..
git push egret master
git push github master
git subtree push --prefix=pythonlib github-pythonlib-subtree master
