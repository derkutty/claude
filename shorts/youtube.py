"""Upload und Statistiken über die YouTube Data API v3."""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import require_env

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def client():
    creds = Credentials(
        None,
        refresh_token=require_env("YOUTUBE_REFRESH_TOKEN"),
        client_id=require_env("YOUTUBE_CLIENT_ID"),
        client_secret=require_env("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(yt, path, title: str, description: str, tags: list[str], upload_cfg: dict) -> str:
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": upload_cfg["category_id"],
            "defaultLanguage": upload_cfg["language_code"],
            "defaultAudioLanguage": upload_cfg["language_code"],
        },
        "status": {
            "privacyStatus": upload_cfg["privacy"],
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": upload_cfg["contains_synthetic_media"],
        },
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=-1, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def _normalize(title: str) -> str:
    return " ".join(title.lower().split())


def link_manual_uploads(yt, history: list[dict]) -> None:
    """Selbst hochgeladene Videos über den Titel den Einträgen im Verlauf zuordnen.

    Liest die letzten 100 Uploads des eigenen Kanals (je 1 Quota-Einheit pro 50)."""
    open_entries = [h for h in history if not h.get("video_id")]
    if not open_entries:
        return
    channels = yt.channels().list(part="contentDetails", mine=True).execute().get("items", [])
    if not channels:
        return
    playlist = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    uploads, token = [], None
    for _ in range(2):
        resp = yt.playlistItems().list(part="snippet,contentDetails", playlistId=playlist, maxResults=50,
                                       pageToken=token).execute()
        uploads += resp.get("items", [])
        token = resp.get("nextPageToken")
        if not token:
            break
    known = {h["video_id"] for h in history if h.get("video_id")}
    for h in open_entries:
        wanted = _normalize(h["title"])
        for item in uploads:
            video_id = item["contentDetails"]["videoId"]
            # "enthält" statt "gleich", falls beim Hochladen z. B. noch ein Hashtag angehängt wurde.
            if video_id not in known and wanted in _normalize(item["snippet"]["title"]):
                h["video_id"] = video_id
                h["published"] = item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"]
                known.add(video_id)
                print(f"Selbst hochgeladenes Video gefunden: {h['title']}")
                break


def refresh_stats(yt, history: list[dict]) -> None:
    """Aufrufe/Likes der bisherigen Videos aktualisieren (kostet 1 Quota-Einheit pro 50 Videos)."""
    ids = [h["video_id"] for h in history if h.get("video_id")]
    by_id = {h["video_id"]: h for h in history if h.get("video_id")}
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        for item in resp.get("items", []):
            stats = item["statistics"]
            entry = by_id[item["id"]]
            entry["views"] = int(stats.get("viewCount", 0))
            entry["likes"] = int(stats.get("likeCount", 0))
