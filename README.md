# telegram-twitter-forwarder

This projects aims to make a [Telegram](https://telegram.org) bot that forwards [Twitter](https://twitter.com/) updates to people, groups, channels (Working only partially require to manually change in the database since the bot doesn't answer to channels messages for now).

This project is a fork from [franciscod/telegram-twitter-forwarder-bot](https://github.com/franciscod/telegram-twitter-forwarder-bot)

## How do I run this?

**The code is targeting Python 3.8**

1. Clone this repo `git clone https://github.com/Write/telegram-twitter-forwarder.git`
2. Fill secrets.env (see next readme section)
3. Setup the python venv `./setup.sh`
5. Run it ! `./cron-run.sh` or `python main.py`

## Features added since Franciscod's version

- Blocklist support : Block tweets containing certain string (See [here](https://github.com/Write/telegram-twitter-forwarder/blob/master/job.py#L61) and [here](https://github.com/Write/telegram-twitter-forwarder/blob/master/job.py#L123))
- Skip tweet that are reply (See [here](https://github.com/Write/telegram-twitter-forwarder/blob/master/job.py#128))
- If tweet is a retweet, use full_text insead of truncated one (See [here](https://github.com/Write/telegram-twitter-forwarder/blob/master/job.py#132))
- Use html format instead of markdown for telegram sendMessage, change the format in [bot.py](https://github.com/Write/telegram-twitter-forwarder/blob/master/bot.py#L60)

## secrets.env ?

First, you'll need a Telegram Bot Token, you can get it via BotFather ([more info here](https://core.telegram.org/bots)).

Also, setting this up will need an Application-only authentication token from Twitter ([more info here](https://dev.twitter.com/oauth/application-only)). Optionally, you can provide a user access token and secret.

You can get this by creating a Twitter App [here](https://apps.twitter.com/).

Bear in mind that if you don't have added a mobile phone to your Twitter account you'll get this:

>You must add your mobile phone to your Twitter profile before creating an application. Please read https://support.twitter.com/articles/110250-adding-your-mobile-number-to-your-account-via-web for more information.

Get a consumer key, consumer secret, access token and access token secret (the latter two are optional), fill in your `secrets.env`, source it, and then run the bot!

## Setting up cronjob (Periodically check if bot is launched)

**Make sure crontab user have write access to venv directory**

1. Type `crontab -e` to edit your crontask file
2. Append this to your crontab file to check every minutes if the bot is running, if not it'll relaunch it.
`* * * * * cd /path/to/telegram-twitter-forwarder-bot && ./cron-run.sh >> /dev/null 2>&1`

## Credit

This is based on former work:
- [franciscod/telegram-twitter-forwarder-bot](https://github.com/franciscod/telegram-twitter-forwarder-bot)
- [python-telegram-bot](https://github.com/leandrotoledo/python-telegram-bot)

Tools used:
- [tweepy](https://github.com/tweepy/tweepy)
- [peewee](https://github.com/coleifer/peewee)
- [envparse](https://github.com/rconradharris/envparse)
- also, python, pip, the internets, and so on
