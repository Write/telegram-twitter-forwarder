from functools import wraps
import re


def with_touched_chat(f):
    @wraps(f)
    def wrapper(bot, update=None, *args, **kwargs):
        if update is None:
            return f(bot, *args, **kwargs)

        chat = bot.get_chat(update.message.chat)
        chat.touch_contact()
        kwargs.update(chat=chat)
        return f(bot, update, *args, **kwargs)

    return wrapper


def escape_markdown(text):
    """Helper function to escape telegram markup symbols"""
    escape_chars = '\*_`\['
    return re.sub(r'([%s])' % escape_chars, r'\\\1', text)

def remove_echobox(text):
    return re.sub(r'#Echobox.*', '', text)

def remove_after_ext(text):
    return re.sub(r'\?.*', '', text)

def remove_utm(text):
    return re.sub(r'\?utm_.*', '', text)

def remove_underscore(text):
    return re.sub(r'\?__.*', '', text)

def remove_hashtag_afterhashtag(text):
    return re.sub(r'\?[^\s]*#.*', '', text)

def keep_one_carriage(text):
    return re.sub(r'\n{1,}|\r{1,}|\r\n{1,}', '\n', text)
    #return re.sub(r'(\n|\s{2,})', '\n', text)

def remove_last_carriage(text):
    return re.sub(r'(^[\r\n]+|[\r\n]+|[\n]+$)', '\n', text)

def remove_tco(text):
    return re.sub(r'https:\/\/t.co\/.*', '', text)

def remove_all_carriage(text):
    return re.sub(r'\n|\s{2,}', ' ', text)

def remove_hashtag_utm(text):
    return re.sub(r'#utm_.*', '', text)

def remove_hashtag_xtor(text):
    return re.sub(r'#xtor.*', '', text)

def remove_hashtag_xtor2(text):
    return re.sub(r'\?xtor.*', '', text)

def remove_cmp(text):
    return re.sub(r'\?CMP.*', '', text)

def remove_origine(text):
    return re.sub(r'\?origine.*', '', text)

def markdown_twitter_usernames(text):
    """Restore markdown escaped usernames and make them link to twitter"""
    return re.sub(r'\B(\@[a-zA-Z_0-9]+\b)(?!;)',
                  lambda s: '[@{username}](https://twitter.com/{username})'
                  .format(username=s.group(1).replace(r'\_', '_')),
                  text)

def html_twitter_usernames(text):
    """Restore markdown escaped usernames and make them link to twitter"""
    return re.sub(r'\B\@([a-zA-Z_0-9]+\b)(?!;)',
                  lambda s: "<a href='https://twitter.com/{username}'>@{username}</a>"
                  .format(username=s.group(1).replace(r'\_', '_')),
                  text)

def markdown_twitter_hashtags(text):
    """Restore markdown escaped hashtags and make them link to twitter"""
    return re.sub(r'\B(\#[a-zA-Z_çàéèù0-9]+\b)(?!;)',
                  lambda s: '[#{tag}](https://twitter.com/hashtag/{tag})'
                  .format(tag=s.group(1).replace(r'\_', '_')),
                  text)

def html_twitter_hashtags(text):
    """Restore markdown escaped hashtags and make them link to twitter"""
    return re.sub(r'\B\#([a-zA-Z_çàéèù0-9]+\b)(?!;)',
                  lambda s: "<a href='https://twitter.com/hashtag/{tag}'>#{tag}</a>"
                  .format(tag=s.group(1).replace(r'\_', '_')),
                  text)

def sanitize_url(url):
    res = remove_echobox(url)
    res = remove_utm(res)
    res = remove_hashtag_utm(res)
    res = remove_hashtag_xtor(res)
    res = remove_hashtag_xtor2(res)
    res = remove_hashtag_afterhashtag(res)
    res = remove_underscore(res)
    res = remove_origine(res)
    res = remove_cmp(res)
    return res

def prepare_tweet_text_reply(text):
    """Do all escape things for tweet text"""
    res = sanitize_url(text)
    return res

def prepare_tweet_text(text):
    """Do all escape things for tweet text"""
    res = sanitize_url(text)
    res = html_twitter_usernames(res)
    #res = html_twitter_hashtags(res)
    return res
