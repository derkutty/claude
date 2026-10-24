# Automatischer YouTube-Shorts-Kanal

Erzeugt zweimal täglich ein komplett neues Short und lädt es hoch, ohne dass du etwas tun musst:

1. **Skript:** Claude wählt ein neues Thema in deiner Nische und schreibt ein Skript mit starkem Hook,
   Spannungsbogen und Loop-Ende. Dabei sieht Claude, welche deiner bisherigen Videos die meisten und die
   wenigsten Aufrufe hatten, und richtet die nächsten Ideen danach aus.
2. **Stimme:** kostenlose Microsoft-Edge-Stimmen (`edge-tts`), inklusive Zeitstempel für jedes Wort.
3. **Bilder:** passende Hochkant-Stock-Videos von Pexels (kostenlos und kommerziell nutzbar).
4. **Schnitt:** ffmpeg setzt alles in 9:16 zusammen, mit großen Wort-für-Wort-Untertiteln und optionaler Musik.
5. **Upload:** YouTube Data API; der Verlauf landet in `data/history.json`.
6. **Zeitplan:** GitHub Actions (kostenlos, kein eigener Server nötig).

Nische, Sprache, Stimme, Länge, Schrift und Uhrzeiten stellst du in `config.toml` und
`.github/workflows/post-short.yml` ein.

## Einrichtung (einmalig, ca. 30 Minuten)

### 1. Anthropic-API-Schlüssel
Unter <https://console.anthropic.com> einen API-Schlüssel anlegen und etwas Guthaben aufladen.
Ein Skript kostet grob 5–15 Cent.

### 2. Pexels-API-Schlüssel
Kostenlos unter <https://www.pexels.com/api/> anfordern.

### 3. YouTube-Zugang
1. In der [Google Cloud Console](https://console.cloud.google.com) ein Projekt anlegen.
2. **APIs & Dienste → Bibliothek → „YouTube Data API v3“** aktivieren.
3. **OAuth-Zustimmungsbildschirm:** Typ „Extern“, dich selbst als Testnutzer eintragen und danach auf
   **„In Produktion“ veröffentlichen**. Sonst läuft der Zugang nach 7 Tagen ab. Die Google-Prüfung
   brauchst du dafür nicht; beim Anmelden erscheint nur eine Warnung, die du überspringen kannst.
4. **Anmeldedaten → OAuth-Client-ID → Anwendungstyp „Desktop-App“** anlegen und die JSON-Datei herunterladen.
5. Auf deinem Rechner:
   ```bash
   pip install google-auth-oauthlib
   python scripts/get_youtube_token.py ~/Downloads/client_secret_XXX.json
   ```
   Mit dem Google-Konto des Kanals anmelden. Das Skript gibt danach drei Werte aus.

### 4. Secrets bei GitHub eintragen
Im Repository unter **Settings → Secrets and variables → Actions** diese fünf Secrets anlegen:

| Name | Wert |
|---|---|
| `ANTHROPIC_API_KEY` | aus Schritt 1 |
| `PEXELS_API_KEY` | aus Schritt 2 |
| `YOUTUBE_CLIENT_ID` | aus Schritt 3 |
| `YOUTUBE_CLIENT_SECRET` | aus Schritt 3 |
| `YOUTUBE_REFRESH_TOKEN` | aus Schritt 3 |

### 5. Testen
**Actions → „Short posten“ → Run workflow** mit Haken bei „Nur erzeugen“. Das fertige Video kannst du danach
unten im Lauf unter *Artifacts* herunterladen und ansehen. Wenn es dir gefällt, läuft der Kanal ab jetzt von
selbst (Standard: 12:17 und 19:47 Uhr). Der Zeitplan startet erst, wenn der Workflow auf dem Standard-Branch liegt.

## Wichtig, bevor es öffentlich läuft

- **Neue API-Projekte laden nur privat hoch.** Google stellt Videos von ungeprüften API-Projekten
  automatisch auf „privat“. Damit sie öffentlich erscheinen, musst du einmal das
  [YouTube-API-Audit](https://support.google.com/youtube/contact/yt_api_form) beantragen. Das ist kostenlos
  und dauert meist einige Tage bis wenige Wochen. Bis dahin kannst du die Videos im YouTube Studio von Hand
  auf öffentlich stellen.
- **Upload-Limit:** Das kostenlose API-Kontingent reicht für etwa 6 Uploads pro Tag. 1–3 pro Tag sind ohnehin sinnvoller.
- **Monetarisierung:** YouTube streicht die Monetarisierung bei massenhaft produzierten, sich wiederholenden
  Inhalten („inauthentic content“). Darum schreibt Claude jedes Video neu, mit eigenem Thema und eigenen Bildern.
  Schau trotzdem regelmäßig rein und variiere die Nische oder den Stil, wenn die Videos zu gleichförmig werden.
- **Keine fremden Videos:** Dieses System lädt bewusst keine viralen Clips anderer Leute erneut hoch. Das
  führt zu Copyright-Strikes, und nach drei Strikes wird der Kanal gelöscht.
- **Viral ist nicht garantiert.** Der Kanal lernt mit: Ab etwa 4 Videos mit Aufrufzahlen sieht Claude, was
  bei deinem Publikum funktioniert. Rechne mit einigen Wochen, bis der Algorithmus den Kanal einordnet.

## Anpassen

- **Nische/Sprache/Zielgruppe:** `config.toml`, Abschnitt `[channel]`.
- **Stimme:** `edge-tts --list-voices` zeigt alle Stimmen; z. B. `de-DE-KatjaNeural` für eine weibliche Stimme.
- **Musik:** lizenzfreie `.mp3`-Dateien in `assets/music/` legen, z. B. aus der YouTube Audio Library.
- **Schrift:** `.ttf`-Datei in `assets/fonts/` legen und den Namen in `config.toml` unter `font` eintragen.
- **Uhrzeiten:** `cron`-Zeilen in `.github/workflows/post-short.yml` (die Zeiten sind in UTC).

## Lokal ausführen

```bash
sudo apt install ffmpeg            # bzw. brew install ffmpeg
pip install -r requirements.txt
export ANTHROPIC_API_KEY=... PEXELS_API_KEY=...
python -m shorts.main --no-upload  # Video landet in build/<zeitstempel>/short.mp4
```
