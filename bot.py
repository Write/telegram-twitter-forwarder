import logging

import telegram
import tweepy
from pytz import timezone, utc
from telegram import Bot
from telegram.error import TelegramError

from models import TelegramChat, TwitterUser
from util import escape_markdown, prepare_tweet_text, prepare_tweet_text_reply, sanitize_url, remove_all_carriage, remove_tco, keep_one_carriage

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

    def send_tweet(self, chat, tweet, is_reply, tweet_replied_to):
        try:
            self.logger.debug("{} - Sending tweet {} to chat {}...".format(tweet.screen_name, tweet.tw_id, chat.chat_id))

            '''
            Use a soft-hyphen to put an invisible link to the first
            image in the tweet, which will then be displayed as preview
            Get first link to use as preview(photo_url) if tweet.photo_url isn't defined
            '''
            first_link = re.findall(r'(https?:\/\/[^\s]+)', tweet.text)
            photo_url = ''
            appendUrlToTweet = False

            if len(first_link) > 1:
                url1 = sanitize_url(first_link[0])
                url2 = sanitize_url(first_link[1])
                self.logger.debug("{} - 1st link found: {}".format(tweet.screen_name, url1))
                self.logger.debug("{} - 2nd link found: {}".format(tweet.screen_name, url2))
                if (re.match(r'((?:http|https):\/\/t\.(?:co)\/)', url1) and re.match(r'((?:http|https):\/\/t\.(?:co)\/)', url2)):
                    self.logger.debug("{} - Both link match t.co. Append 1st url to tweet.".format(tweet.screen_name))
                    appendUrlToTweet = True

            if tweet.photo_url:
                photo_url = '<a href="%s">\xad</a>' % tweet.photo_url
            elif first_link:
                if first_link[0]:
                    photo_url = '<a href="%s">\xad</a>' % sanitize_url(first_link[0])


            self.logger.debug("{} - Number of links found : {}".format(tweet.screen_name, len(first_link)))

            # Timezone not used right now.
            created_dt = utc.localize(tweet.created_at)
            if chat.timezone_name is not None:
                tz = timezone(chat.timezone_name)
                created_dt = created_dt.astimezone(tz)
            created_at = created_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

                                           #Mediavenir_LIVE #ITBR67         #afpfr           #Brevesdepresse  #LPLdirect
            chat_format_without_username = [-1001332809371, -1001291532104, -1001339948833 , -1001124396585,  -1001486365151,
                                               #mediavenir_france         #ActusFoot      #ConflitsFrance_fr  #ValeursActuelles_fr
                                               -1001284282476,            -1001296342105, -1001186206341,     -1001240509607,
                                               #dodo_live       #lemondefr_live   #LEXPRESS (lexpress_fr)    #Rue89
                                               -1001437451039,  -1001402437708  , -1001150749694           , -1001383628656,
                                               #arretsurimages          #LeHuffPost,          #MarianneLeMag   #StrasbourgActus
                                               -1001340251417,          -1001194650065,       -1001338188801,  -1001275431601]

                               #France24_en    #spectatorindex_live  #dodo_live
            chat_in_english = [-1001259662796, -1001405816725,       -1001437451039] 

            if (chat.chat_id in chat_in_english):
                str_opentweet = 'Open tweet'
                str_replyto   = 'Is a reply to this'
                str_from      = 'from'
            else:
                str_opentweet = 'Ouvrir le tweet'
                str_replyto   = 'En réponse à ce'
                str_from      = 'de'

            # Change format based on chat_id. Hack used for personal use.
            #if (chat.chat_id in chat_format_without_username):
            #    # Format without username
            #    tweet_format_before = "\n{link_preview}{text}"
            #else:
            #    # "Normal" format
            #    tweet_format_before = "\n{link_preview}<b>{name}</b> (<a href='https://twitter.com/{screen_name}'>@{screen_name}</a>)\n{text}"

            tweet_format = "\n{link_preview}{text}"
            tweet_format_open_tweetonly = "\n— <b><a href='https://twitter.com/{screen_name}/status/{tw_id}'>"+ str_opentweet +"</a></b>"

            if (-1001150749694 == chat.chat_id):
                tweet.text = remove_all_carriage(tweet.text)
                self.logger.debug("{} - Traitement 0".format(tweet.screen_name))
                urls = re.findall(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', tweet.text)
                if len(urls) > 0:

                    url = sanitize_url(urls[0]);
                    self.logger.debug("{} - URLs list : {}".format(tweet.screen_name, urls))
                    self.logger.debug("{} - URL selected : {}".format(tweet.screen_name, url))

                    # Remove all URLs
                    text_only = re.sub(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', '', tweet.text)
                    # Remove trailing carriage
                    text_only = re.sub(r'\n+$', '', text_only)

                    self.logger.debug("{} - text_only : {}".format(tweet.screen_name, text_only))

                    tweet.text = text_only + "\n— <a href='"+url+"'><b>Lire l'article</b></a> | <b><a href='https://twitter.com/{screen_name}/status/{tw_id}'>{str_opentweet}</a></b>".format(tw_id=tweet.tw_id, screen_name=tweet.screen_name, str_opentweet=str_opentweet)

                    # Remove remaining hashtags after replacement.
                    tweet.text = re.sub(r'(article<\/b><\/a>)(.*\#.*)', r'\1', tweet.text)
                    tweet.text = re.sub(r'⤵️|👇|➡️|👉', '', tweet.text)
                else:
                    # No URLS. Append tweet link.
                    tweet_format = tweet_format + tweet_format_open_tweetonly

                if (is_reply):
                    tweet_replied_to.text = remove_all_carriage(tweet_replied_to.text)
            else:
                # Generic replacement
                tweet.text = re.sub(r'🇲🇫', '🇫🇷', tweet.text)
                tweet.text = re.sub(r'🇨🇵', '🇫🇷', tweet.text)
                tweet.text = re.sub(r'🇪🇦', '🇪🇸', tweet.text)
                tweet.text = re.sub(r'🇺🇲', '🇺🇸', tweet.text)
                tweet.text = remove_tco(tweet.text)

            # Remove all cariage
            if ("arretsurimages" in tweet.screen_name or "F_Desouche" in tweet.screen_name or "LeHuffPost" in tweet.screen_name or "MarianneleMag" in tweet.screen_name or "LPLdirect" in tweet.screen_name or -1001275431601 == chat.chat_id or "Rue89" in tweet.screen_name or "Brevesdepresse" in tweet.screen_name or "lemondefr" in tweet.screen_name or "afpfr" in tweet.screen_name):
                tweet.text = remove_all_carriage(tweet.text)
                self.logger.debug("{} - Traitement 1".format(tweet.screen_name))
                urls = re.findall(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', tweet.text)
                if len(urls) > 0:

                    url = sanitize_url(urls[0]);
                    self.logger.debug("{} - URLs list : {}".format(tweet.screen_name, urls))
                    self.logger.debug("{} - URL selected : {}".format(tweet.screen_name, url))

                    tweet.text = re.sub(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', r"\n— <a href='"+url+"'><b>Lire l'article</b></a> | <b><a href='https://twitter.com/{screen_name}/status/{tw_id}'>{str_opentweet}</a></b>".format(tw_id=tweet.tw_id, screen_name=tweet.screen_name, str_opentweet=str_opentweet), tweet.text)

                    # Remove tiret (-) pour f_desouche at the end of the str
                    tweet.text = re.sub(r'(-\n— Lire)', r'\0', tweet.text)

                    # Remove remaining hashtags after replacement.
                    tweet.text = re.sub(r'(article<\/b><\/a>)(.*\#.*)', r'\1', tweet.text)
                    self.logger.debug("{} - After removing hashtags : {}".format(tweet.screen_name, tweet.text))

                    # Remove "#Strasbourg" from text
                    tweet.text = re.sub(r'\#Strasbourg', 'Strasbourg', tweet.text)
                    tweet.text = re.sub(r'via @LObs', '', tweet.text)

                    tweet.text = re.sub(r'⤵️|👇|➡️|⬇️|👉', '', tweet.text)
                    self.logger.debug("{} - link replaced : {}".format(tweet.screen_name, tweet.text))
                else:
                    # No URLS. Append tweet link.
                    tweet_format = tweet_format + tweet_format_open_tweetonly

                if (is_reply):
                    tweet_replied_to.text = remove_all_carriage(tweet_replied_to.text)

            # Keep one carriage
            if ("ActuFoot_" in tweet.screen_name or "Tanziloic" in tweet.screen_name or "Valeurs" in tweet.screen_name or "Mediavenir" in tweet.screen_name or "dodo" in tweet.screen_name or "ITA6778" in tweet.screen_name):
                
                self.logger.debug("{} - Traitement 2".format(tweet.screen_name))
                # Keep only 1 carriage return
                tweet.text = re.sub(r'(((?:|\s)(?:\n{1,}|\r{1,}|\r\n{1,})(?:|\s)))', '\n', tweet.text)

                # Remove url
                text_only = re.sub(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', '', tweet.text)
                # Remove trailing carriage
                text_only = re.sub(r'\n+$', '', text_only)

                self.logger.debug("{} - text_only : {}".format(tweet.screen_name, text_only))

                # Capture url from original tweet and combine text_only + urls
                urls = re.findall(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', tweet.text)
                if len(urls) > 0:
                    url = sanitize_url(urls[0])
                    tweet.text = text_only + "\n— <a href='"+url+"'><b>Lire l'article</b></a> | <b><a href='https://twitter.com/{screen_name}/status/{tw_id}'>{str_opentweet}</a></b>".format(tw_id=tweet.tw_id, screen_name=tweet.screen_name, str_opentweet=str_opentweet)
                else:
                    tweet.text = text_only
                    # No URLS. Append tweet link.
                    tweet_format = tweet_format + tweet_format_open_tweetonly

                # Remove remaining hashtags after replacement.
                tweet.text = re.sub(r'(article<\/b><\/a>)(.*\#.*)', r'\1', tweet.text)
                self.logger.debug("{} - After removing hashtags : {}".format(tweet.screen_name, tweet.text))

                tweet.text = re.sub(r'⤵️|👇|➡️|⬇️', '', tweet.text)
                self.logger.debug("{} - link deleted : {}".format(tweet.screen_name, tweet.text))
                if (is_reply):
                    tweet_replied_to.text = re.sub(r'(((?:|\s)(?:\n{1,}|\r{1,}|\r\n{1,})(?:|\s)))', '\n', tweet_replied_to.text)

            # Append url to tweet if two links are to t.co and keep only 1st link
            if (appendUrlToTweet):
                self.logger.debug("{} - appendUrlToTweet true".format(tweet.screen_name))
                tweet.text = tweet.text + " " + url1

            # Remove any url from reply
            if (is_reply):
                tweet_replied_to.text = remove_tco(tweet_replied_to.text)
                tweet_replied_to.text = re.sub(r'(?:📎|📎 | |- |)(https?:\/\/[^\s]+)', '', tweet_replied_to.text)

            # Debug photo_url
            self.logger.debug("{} - photo_url value : {}".format(tweet.screen_name, photo_url))

            # IF is_REPLY and FILTER_FROM_REPLY
            if (is_reply and "Brevesdepresse" not in tweet.screen_name and "F_Desouche" not in tweet.screen_name and "Valeurs" not in tweet.screen_name and "ActuFoot_" not in tweet.screen_name and chat.chat_id != -1001339948833): #afpfr
                tweet_format_text = tweet_format + "\n\n<i>"+ str_replyto +" <a href='https://twitter.com/{screen_name_replied_to}/status/{tw_id_replied_to}'>tweet</a> : </i>\n<pre>{text_replied_to}</pre>\n"""
                formatted_tweet = tweet_format_text.format(
                            link_preview=photo_url,
                            text=prepare_tweet_text(tweet.text),
                            name=tweet.name,
                            screen_name=tweet.screen_name,
                            created_at=created_at,
                            tw_id=tweet.tw_id,
                            text_replied_to=prepare_tweet_text_reply(tweet_replied_to.text),
                            name_replied_to=tweet_replied_to.name,
                            screen_name_replied_to=tweet_replied_to.screen_name,
                            tw_id_replied_to=tweet_replied_to.tw_id,
                        )
            else:
                formatted_tweet = tweet_format.format(
                            link_preview=photo_url,
                            text=prepare_tweet_text(tweet.text),
                            name=tweet.name,
                            screen_name=tweet.screen_name,
                            created_at=created_at,
                            tw_id=tweet.tw_id,
                        )

            self.sendMessage(
                chat_id=chat.chat_id,
                disable_web_page_preview=not photo_url,
                text=formatted_tweet,
                parse_mode=telegram.ParseMode.HTML
            )

        except TelegramError as e:
            self.logger.info("{} - Couldn't send tweet {} to chat {}: {}".format(
                tweet.name, tweet.tw_id, chat.chat_id, e.message
            ))

            delet_this = None

            if 'parse entities' in e.message.lower():
                self.logger.debug("{} - Parse entities problem: {}".format(tweet.screen_name, formatted_tweet))

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
