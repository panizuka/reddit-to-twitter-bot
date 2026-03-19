import praw
import requests
import os
import re
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv('config.env')

MINIMUM_SCORE = 0
MAX_PHOTO_SIZE = 5242880    # 5 MB
MAX_GIF_SIZE = 15728640     # 15 MB
MAX_VIDEO_SIZE = 536870912  # 512 MB
LAST_SUBREDDITS_FILE = "last_subreddits.txt"
MEMORY_SIZE = 5

# Validation des variables d'environnement au démarrage
_required_vars = ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT',
                  'REDDIT_PASSWORD', 'REDDIT_USERNAME']
for _var in _required_vars:
    if not os.getenv(_var):
        raise EnvironmentError(f"Variable d'environnement manquante : {_var}")


def read_last_subreddits():
    """Lit le fichier de mémoire et retourne une liste des derniers subreddits."""
    if not os.path.exists(LAST_SUBREDDITS_FILE):
        return []
    with open(LAST_SUBREDDITS_FILE, 'r') as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def update_last_subreddits(subreddit_name):
    """Met à jour le fichier de mémoire avec le nouveau subreddit."""
    last_subreddits = read_last_subreddits()
    if subreddit_name in last_subreddits:
        last_subreddits.remove(subreddit_name)
    last_subreddits.insert(0, subreddit_name)
    updated_list = last_subreddits[:MEMORY_SIZE]
    with open(LAST_SUBREDDITS_FILE, 'w') as f:
        f.write('\n'.join(updated_list))
    print(f"Mémoire mise à jour. Subreddits récents : {updated_list}")


def check_size(url, max_bytes):
    """Vérifie si la taille du contenu d'une URL est inférieure à un seuil.
    Si Content-Length est absent, on accepte (certains CDN ne l'envoient pas)."""
    try:
        response = requests.head(url, timeout=10)
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length is None:
            return True  # Taille inconnue → on fait confiance
        return int(content_length) < max_bytes
    except requests.RequestException:
        return False


def reddit_api():
    """Initialise et retourne une instance de l'API Reddit."""
    return praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT'),
        password=os.getenv('REDDIT_PASSWORD'),
        username=os.getenv('REDDIT_USERNAME')
    )


def is_submission_valid(submission):
    """Vérifie si une soumission est valide pour être tweetée (score, type, taille)."""
    if submission.score < MINIMUM_SCORE or submission.saved or submission.spoiler or submission.over_18:
        return False
    url = submission.url
    if 'v.redd.it' in url:
        try:
            video_url = submission.media["reddit_video"]["fallback_url"]
            return check_size(video_url, MAX_VIDEO_SIZE)
        except (KeyError, TypeError):
            return False
    if url.endswith('.gif'):
        return check_size(url, MAX_GIF_SIZE)
    if url.endswith(('.jpg', '.png', '.jpeg')):
        return check_size(url, MAX_PHOTO_SIZE)
    if "/gallery/" in url:
        for item in submission.gallery_data['items']:
            media_id = item['media_id']
            meta = submission.media_metadata[media_id]
            if meta['e'] == 'Image':
                ext = meta['m'].split('/')[-1]
                if ext in ["jpg", "png", "jpeg"] and check_size(meta['s']['u'], MAX_PHOTO_SIZE):
                    return True
        return False
    return False


def get_submission(reddit_instance):
    """Récupère la meilleure soumission valide d'un subreddit non posté récemment.
    Une seule requête Reddit grâce au cache de la liste."""
    subreddit = reddit_instance.multireddit('top_anime_13', 'topanime')
    last_subreddits = read_last_subreddits()
    print(f"Subreddits à éviter (mémoire) : {last_subreddits}")

    # On récupère la liste une seule fois
    submissions = list(subreddit.top('day', limit=100))

    # Passe 1 : chercher dans un subreddit non récent
    for submission in submissions:
        subreddit_name = submission.subreddit.display_name
        if is_submission_valid(submission) and subreddit_name not in last_subreddits:
            print(f"Submission valide trouvée dans un nouveau subreddit : r/{subreddit_name}")
            return submission

    # Passe 2 : fallback sur n'importe quel subreddit valide
    print("Aucun post de nouveau subreddit trouvé. Recherche du meilleur post valide.")
    for submission in submissions:
        if is_submission_valid(submission):
            print(f"Fallback : r/{submission.subreddit.display_name}")
            return submission

    raise Exception("Aucune soumission valide trouvée dans le top 100 des 24 dernières heures.")


def get_submission_gallery_filenames(submission):
    """Extrait les URLs et génère les noms de fichiers pour une galerie (max 4 images)."""
    filenames, urls = [], []
    i = 1
    for item in sorted(submission.gallery_data['items'], key=lambda x: x['id']):
        if i > 4:
            break
        media_id = item['media_id']
        meta = submission.media_metadata[media_id]
        if meta['e'] == 'Image':
            ext = meta['m'].split('/')[-1]
            source_url = meta['s']['u']
            if ext in ["jpg", "png", "jpeg"] and check_size(source_url, MAX_PHOTO_SIZE):
                urls.append(source_url)
                filenames.append(f"{submission.id}-{i}.{ext}")
                i += 1
    return filenames, urls


def get_submission_filename(submission):
    """Génère un nom de fichier unique basé sur l'ID de la soumission."""
    url = submission.url
    if url.endswith('.jpg'):   return f"{submission.id}.jpg"
    if url.endswith('.jpeg'):  return f"{submission.id}.jpeg"
    if url.endswith('.png'):   return f"{submission.id}.png"
    if url.endswith('.gif'):   return f"{submission.id}.gif"
    if 'v.redd.it' in url:    return f"{submission.id}.mp4"
    return f"{submission.id}.tmp"


def get_submission_media_category(submission):
    """Détermine la catégorie de média pour l'API Twitter."""
    if "/gallery/" in submission.url or submission.url.endswith(('.jpg', '.png', '.jpeg')):
        return "tweet_image"
    if submission.url.endswith('.gif'):
        return "tweet_gif"
    if 'v.redd.it' in submission.url:
        return "tweet_video"
    return None


def get_submission_chunked(submission):
    """Détermine si l'upload doit être chunked (GIF et vidéos)."""
    return submission.url.endswith('.gif') or 'v.redd.it' in submission.url


def get_submission_video_urls(submission):
    """Retourne les URLs de la meilleure qualité pour la vidéo et l'audio."""
    if not submission.is_video or "reddit_video" not in submission.media:
        return None, None

    fallback_video_url = submission.media["reddit_video"]["fallback_url"]
    audio_url = None
    manifest_url = submission.media["reddit_video"]["dash_url"]
    base_url = manifest_url.rsplit('/', 1)[0]
    final_video_url = fallback_video_url.split('?')[0]

    try:
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespace = '{urn:mpeg:dash:schema:mpd:2011}'

        # Meilleure qualité vidéo
        max_video_bandwidth = -1
        best_video_file = None
        for adaptation_set in root.findall(f'.//{namespace}AdaptationSet[@contentType="video"]'):
            for representation in adaptation_set.findall(f'{namespace}Representation'):
                bandwidth = int(representation.get('bandwidth', 0))
                if bandwidth > max_video_bandwidth:
                    max_video_bandwidth = bandwidth
                    tag = representation.find(f'{namespace}BaseURL')
                    if tag is not None:
                        best_video_file = tag.text

        if best_video_file:
            manifest_res = int(re.search(r'DASH_(\d+)', best_video_file).group(1)) \
                if re.search(r'DASH_(\d+)', best_video_file) else 0
            fallback_res = int(re.search(r'DASH_(\d+)', fallback_video_url).group(1)) \
                if re.search(r'DASH_(\d+)', fallback_video_url) else 0
            print(f"Qualité manifeste: {manifest_res}p | Qualité fallback: {fallback_res}p")
            if manifest_res > fallback_res:
                final_video_url = f"{base_url}/{best_video_file}"
                print(f"Utilisation du manifeste ({manifest_res}p).")
            else:
                print(f"Utilisation du fallback ({fallback_res}p).")

        # Meilleur flux audio
        max_audio_bandwidth = -1
        best_audio_file = None
        for adaptation_set in root.findall(f'.//{namespace}AdaptationSet[@contentType="audio"]'):
            for representation in adaptation_set.findall(f'{namespace}Representation'):
                bandwidth = int(representation.get('bandwidth', 0))
                if bandwidth > max_audio_bandwidth:
                    max_audio_bandwidth = bandwidth
                    tag = representation.find(f'{namespace}BaseURL')
                    if tag is not None:
                        best_audio_file = tag.text

        if best_audio_file:
            audio_url = f"{base_url}/{best_audio_file}"
            print(f"Flux audio trouvé ({max_audio_bandwidth} bps): {audio_url}")

    except Exception as e:
        print(f"Erreur analyse manifeste ({e}). Utilisation du fallback.")

    if not audio_url:
        print("Pas de flux audio trouvé.")

    print(f"URL vidéo finale : {final_video_url}")
    return final_video_url, audio_url