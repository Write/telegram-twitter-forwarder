import logging

import telegram
import tweepy
from pytz import timezone, utc
from telegram import Bot
from telegram.error import TelegramError

from models import TelegramChat, TwitterUser
from util import escape_markdown, prepare_tweet_text, sanitize_url

from inspect import getmembers
from pprint import pprint
import re


class TwitterForwarderBot(Bot):

    def __init__(self, token, tweepy_api_object, update_offset=0):
        super().__init__(token=token)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing")
        self.update_offset = update_offset
        self.tw = tweepy_api_object

    def reply(self, update, text, *args, **kwargs):
        self.sendMessage(chat_id=update.message.chat.id, text=text, *args, **kwargs)

    def send_tweet(self, chat, tweet):
        try:
            self.logger.debug("("+ tweet.name +") - Sending tweet {} to chat {}...".format(tweet.tw_id, chat.chat_id))

            '''
            Use a soft-hyphen to put an invisible link to the first
            image in the tweet, which will then be displayed as preview
            Get first link to use as preview(photo_url) if tweet.photo_url isn't defined
            '''
            first_link = re.findall(r'(https?:\/\/[^\s]+)', tweet.text)
            photo_url = ''
            if tweet.photo_url:
                photo_url = '<a href="%s">\xad</a>' % tweet.photo_url
            elif first_link:
                if first_link[0]:
                    photo_url = '<a href="%s">\xad</a>' % sanitize_url(first_link[0])
                if len(first_link) > 1:
                    self.logger.debug("("+ tweet.name +") - 1st link found: " + sanitize_url(first_link[0]))
                    self.logger.debug("("+ tweet.name +") - 2nd link found: " + sanitize_url(first_link[1]))

            # Timezone not used right now.
            created_dt = utc.localize(tweet.created_at)
            if chat.timezone_name is not None:
                tz = timezone(chat.timezone_name)
                created_dt = created_dt.astimezone(tz)
            created_at = created_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

            # Change format based on chat_id. Hack used for personal use.
            if (chat.chat_id == -1001332809371 or chat.chat_id == -1001291532104 or chat.chat_id == -1001153548625):
                tweet_format_text = """
{link_preview}{text}
— <b><a href='https://twitter.com/{screen_name}/status/{tw_id}'>Ouvrir le Tweet</a></b>
"""
            # 'Normal format' :
            else:
                tweet_format_text = """
{link_preview}<b>{name}</b> (<a href='https://twitter.com/{screen_name}'>@{screen_name}</a>) :
{text}
— <b><a href='https://twitter.com/{screen_name}/status/{tw_id}'>Ouvrir le Tweet</a></b>
"""

            self.sendMessage(
                chat_id=chat.chat_id,
                disable_web_page_preview=not photo_url,
                text=tweet_format_text.format(
                    link_preview=photo_url,
                    text=prepare_tweet_text(tweet.text),
                    name=tweet.name,
                    screen_name=tweet.screen_name,
                    created_at=created_at,
                    tw_id=tweet.tw_id,
                ),
                parse_mode=telegram.ParseMode.HTML
            )

        except TelegramError as e:
            self.logger.info("Couldn't send tweet {} to chat {}: {}".format(
                tweet.tw_id, chat.chat_id, e.message
            ))

            delet_this = None

            if e.message == 'Bad Request: group chat was migrated to a supergroup chat':
                delet_this = True

            if e.message == "Unauthorized":
                delet_this = True

            if delet_this:
                self.logger.info("Marking chat for deletion")
                chat.delete_soon = True
                chat.save()

    def get_chat(self, tg_chat):
        db_chat, _created = TelegramChat.get_or_create(
            chat_id=tg_chat.id,
            tg_type=tg_chat.type,
        )
        return db_chat

    def get_tw_user(self, tw_username):
        try:
            tw_user = self.tw.get_user(tw_username)
        except tweepy.error.TweepError as err:
            self.logger.error(err)
            return None

        db_user, _created = TwitterUser.get_or_create(
            screen_name=tw_user.screen_name,
            defaults={
                'name': tw_user.name,
            },
        )

        if not _created:
            if db_user.name != tw_user.name:
                db_user.name = tw_user.name
                db_user.save()

        return db_user
