# main.py

import os
import requests
import subprocess
from tweepy import TweepyException
from praw.exceptions import PRAWException
from requests.exceptions import RequestException

from twitter import tweet_content, twitter_api_v1, twitter_api_v2
from reddit import (
    get_submission, get_submission_gallery_filenames, get_submission_filename,
    get_submission_chunked, get_submission_media_category, reddit_api, get_submission_video_urls 
)

TWEET_MAX_LENGTH = 280
CURRENT_DIR = os.getcwd()
IMAGES_PATH = os.path.join(CURRENT_DIR, "images")

DICT_HASHTAGS = {
  "anime": "#anime #manga",
  "anime_irl": "#anime #manga",
  "animegifs": "#anime #manga",
  "animememes": "#Memes #anime #manga",
  "attackontitan": "#SNK #ShingekiNoKyojin #AoT #AttackOnTitan",
  "Berserk": "#Berserk",
  "bleach": "#BLEACH",
  "BlueLock": "#bluelock",
  "BokuNoHeroAcademia": "#BokuNoHeroAcademia #MyHeroAcadamia #mha",
  "BokuNoMetaAcademia": "#Memes #BokuNoHeroAcademia #MyHeroAcadamia #mha",
  "Boruto": "#BorutoNarutonextgenerations #BORUTO #NARUTO #NarutoShippuden",
  "ChainsawMan": "#chainsawman",
  "dankruto": "#Memes #NARUTO #NarutoShippuden",
  "dbz": "#DBZ #DragonBall #DragonBallZ #DragonBallGT #DragonBallSuper",
  "deathnote": "#DeathNote",
  "Dragonballsuper": "#DBZ #DragonBall #DragonBallZ #DragonBallGT #DragonBallSuper",
  "DrStone": "#DrSTONE",
  "fairytail": "#FairyTail",
  "FullmetalAlchemist": "#fma #FullmetalAlchemist #fmab #FullmetalAlchemistBrotherhood",
  "GoldenKamuy": "#goldenkamuy",
  "Grapplerbaki": "#baki",
  "hajimenoippo": "#hajimenoippo",
  "HunterXHunter": "#hxh #HunterXHunter",
  "JuJutsuKaisen": "#JJK #JujutsuKaisen",
  "KimetsuNoYaiba": "#DemonSlayer #kimetsunoyaiba",
  "Kingdom": "#Kingdom",
  "MemePiece": "#Memes #ONEPIECE",
  "Naruto": "#NARUTO #NarutoShippuden",
  "Ningen": "#Memes #DBZ #DragonBall #DragonBallZ #DragonBallGT #DragonBallSuper",
  "OnePiece": "#ONEPIECE",
  "OnePunchMan": "#OnePunchMan",
  "Re_Zero": "#rezero",
  "ShingekiNoKyojin": "#SNK #ShingekiNoKyojin #AoT #AttackOnTitan",
  "ShitPostCrusaders": "#Memes #JJBA #JOJOsBizzareAdventure #stardustcrusaders #goldenwind #StoneOcean",
  "sololeveling": "#sololeveling",
  "StardustCrusaders": "#JJBA #JOJOsBizzareAdventure #stardustcrusaders #goldenwind #StoneOcean",
  "TokyoRevengers": "#TokyoRevengers",
  "VinlandSaga": "#VinlandSaga #VINLAND_SAGA",
  "yugioh": "#yugioh",
  "YuYuHakusho": "#YuYuHakusho",
}

def download_content(urls, file_path_list):
    """Télécharge le contenu des URLs en utilisant requests."""
    for url, file_path in zip(urls, file_path_list):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except RequestException as e:
            print(f"Erreur de téléchargement pour {url}: {e}")
            # Si un fichier ne peut être téléchargé, on le supprime pour éviter un tweet partiel
            if os.path.exists(file_path):
                os.remove(file_path)
            raise # Propage l'exception pour que la boucle principale l'attrape

def download_and_merge_video(video_url, audio_url, output_path):
    """Télécharge la vidéo et l'audio, puis les fusionne avec FFmpeg."""
    temp_video_path = os.path.join(IMAGES_PATH, "temp_video.mp4")
    temp_audio_path = os.path.join(IMAGES_PATH, "temp_audio.mp4")

    # Étape 1: Télécharger la vidéo
    download_content([video_url], [temp_video_path])

    if audio_url:
        # Étape 2: Télécharger l'audio
        download_content([audio_url], [temp_audio_path])
        
        # Étape 3: Fusionner avec FFmpeg
        # -i : input file
        # -c:v copy : copie le flux vidéo sans le ré-encoder (rapide)
        # -c:a copy : copie le flux audio sans le ré-encoder (rapide)
        command = [
            'ffmpeg',
            '-i', temp_video_path,
            '-i', temp_audio_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            output_path
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Erreur avec FFmpeg. Assurez-vous qu'il est installé et dans le PATH. Erreur: {e}")
            # Si la fusion échoue, on fournit au moins la vidéo sans son
            os.rename(temp_video_path, output_path)
        finally:
            # Étape 4: Nettoyer les fichiers temporaires
            if os.path.exists(temp_video_path): os.remove(temp_video_path)
            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
    else:
        # Pas d'audio, on renomme juste le fichier vidéo
        os.rename(temp_video_path, output_path)

def delete_all_files():
    """Supprime tous les fichiers médias téléchargés."""
    for filename in os.listdir(IMAGES_PATH):
        if filename != "placeholder.txt":
            os.remove(os.path.join(IMAGES_PATH, filename))

def create_title(submission):
    """Crée le texte du tweet en respectant la limite de caractères."""
    subreddit_name = str(submission.subreddit)
    hashtag = DICT_HASHTAGS.get(subreddit_name, "#anime #manga")
    credits = "📸: " + submission.shortlink
    end_message = f"{hashtag}\n\n{credits}"

    available_length = TWEET_MAX_LENGTH - len(end_message) - 1  # -1 pour l'espace
    if len(submission.title) <= available_length:
        return f"{submission.title} {end_message}"
    else:
        truncated_title = submission.title[:available_length - 3] + "..."
        return f"{truncated_title} {end_message}"

if __name__ == "__main__":
    success = False
    iteration = 0
    reddit_instance = reddit_api()
    twitter_instance_v1 = twitter_api_v1()
    twitter_instance_v2 = twitter_api_v2()

    while not success and iteration < 3:
        iteration += 1
        submission = None
        try:
            submission = get_submission(reddit_instance)
            
            urls, file_path_list = [], []

            if "/gallery/" in submission.url:
                filenames, urls = get_submission_gallery_filenames(submission)
                file_path_list = [os.path.join(IMAGES_PATH, fn) for fn in filenames]
                # Le téléchargement se fait ici pour les galeries
                download_content(urls, file_path_list)

            elif "v.redd.it" in submission.url:
                video_url, audio_url = get_submission_video_urls(submission)
                if not video_url:
                    raise Exception("Impossible de trouver l'URL de la vidéo.")
                
                output_filename = get_submission_filename(submission)
                output_path = os.path.join(IMAGES_PATH, output_filename)
                
                # Le téléchargement ET la fusion se font dans cette fonction
                download_and_merge_video(video_url, audio_url, output_path)
                
                # La liste des fichiers à tweeter ne contient que le fichier final
                file_path_list = [output_path]
            else:
                # Pour les images simples et les GIFs
                urls = [submission.url]
                filename = get_submission_filename(submission)
                file_path_list = [os.path.join(IMAGES_PATH, filename)]
                # Le téléchargement se fait ici
                download_content(urls, file_path_list)

            # Maintenant, on tweete le contenu qui a été préparé
            tweet_content(
                twitter_instance_v1,
                twitter_instance_v2,
                create_title(submission),
                file_path_list,
                get_submission_chunked(submission),
                get_submission_media_category(submission),
            )
            
            print(f"Tweet posté avec succès pour la soumission Reddit : {submission.shortlink}")
            submission.save()
            success = True

        except (TweepyException, PRAWException, RequestException) as e:
            print(f"Erreur d'API lors de l'itération {iteration}: {e}")
            if submission:
                submission.save() # Sauvegarde pour ne pas réessayer ce post
        except Exception as e:
            print(f"Une erreur inattendue est survenue lors de l'itération {iteration}: {e}")
            if submission:
                submission.save()
        finally:
            delete_all_files()