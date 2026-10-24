"""Einmalig lokal ausführen, um den YouTube-Refresh-Token zu bekommen.

    pip install google-auth-oauthlib
    python scripts/get_youtube_token.py pfad/zu/client_secret.json

Es öffnet sich ein Browser-Fenster: Mit dem Google-Konto anmelden, dem der
YouTube-Kanal gehört, und den Zugriff erlauben. Danach werden die drei Werte
ausgegeben, die als GitHub-Secrets eingetragen werden.
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

if len(sys.argv) != 2:
    sys.exit(__doc__)

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
client = json.load(open(sys.argv[1]))["installed"]

print("\nDiese drei Werte als GitHub-Secrets eintragen:\n")
print(f"YOUTUBE_CLIENT_ID={client['client_id']}")
print(f"YOUTUBE_CLIENT_SECRET={client['client_secret']}")
print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
