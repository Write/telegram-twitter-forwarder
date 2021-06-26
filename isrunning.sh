#!/bin/bash
if [ `pgrep -f telegram-twitter-forwarder-bot.py` ];
then
    echo "Already running"
    exit 1
else
    echo "Not running"
    exit 0
fi
