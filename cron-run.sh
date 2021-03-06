#!/bin/bash
if [ `pgrep -f telegram-twitter-forwarder-bot.py` ];
then
    echo "Already running"
    exit 1
else
    ./launch-program.sh 2>&1 | tee -a ./log/debug-$(date +%d-%B-%Y).log
    exit 0
fi
