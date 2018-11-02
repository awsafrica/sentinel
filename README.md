# Brixcoin Sentinel

An all-powerful toolset for BRIXCOIN.


Sentinel is an autonomous agent for persisting, processing and automating Brixcoin governance objects and tasks.

Sentinel is implemented as a Python application that binds to a local version 12 brixcoind instance on each Brixcoin Masternode.

This guide covers installing Sentinel onto an existing Masternode in Ubuntu 16.04.

## Installation

### 1. Install Prerequisites

Make sure Python version 2.7.x or above is installed:

    python --version

Update system packages and ensure virtualenv is installed:

    $ sudo apt-get update
    $ sudo apt-get -y install python-virtualenv

Make sure the local Brixcoin daemon running is at least version 0.12.3

    $ brixcoin-cli getinfo | grep version

### 2. Install Sentinel

Clone the Sentinel repo and install Python dependencies.

    $ cd .brixcoincore
    $ git clone https://github.com/awsafrica/sentinel.git && cd sentinel
    $ virtualenv ./venv
    $ ./venv/bin/pip install -r requirements.txt

### 3. Set up Cron

Set up a crontab entry to call Sentinel every minute:

    $ crontab -e

In the crontab editor, add the lines below, replacing '/home/YOURUSERNAME/sentinel' to the path where you cloned sentinel to:

    * * * * * cd /home/YOURUSERNAME/sentinel && ./venv/bin/python bin/sentinel.py >/dev/null 2>&1

## Configuration

An alternative (non-default) path to the `brixcoin.conf` file can be specified in `sentinel.conf`:

    brixcoin_conf=/path/to/brixcoin.conf

## Troubleshooting

To view debug output, set the `SENTINEL_DEBUG` environment variable to anything non-zero, then run the script manually:

    $ SENTINEL_DEBUG=1 ./venv/bin/python bin/sentinel.py

