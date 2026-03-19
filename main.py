import os
import sys
import requests
import subprocess
from tweepy import TweepyException
from praw.exceptions import PRAWException
from requests.exceptions import RequestException
from twitter import tweet_content, twitter_api_v1, twitter_api_v2
from reddit import (
    get_submission, get_submission_gallery_filenames, get_submission_filename,
    get_submission_chunked, get_submission_media_category, reddit_api,
    get_submission_video_urls, update_last_subreddits
)
from dotenv import load_dotenv

load_dotenv('config.env')
TWEET_MAX_LENGTH = 280
CURRENT_DIR = os.getcwd()
IMAGES_PATH = os.path.join(CURRENT_DIR, "images")
HEALTHCHECK_URL = os.getenv('HEALTHCHECK_URL')
if not HEALTHCHECK_URL:
    raise EnvironmentError("Variable d'environnement manquante : HEALTHCHECK_URL")

DICT_HASHTAGS = {
    "anime": "#anime #manga", "anime_irl": "#anime #manga", "animegifs": "#anime #manga",
    "animememes": "#Memes #anime #manga", "attackontitan": "#SNK #ShingekiNoKyojin #AoT #AttackOnTitan",
    "Berserk": "#Berserk", "bleach": "#BLEACH", "BlueLock": "#bluelock",
    "BokuNoHeroAcademia": "#BokuNoHeroAcademia #MyHeroAcadamia #mha",
    "BokuNoMetaAcademia": "#Memes #BokuNoHeroAcademia #MyHeroAcadamia #mha",
    "Boruto": "#BorutoNarutonextgenerations #BORUTO #NARUTO #NarutoShippuden",
    "ChainsawMan": "#chainsawman", "dankruto": "#Memes #NARUTO #NarutoShippuden",
    "dbz": "#DBZ #DragonBall #DragonBallZ #DragonBallGT #DragonBallSuper", "deathnote": "#DeathNote",
    "Dragonballsuper": "#DBZ #DragonBall #DragonBallZ #DragonBallGT #DragonBallSuper",
    "DrStone": "#DrSTONE", "fairytail": "#FairyTail",
    "FullmetalAlchemist": "#fma #FullmetalAlchemist #fmab #FullmetalAlchemistBrotherhood",
    "GoldenKamuy": "#goldenkamuy", "Grapplerbaki": "#baki", "hajimenoippo": "#hajimenoippo",
    "HunterXHunter": "#hxh #HunterXHunter", "JuJutsuKaisen": "#JJK #JujutsuKaisen",
    "KimetsuNoYaiba": "#DemonSlayer #kimetsunoyaiba", "Kingdom": "#Kingdom",
    "MemePiece": "#Memes #ONEPIECE", "Naruto": "#NARUTO #NarutoShippuden",
    "Ningen": "#Memes #DBZ #DragonBall #DragonBallZ #DragonBallGT #DragonBallSuper",
    "OnePiece": "#ONEPIECE", "OnePunchMan": "#OnePunchMan", "Re_Zero": "#rezero",
    "ShingekiNoKyojin": "#SNK #ShingekiNoKyojin #AoT #AttackOnTitan",
    "ShitPostCrusaders": "#Memes #JJBA #JOJOsBizzareAdventure", "sololeveling": "#sololeveling",
    "StardustCrusaders": "#JJBA #JOJOsBizzareAdventure", "TokyoRevengers": "#TokyoRevengers",
    "VinlandSaga": "#VinlandSaga #VINLAND_SAGA", "yugioh": "#yugioh", "YuYuHakusho": "#YuYuHakusho",
}


def ping_healthcheck(success=True):
    """Ping Healthchecks.io pour signaler succès ou échec."""
    url = HEALTHCHECK_URL if success else f"{HEALTHCHECK_URL}/fail"
    try:
        requests.get(url, timeout=10)
        print(f"Healthcheck pingé ({'succès' if success else 'échec'}).")
    except RequestException as e:
        print(f"Impossible de pinguer Healthcheck : {e}")


def download_content(urls, file_path_list):
    """Télécharge le contenu des URLs en utilisant requests."""
    for url, file_path in zip(urls, file_path_list):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except RequestException as e:
            print(f"Erreur de téléchargement pour {url}: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            raise


def download_and_merge_video(video_url, audio_url, output_path):
    """Télécharge la vidéo et l'audio, puis les fusionne avec FFmpeg."""
    temp_video_path = os.path.join(IMAGES_PATH, "temp_video.mp4")
    temp_audio_path = os.path.join(IMAGES_PATH, "temp_audio.mp4")
    download_content([video_url], [temp_video_path])
    if audio_url:
        download_content([audio_url], [temp_audio_path])
        command = [
            'ffmpeg', '-i', temp_video_path, '-i', temp_audio_path,
            '-c:v', 'copy', '-c:a', 'copy', output_path
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Erreur FFmpeg : {e}. Utilisation de la vidéo sans audio.")
            os.rename(temp_video_path, output_path)
        finally:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
    else:
        os.rename(temp_video_path, output_path)


def delete_all_files():
    """Supprime tous les fichiers médias téléchargés."""
    for filename in os.listdir(IMAGES_PATH):
        if filename != "placeholder.txt":
            try:
                os.remove(os.path.join(IMAGES_PATH, filename))
            except OSError as e:
                print(f"Impossible de supprimer {filename} : {e}")


def create_title(submission):
    """Crée le texte du tweet en respectant la limite de caractères."""
    subreddit_name = str(submission.subreddit)
    hashtag = DICT_HASHTAGS.get(subreddit_name, "#anime #manga")
    credits = "📸: " + submission.shortlink
    end_message = f"{hashtag}\n\n{credits}"
    available_length = TWEET_MAX_LENGTH - len(end_message) - 1
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
            file_path_list = []

            if "/gallery/" in submission.url:
                filenames, urls = get_submission_gallery_filenames(submission)
                file_path_list = [os.path.join(IMAGES_PATH, fn) for fn in filenames]
                download_content(urls, file_path_list)
            elif "v.redd.it" in submission.url:
                video_url, audio_url = get_submission_video_urls(submission)
                if not video_url:
                    raise Exception("Impossible de trouver l'URL de la vidéo.")
                output_filename = get_submission_filename(submission)
                output_path = os.path.join(IMAGES_PATH, output_filename)
                download_and_merge_video(video_url, audio_url, output_path)
                file_path_list = [output_path]
            else:
                urls = [submission.url]
                filename = get_submission_filename(submission)
                file_path_list = [os.path.join(IMAGES_PATH, filename)]
                download_content(urls, file_path_list)

            tweet_content(
                twitter_instance_v1,
                twitter_instance_v2,
                create_title(submission),
                file_path_list,
                get_submission_chunked(submission),
                get_submission_media_category(submission),
            )

            print(f"Tweet posté avec succès : {submission.shortlink}")
            update_last_subreddits(submission.subreddit.display_name)
            submission.save()
            success = True

        except (TweepyException, PRAWException, RequestException) as e:
            print(f"Erreur d'API lors de l'itération {iteration}: {e}")
            if submission:
                submission.save()
        except Exception as e:
            print(f"Erreur inattendue lors de l'itération {iteration}: {e}")
            if submission:
                submission.save()
        finally:
            delete_all_files()

    if success:
        ping_healthcheck(success=True)
    else:
        print("Échec après 3 tentatives.")
        ping_healthcheck(success=False)
        sys.exit(1)