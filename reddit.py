import praw
import requests
import os
import re
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv('config.env')

MINIMUM_SCORE = 0
MAX_PHOTO_SIZE = 5242880
MAX_GIF_SIZE = 15728640
MAX_VIDEO_SIZE = 536870912
LAST_SUBREDDITS_FILE = "last_subreddits.txt"
MEMORY_SIZE = 5

def read_last_subreddits():
    """Lit le fichier de mémoire et retourne une liste des derniers subreddits."""
    if not os.path.exists(LAST_SUBREDDITS_FILE):
        return []
    with open(LAST_SUBREDDITS_FILE, 'r') as f:
        return [line.strip() for line in f.readlines()]

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
    """Vérifie si la taille du contenu d'une URL est inférieure à un seuil."""
    try:
        response = requests.head(url, timeout=10)
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        return content_length and int(content_length) < max_bytes
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
    """Récupère la meilleure soumission valide d'un subreddit qui n'a pas été posté récemment."""
    subreddit = reddit_instance.multireddit('top_anime_13', 'topanime')
    last_subreddits = read_last_subreddits()
    print(f"Subreddits à éviter (mémoire) : {last_subreddits}")

    for submission in subreddit.top('day', limit=100):
        subreddit_name = submission.subreddit.display_name
        is_valid = is_submission_valid(submission)
        is_recent = subreddit_name in last_subreddits
        if is_valid and not is_recent:
            print(f"Submission valide trouvée dans un nouveau subreddit : r/{subreddit_name}")
            return submission

    print("Aucun post de NOUVEAU subreddit trouvé. Recherche du meilleur post valide, peu importe le subreddit.")
    for submission in subreddit.top('day', limit=100):
        if is_submission_valid(submission):
            print(f"Fallback : Utilisation du meilleur post valide de r/{submission.subreddit.display_name}")
            return submission

    raise Exception("Aucune soumission valide n'a été trouvée dans le top 100 des 24 dernières heures.")

def get_submission_gallery_filenames(submission):
    """Extrait les URLs et génère les noms de fichiers pour une galerie."""
    filenames, urls = [], []
    i = 1
    for item in sorted(submission.gallery_data['items'], key=lambda x: x['id']):
        if i > 4: break
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
    if url.endswith('.jpg'): return f"{submission.id}.jpg"
    if url.endswith('.jpeg'): return f"{submission.id}.jpeg"
    if url.endswith('.png'): return f"{submission.id}.png"
    if url.endswith('.gif'): return f"{submission.id}.gif"
    if 'v.redd.it' in url: return f"{submission.id}.mp4"
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
    """Détermine si l'upload doit être 'chunked' (pour les gros fichiers)."""
    return submission.url.endswith('.gif') or 'v.redd.it' in submission.url

def get_submission_video_urls(submission):
    """Retourne les URLs de la PLUS HAUTE QUALITÉ pour la vidéo et l'audio."""
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
        manifest_text = response.text
        root = ET.fromstring(manifest_text)
        namespace = '{urn:mpeg:dash:schema:mpd:2011}'

        max_video_bandwidth = -1
        best_video_file_from_manifest = None
        for adaptation_set in root.findall(f'.//{namespace}AdaptationSet[@contentType="video"]'):
            for representation in adaptation_set.findall(f'{namespace}Representation'):
                bandwidth = int(representation.get('bandwidth', 0))
                if bandwidth > max_video_bandwidth:
                    max_video_bandwidth = bandwidth
                    base_url_tag = representation.find(f'{namespace}BaseURL')
                    if base_url_tag is not None:
                        best_video_file_from_manifest = base_url_tag.text
        
        if best_video_file_from_manifest:
            manifest_res_match = re.search(r'DASH_(\d+)', best_video_file_from_manifest)
            manifest_resolution = int(manifest_res_match.group(1)) if manifest_res_match else 0
            fallback_res_match = re.search(r'DASH_(\d+)', fallback_video_url)
            fallback_resolution = int(fallback_res_match.group(1)) if fallback_res_match else 0
            print(f"Qualité vidéo du manifeste: {manifest_resolution}p. Qualité du fallback: {fallback_resolution}p.")
            if manifest_resolution > fallback_resolution:
                final_video_url = f"{base_url}/{best_video_file_from_manifest}"
                print(f"Le manifeste offre une meilleure qualité ({manifest_resolution}p). Utilisation de cette source.")
            else:
                print(f"Le fallback offre une qualité égale ou supérieure ({fallback_resolution}p). Utilisation du fallback.")
        
        max_audio_bandwidth = -1
        best_audio_file = None
        for adaptation_set in root.findall(f'.//{namespace}AdaptationSet[@contentType="audio"]'):
            for representation in adaptation_set.findall(f'{namespace}Representation'):
                bandwidth = int(representation.get('bandwidth', 0))
                if bandwidth > max_audio_bandwidth:
                    max_audio_bandwidth = bandwidth
                    base_url_tag = representation.find(f'{namespace}BaseURL')
                    if base_url_tag is not None:
                        best_audio_file = base_url_tag.text
        
        if best_audio_file:
            audio_url = f"{base_url}/{best_audio_file}"
            print(f"✅ Meilleur flux audio trouvé (qualité: {max_audio_bandwidth} bps): {audio_url}")

    except Exception as e:
        print(f"Une erreur est survenue lors de l'analyse du manifeste ({e}). Utilisation du fallback_url par défaut.")

    if not audio_url:
        print("⚠️ Pas de flux audio trouvé.")

    print(f"URL vidéo finale choisie : {final_video_url}")
    return final_video_url, audio_url