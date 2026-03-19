import os
import time
import tweepy
from tweepy import TweepyException, TooManyRequests
from dotenv import load_dotenv

load_dotenv('config.env')

TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET')

_required_vars = {
    'TWITTER_API_KEY': TWITTER_API_KEY,
    'TWITTER_API_SECRET': TWITTER_API_SECRET,
    'TWITTER_ACCESS_TOKEN': TWITTER_ACCESS_TOKEN,
    'TWITTER_ACCESS_SECRET': TWITTER_ACCESS_SECRET,
}
for _var, _val in _required_vars.items():
    if not _val:
        raise EnvironmentError(f"Variable d'environnement manquante : {_var}")


def twitter_api_v1():
    """Configure et retourne une instance de l'API Twitter v1.1 (upload de médias)."""
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    return tweepy.API(auth)


def twitter_api_v2():
    """Configure et retourne un client de l'API Twitter v2 (création de tweets)."""
    return tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET
    )


def _post_tweet_with_backoff(client, message, media_ids, max_retries=3):
    """Poste un tweet avec gestion du rate limit (429) via TooManyRequests."""
    for attempt in range(1, max_retries + 1):
        try:
            client.create_tweet(text=message, media_ids=media_ids)
            print("Tweet posté via API v2.")
            return
        except TooManyRequests as e:
            # TooManyRequests est le 429 natif de Tweepy — plus propre que lire response.status_code
            if attempt >= max_retries:
                raise
            reset_ts = int(e.response.headers.get('x-rate-limit-reset', 0))
            wait_time = max(reset_ts - time.time(), 60)
            print(f"Rate limit atteint (tentative {attempt}/{max_retries}). "
                  f"Attente de {int(wait_time)}s avant retry...")
            time.sleep(wait_time)
        except TweepyException:
            raise  # Toute autre erreur remonte immédiatement


def tweet_content(twitter_instance_v1, twitter_instance_v2, message, file_path_list, chunked, media_category):
    """Uploade les médias et poste le tweet."""
    if not file_path_list:
        print("Aucun fichier à uploader. Annulation du tweet.")
        return

    media_ids = []
    for file_path in file_path_list:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            media = twitter_instance_v1.media_upload(
                filename=file_path,
                chunked=chunked,
                media_category=media_category
            )
            media_ids.append(media.media_id)
            print(f"Média uploadé : {file_path} → media_id={media.media_id}")
        else:
            print(f"Fichier invalide ou vide, ignoré : {file_path}")

    if not media_ids:
        print("Aucun média uploadé. Annulation du tweet.")
        return

    _post_tweet_with_backoff(twitter_instance_v2, message, media_ids)