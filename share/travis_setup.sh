#!/bin/bash
set -evx

mkdir ~/.brixcoincore

# safety check
if [ ! -f ~/.brixcoincore/.dash.conf ]; then
  cp share/brixcoin.conf.example ~/.brixcoincore/brixcoin.conf
fi
