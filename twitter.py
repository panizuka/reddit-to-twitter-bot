# twitter.py

import tweepy
import os
from dotenv import load_dotenv

load_dotenv('config.env')

# Clés Twitter
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET')

def twitter_api_v1():
    """Configure et retourne une instance de l'API Twitter v1.1 (pour l'upload de médias)."""
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    api = tweepy.API(auth)
    return api

def twitter_api_v2():
    """Configure et retourne une instance client de l'API Twitter v2 (pour créer le tweet)."""
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET
    )
    return client

def tweet_content(twitter_instance_v1, twitter_instance_v2, message, file_path_list, chunked, media_category):
    """Uploade les médias et poste le tweet."""
    if not file_path_list:
        print("Aucun fichier à uploader. Annulation du tweet.")
        return

    media_ids = []
    for file_path in file_path_list:
        # Vérifie que le fichier existe et n'est pas vide avant de l'uploader
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            media = twitter_instance_v1.media_upload(
                filename=file_path, 
                chunked=chunked, 
                media_category=media_category
            )
            media_ids.append(media.media_id)
        else:
            print(f"Le fichier {file_path} est invalide ou vide. Il ne sera pas uploadé.")

    if not media_ids:
        print("Aucun média n'a pu être uploadé. Annulation du tweet.")
        return

    twitter_instance_v2.create_tweet(text=message, media_ids=media_ids)