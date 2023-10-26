#!/usr/bin/env bash

set -eux -o pipefail

# azure.archive.ubuntu.com is flaky
sudo sed -i 's/azure.archive.ubuntu.com/archive.ubuntu.com/' /etc/apt/sources.list
sudo apt-get update -o APT::Update::Error-Mode=any
