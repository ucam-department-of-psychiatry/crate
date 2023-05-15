#!/bin/bash
# Run from .github/workflows/python-checks.yml
# Set up Redis for NLP Webserver tests

set -eux -o pipefail

sudo apt-get -y update
sudo apt-get -y install redis-server

sudo netstat -lnp | grep redis
