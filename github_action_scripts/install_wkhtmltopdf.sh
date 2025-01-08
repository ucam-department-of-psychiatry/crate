#!/usr/bin/env bash

# Install wkhtmltopdf on headless ubuntu 18 vps
# https://gist.github.com/lobermann/ca0e7bb2558b3b08923c6ae2c37a26ce
# 429 = Too many requests. Unfortunately wget doesn't read the
# Retry-after header so just wait 5 minutes
wget --retry-on-http-error=429 --waitretry=300 --tries=20 https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bionic_amd64.deb
sudo apt-get -y install fontconfig gdebi libxrender1 xfonts-75dpi xfonts-base
sudo gdebi --non-interactive wkhtmltox_0.12.6-1.bionic_amd64.deb
