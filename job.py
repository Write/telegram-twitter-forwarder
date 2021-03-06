import html
import logging
import math
import re
from datetime import datetime
from threading import Event

import tweepy
from telegram.error import TelegramError
from telegram.ext import Job

from inspect import getmembers
from pprint import pprint

from models import TwitterUser, Tweet, Subscription, db, TelegramChat

import sys
import requests

INFO_CLEANUP = {
    'NOTFOUND': "Your subscription to @{} was removed because that profile doesn't exist anymore. Maybe the account's name changed?",
    'PROTECTED': "Your subscription to @{} was removed because that profile is protected and can't be fetched.",
}

class FetchAndSendTweetsJob(Job):


    # List of Strings blocklist.
    # Tweets containing one of those strings will be skipped.
    blocklist = [
        "circulation normale",
        "je suis avec vous",
        "nous sommes avec vous",
        "avec vous cet après-midi",
        "pour rester au courant de l'actualité sur tous",
        "photo du jour est disponible",
        "SONDAGE |",
        "Betclic",
        "La Plume Libre recrute",
        "tousuncotefoot",
        "freebets"
    ]

    # Twitter API rate limit parameters
    LIMIT_WINDOW = 15 * 60
    LIMIT_COUNT = 300
    MIN_INTERVAL = 60
    TWEET_BATCH_INSERT_COUNT = 100

    @property
    def interval(self):
        tw_count = (TwitterUser.select()
                    .join(Subscription)
                    .group_by(TwitterUser)
                    .count())
        if tw_count >= self.LIMIT_COUNT:
            return self.LIMIT_WINDOW
        res = math.ceil(tw_count * self.LIMIT_WINDOW / self.LIMIT_COUNT)
        return max(self.MIN_INTERVAL, res)

    def __init__(self, context=None):
        self.repeat = True
        self.context = context
        self.name = self.__class__.__name__
        self._remove = Event()
        self._enabled = Event()
        self._enabled.set()
        self.logger = logging.getLogger(self.name)

    def run(self, bot):

        self.logger.debug("Fetching tweets...")
        tweet_rows = []
        # fetch the tw users' tweets
        tw_users = list((TwitterUser.select()
                         .join(Subscription)
                         .group_by(TwitterUser)
                         .order_by(TwitterUser.last_fetched)))
        updated_tw_users = []
        users_to_cleanup = []

        for tw_user in tw_users:
            try:
                if tw_user.last_tweet_id == 0:
                    # get just the latest tweet
                    self.logger.debug(
                        "Fetching latest tweet by {}".format(tw_user.screen_name))
                    tweets = bot.tw.user_timeline(
                        screen_name=tw_user.screen_name,
                        count=1,
                        tweet_mode='extended')
                else:
                    # get the fresh tweets
                    self.logger.debug(
                        "Fetching new tweets from {}".format(tw_user.screen_name))
                    tweets = bot.tw.user_timeline(
                        screen_name=tw_user.screen_name,
                        since_id=tw_user.last_tweet_id,
                        tweet_mode='extended')
                updated_tw_users.append(tw_user)
            except tweepy.error.TweepError as e:
                sc = e.response.status_code
                if sc == 429:
                    self.logger.debug("- Hit ratelimit, breaking.")
                    break

                if sc == 401:
                    users_to_cleanup.append((tw_user, 'PROTECTED'))
                    self.logger.debug("- Protected tweets here. Cleaning up this user")
                    continue

                if sc == 404:
                    users_to_cleanup.append((tw_user, 'NOTFOUND'))
                    self.logger.debug("- 404? Maybe screen name changed? Cleaning up this user")
                    continue

                self.logger.debug(
                    "- Unknown exception, Status code {}".format(sc))
                continue

            for tweet in tweets:
       
                self.logger.debug("- (" + tw_user.screen_name +") Got tweet.")
                
                # Check if tweet contains media, else check if it contains a link to an image
                extensions = ('.jpg', '.jpeg', '.png', '.gif')
                pattern = '[(%s)]$' % ')('.join(extensions)
                photo_url = ''

                isRetweet = hasattr(tweet, 'retweeted_status')
                if (isRetweet):
                    tweet_text = html.unescape(tweet.retweeted_status.full_text)
                else:
                    tweet_text = html.unescape(tweet.full_text)

                self.logger.debug("- ("+ tw_user.screen_name +") - " + tweet_text)

                isBlocked = False
                for blockedstr in self.blocklist:
                    if blockedstr.lower() in tweet_text.lower():
                       self.logger.debug("- ("+ tw_user.screen_name +") - Blocked string: " + blockedstr);
                       isBlocked = True
                       break
                if isBlocked:
                    self.logger.debug("- ("+ tw_user.screen_name +") - Blocked string. Going to next tweet.")
                    break
                  
                # Only catch reply that are reply to themselves. (For example news source replying to their own tweets)
                if (tweet.in_reply_to_status_id_str):
                    if tweet.in_reply_to_screen_name == tw_user.screen_name:
                        is_reply = True
                        reply_to = tweet.in_reply_to_status_id_str
                        self.logger.debug("- ("+ tw_user.screen_name +") - Reply to user: " + tweet.in_reply_to_screen_name + " - status id: " + tweet.in_reply_to_status_id_str)
                    else:
                        self.logger.debug("- ("+ tw_user.screen_name +") - Reply to an other user: " + tweet.in_reply_to_screen_name + ". Tweet canceled.")
                        break
                else:
                    reply_to = ''
                    is_reply = False

                users_skip_retweet_prefix = [ 'strasbourg', 'F3Alsace', 'bleualsace', 'Alsace', 'Tanziloic' ]

                if (isRetweet and tw_user.screen_name not in users_skip_retweet_prefix) :
                    self.logger.debug('- ('+ tw_user.screen_name +') Retweet detected.')
                    userRTFrom = tweet.retweeted_status.user.screen_name
                    tweet_text = 'Retweet @' + userRTFrom + ' : ' + tweet_text
                    # Check if retweeted user (userRTFrom) is in blocklist
                    isBlockedRT = False
                    for blockedstr in self.blocklist:
                        if blockedstr.lower() in userRTFrom.lower():
                           self.logger.debug("- ("+ tw_user.screen_name +") - Blocked string: " + blockedstr);
                           isBlockedRT = True
                           break
                    if isBlockedRT:
                        self.logger.debug("- ("+ tw_user.screen_name +") - Blocked string. Going to next tweet.")
                        break

                if 'media' in tweet.entities:
                    photo_url = tweet.entities['media'][0]['media_url_https']
                else:
                    for url_entity in tweet.entities['urls']:
                        expanded_url = url_entity['expanded_url']
                        if re.search(pattern, expanded_url):
                            photo_url = expanded_url
                            break

                # Cancel if retweet himself
                if (isRetweet):
                    if (tw_user.screen_name == tweet.retweeted_status.user.screen_name):
                        self.logger.debug("- ("+ tw_user.screen_name +") Retweeted target is himself. Skipping...")
                        break

                # Check extended_entities in tweet or retweet for video/gif
                if (isRetweet):
                    tweetSearched = tweet.retweeted_status
                else:
                    tweetSearched = tweet

                if hasattr(tweetSearched, 'extended_entities'):
                        self.logger.debug('- ('+ tw_user.screen_name +') tweetSearched.extended_entities found.')
                        media_type = tweetSearched.extended_entities['media'][0]['type']
                        self.logger.debug('- ('+ tw_user.screen_name +') Media type : ' + tweetSearched.extended_entities['media'][0]['type'])
                        if (media_type == 'video' or media_type == 'animated_gif'):
                            self.logger.debug('- ('+ tw_user.screen_name +') - Type video or gif in retweeted_status.')
                            for variant in tweetSearched.extended_entities['media'][0]['video_info']['variants']:
                                if '.mp4' in variant['url']:
                                    # Number of bytes in a megabyte
                                    MBFACTOR = float(1 << 20)
                                    # Send HEAD request to get video (file) size.
                                    response = requests.head(variant['url'], allow_redirects=True)
                                    video_size = response.headers.get('content-length', 0)
                                    video_size_human = '{:.2f}'.format(int(video_size) / MBFACTOR)
                                    self.logger.debug('- ('+ tw_user.screen_name +') - Size: ' + video_size_human +' MB - Variant found: ' + variant['url'])
                                    # Get video less or equals to 10MB
                                    if (float(video_size_human) <= 10.00):
                                        self.logger.debug('- ('+ tw_user.screen_name +') - - Video URL (<=10MB) Chosen: ' + variant['url'])
                                        photo_url = variant['url']
                                        break;
                                    elif '640x360' in variant['url'] or '360x640' in variant['url'] or '720x720' in variant['url'] or '540x540' in variant['url'] or '320x530' in variant['url'] or '360x596' in variant['url']:
                                        self.logger.debug('- ('+ tw_user.screen_name +') - - Video URL Chosen: ' + variant['url'])
                                        photo_url = variant['url']
                                        break;
                        elif (media_type == 'photo'):
                            self.logger.debug('- ('+ tw_user.screen_name +') - Type photo in retweeted_status.')
                            photo_url = tweetSearched.extended_entities['media'][0]['media_url_https']

                if photo_url:
                    self.logger.debug("- ("+ tw_user.screen_name +") Chosen Media URL: " + photo_url)

                for url_entity in tweet.entities['urls']:
                    expanded_url = url_entity['expanded_url']
                    self.logger.debug('- ('+ tw_user.screen_name +') - Expanded_url: ' + expanded_url);
                    indices = url_entity['indices']
                    display_url = tweet.full_text[indices[0]:indices[1]]
                    tweet_text = tweet_text.replace(display_url, expanded_url)

                tw_data = {
                    'tw_id': tweet.id,
                    'text': tweet_text,
                    'created_at': tweet.created_at,
                    'twitter_user': tw_user,
                    'photo_url': photo_url,
                    'reply_to': reply_to,
                    'is_reply': is_reply,
                }

                try:
                    t = Tweet.get(Tweet.tw_id == tweet.id)
                    self.logger.warning("Got duplicated tw_id on this tweet:")
                    self.logger.warning(str(tw_data))
                except Tweet.DoesNotExist:
                    tweet_rows.append(tw_data)

                if len(tweet_rows) >= self.TWEET_BATCH_INSERT_COUNT:
                    Tweet.insert_many(tweet_rows).execute()
                    tweet_rows = []

        TwitterUser.update(last_fetched=datetime.now()).where(TwitterUser.id << [tw.id for tw in updated_tw_users]).execute()

        if not updated_tw_users:
            return

        if tweet_rows:
            Tweet.insert_many(tweet_rows).execute()

        # send the new tweets to subscribers
        subscriptions = list(Subscription.select().where(Subscription.tw_user << updated_tw_users))

        for s in subscriptions:
            # are there new tweets? send em all!
            self.logger.debug("Checking subscription {} {}".format(s.tg_chat.chat_id, s.tw_user.screen_name))

            if s.last_tweet_id == 0:  # didn't receive any tweet yet
                try:
                    tw = s.tw_user.tweets.select().order_by(Tweet.tw_id.desc()).first()
                    if tw is None:
                        self.logger.warning("Something fishy is going on here...")
                    else:
                        bot.send_tweet(s.tg_chat, tw, False, '')
                        # save the latest tweet sent on this subscription
                        s.last_tweet_id = tw.tw_id
                        s.save()
                except IndexError:
                    self.logger.debug("- No tweets available yet on {}".format(s.tw_user.screen_name))

                continue

            if s.tw_user.last_tweet_id > s.last_tweet_id:
                self.logger.debug("- Some fresh tweets here!")
                for tw in (s.tw_user.tweets.select().where(Tweet.tw_id > s.last_tweet_id).order_by(Tweet.tw_id.asc())):

                    # Check if is a reply. If it's a reply check if reply is in db and send the reply_tweet with it.
                    if (tw.is_reply):
                        reply_to = s.tw_user.tweets.select().where(Tweet.tw_id == tw.reply_to).first()
                        if (reply_to != None):
                            self.logger.debug("- Replied tweet in db. Text is: " + reply_to.text)
                            bot.send_tweet(s.tg_chat, tw, tw.is_reply, reply_to)
                        else:
                            self.logger.debug("- Is a reply but replied tweet not in db")
                            bot.send_tweet(s.tg_chat, tw, False, '')
                    else:
                        bot.send_tweet(s.tg_chat, tw, False, '')

                # Save the latest tweet sent on this subscription
                s.last_tweet_id = s.tw_user.last_tweet_id
                s.save()
                continue

            self.logger.debug("- No new tweets here.")


        self.logger.debug("Starting tw_user cleanup")
        if not users_to_cleanup:
            self.logger.debug("- Nothing to cleanup")
        else:
            for tw_user, reason in users_to_cleanup:
                self.logger.debug("- Cleaning up subs on user @{}, {}".format(tw_user.screen_name, reason))
                message = INFO_CLEANUP[reason].format(tw_user.screen_name)
                subs = list(tw_user.subscriptions)
                for s in subs:
                    chat = s.tg_chat
                    if chat.delete_soon:
                        self.logger.debug ("- - skipping because of delete_soon chatid={}".format(chat_id))
                        continue
                    chat_id = chat.chat_id
                    self.logger.debug ("- - bye on chatid={}".format(chat_id))
                    s.delete_instance()

                    try:
                        bot.sendMessage(chat_id=chat_id, text=message)
                    except TelegramError as e:
                        self.logger.info("Couldn't send unsubscription notice of {} to chat {}: {}".format(
                            tw_user.screen_name, chat_id, e.message
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

            self.logger.debug("- Cleaning up TwitterUser @{}".format(tw_user.screen_name, reason))
            tw_user.delete_instance()

            self.logger.debug ("- Cleanup finished")

        self.logger.debug("Cleaning up TelegramChats marked for deletion")
        for chat in TelegramChat.select().where(TelegramChat.delete_soon == True):
            chat.delete_instance(recursive=True)
            self.logger.debug("Deleting chat {}".format(chat.chat_id))
