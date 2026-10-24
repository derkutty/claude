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
