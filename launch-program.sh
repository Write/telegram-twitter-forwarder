#!/bin/bash
. venv/bin/activate
. secrets.env
echo -e "|\n|\n|\n|\n|     ----------- Relancement ----------\n|\n|           $(date +%d-%B-%Y_%Hh-%Mm)\n|\n|" | tee -a ./log/debug-$(date +%d-%B-%Y).log
python telegram-twitter-forwarder-bot.py
