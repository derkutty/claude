# Automatischer YouTube-Shorts-Kanal

Erstellt zweimal täglich ein neues Short und lädt es hoch, ohne dass du etwas tun musst.
Dabei testet er drei Formate gegeneinander und konzentriert sich danach auf das erfolgreichste.

| Format | Was passiert | Wer erstellt es |
|---|---|---|
| **Quiz-Rätsel** | 3 Fragen mit je 3 Antworten, Countdown, Auflösung | Claude schreibt alles, das Programm zeichnet das Bild |
| **Emoji-Rätsel** | 4 Filme/Sprichwörter aus Emojis erraten | Claude schreibt alles, das Programm zeichnet das Bild |
| **Fakten mit Videoclips** | Sprecher erzählt verblüffende Fakten zu echten Videoclips | Claude schreibt, die Clips kommen von Pexels |

**So funktioniert der Test:** Die ersten ~2 Wochen wechseln sich die Formate ab. Für jedes Video zählt die
Aufrufzahl **3 Tage nach dem Upload**, damit ältere Videos keinen Vorteil haben. Sobald jedes Format 6
bewertete Videos hat, bekommt das beste Format 80 % der Uploads. Die anderen 20 % testen weiter. Den aktuellen
Stand siehst du jederzeit in [`data/report.md`](data/report.md).

---

## Einrichtung Schritt für Schritt

Du brauchst nichts zu installieren, alles passiert im Browser. Plane etwa 45 Minuten ein.
Halte eine Notiz-App offen: Du sammelst unterwegs **fünf geheime Werte**, die am Ende bei GitHub eingetragen werden.

### Schritt 1: YouTube-Kanal anlegen
1. Auf <https://www.youtube.com> mit deinem Google-Konto anmelden.
2. Oben rechts auf dein Profilbild → **Kanal erstellen**.
3. Einen Namen wählen, der zu Rätseln und Wissen passt (z. B. „Rätselzeit“ oder „Kopfnuss“).

### Schritt 2: Claude-Zugang (Anthropic)
Das ist **nicht** dasselbe wie ein Claude-Abo. Die API wird pro Nutzung bezahlt, etwa 5–15 Cent pro Video.
1. Auf <https://console.anthropic.com> mit deinem Google-Konto anmelden.
2. Links auf **Billing** → Guthaben aufladen. 10 € reichen für viele Wochen.
3. Links auf **API Keys** → **Create Key** → Name „shorts“.
4. Den Schlüssel (beginnt mit `sk-ant-`) **sofort** kopieren und in deine Notiz schreiben als
   `ANTHROPIC_API_KEY`. Er wird nur einmal angezeigt.

### Schritt 3: Pexels-Zugang (optional, nur für das Fakten-Format)
Standardmäßig laufen nur die beiden Rätsel-Formate, die brauchen Pexels nicht. Falls Pexels gerade keine
Schlüssel ausgibt, diesen Schritt einfach überspringen und das Secret `PEXELS_API_KEY` weglassen.
Wer das Fakten-Format nutzen will, trägt danach in `config.toml` bei `formats` zusätzlich `"fakten"` ein.

1. Auf <https://www.pexels.com/de-de/join/> ein Konto anlegen.
2. <https://www.pexels.com/api/> öffnen → **Your API Key** → kurzes Formular ausfüllen
   (Zweck z. B. „YouTube-Shorts mit Stock-Videos“).
3. Den Schlüssel kopieren und notieren als `PEXELS_API_KEY`.

### Schritt 4: Upload-Erlaubnis für YouTube (Google Cloud)
Das ist der längste Schritt. Google will wissen, welches Programm in deinem Namen Videos hochladen darf.

**4a. Projekt anlegen**
1. <https://console.cloud.google.com> öffnen und die Nutzungsbedingungen bestätigen. Es ist kostenlos, eine Kreditkarte ist nicht nötig.
2. Oben links auf **Projekt auswählen** → **Neues Projekt** → Name „shorts-bot“ → **Erstellen**.
   Danach sicherstellen, dass oben das Projekt „shorts-bot“ ausgewählt ist.

**4b. YouTube-API einschalten**
1. Oben in die Suche „YouTube Data API v3“ eingeben und öffnen.
2. **Aktivieren** klicken.

**4c. Zustimmungsbildschirm einrichten**
1. Links im Menü **APIs & Dienste → OAuth-Zustimmungsbildschirm** (heißt teils auch „Google Auth Platform“) → **Jetzt starten**.
2. App-Name „shorts-bot“, deine E-Mail als Support- und Kontakt-Adresse, Zielgruppe **Extern**.
3. Unter **Zielgruppe** auf **App veröffentlichen** → bestätigen. Der Status muss **„In Produktion“** sein,
   sonst funktioniert der Zugang nur 7 Tage.

**4d. Zugangsdaten erstellen**
1. Links **Clients** (bzw. **Anmeldedaten**) → **Client erstellen** / **OAuth-Client-ID**.
2. Anwendungstyp: **Webanwendung**, Name „shorts-bot“.
3. Unter **Autorisierte Weiterleitungs-URIs** → **URI hinzufügen** → genau das eintragen:
   `https://developers.google.com/oauthplayground`
4. **Erstellen**. Jetzt werden *Client-ID* und *Clientschlüssel* angezeigt. Notiere sie als
   `YOUTUBE_CLIENT_ID` und `YOUTUBE_CLIENT_SECRET`.

**4e. Den Dauer-Zugang (Refresh-Token) holen**
1. <https://developers.google.com/oauthplayground> öffnen.
2. Oben rechts auf das **Zahnrad** → Haken bei **Use your own OAuth credentials** → Client-ID und
   Clientschlüssel aus 4d einfügen → Fenster schließen.
3. Links unten in das Feld **Input your own scopes** genau das einfügen:
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly`
4. **Authorize APIs** → mit dem Google-Konto anmelden, dem der YouTube-Kanal gehört, und falls gefragt den Kanal auswählen.
   Bei „Google hat diese App nicht überprüft“ auf **Erweitert → Weiter zu shorts-bot** klicken. Das ist deine
   eigene App, also unbedenklich. Danach alle Haken setzen und **Weiter**.
5. Zurück im Playground: **Exchange authorization code for tokens**.
6. Den **Refresh token** (beginnt meist mit `1//`) kopieren und notieren als `YOUTUBE_REFRESH_TOKEN`.

### Schritt 5: Die fünf Werte bei GitHub eintragen
1. Dieses Repository auf github.com öffnen → oben **Settings** → links **Secrets and variables → Actions**.
2. Für jeden der fünf Werte: **New repository secret** → Name genau wie unten, Wert einfügen → **Add secret**.

| Name | Wert aus |
|---|---|
| `ANTHROPIC_API_KEY` | Schritt 2 |
| `PEXELS_API_KEY` | Schritt 3 |
| `YOUTUBE_CLIENT_ID` | Schritt 4d |
| `YOUTUBE_CLIENT_SECRET` | Schritt 4d |
| `YOUTUBE_REFRESH_TOKEN` | Schritt 4e |

### Schritt 6: Probelauf
1. Im Repository oben auf **Actions** → links **Short posten** → rechts **Run workflow**.
2. Haken bei **Nur erzeugen, nicht hochladen** → grüner Button **Run workflow**.
3. Nach 2–5 Minuten ist der Lauf grün. Draufklicken → unten bei **Artifacts** liegt **short** zum Herunterladen.
   Das ist dein erstes Video.
4. Wenn es dir gefällt, denselben Lauf **ohne** Haken starten. Dann wird wirklich hochgeladen.

Ab jetzt läuft der Kanal von selbst, jeden Tag um 12:17 und 19:47 Uhr.

### Schritt 7: Freischaltung für öffentliche Videos
Google stellt Videos von neuen, ungeprüften API-Projekten **automatisch auf „privat“**. Damit sie von selbst
öffentlich erscheinen, beantragst du einmalig das kostenlose
[YouTube-API-Audit](https://support.google.com/youtube/contact/yt_api_form). Das dauert meist einige Tage bis wenige Wochen.
Bis dahin stellst du die Videos im [YouTube Studio](https://studio.youtube.com) unter **Inhalte** von Hand auf
**Öffentlich**. Das sind zwei Klicks pro Video.

---

## Gut zu wissen

- **Monetarisierung:** YouTube streicht die Monetarisierung bei massenhaft gleichförmigen Inhalten
  („inauthentic content“). Darum schreibt Claude jedes Video neu und die Themen wiederholen sich nicht.
  Schau trotzdem ab und zu rein.
- **Keine fremden Videos:** Das System lädt bewusst keine Clips anderer Leute hoch. Das führt zu
  Copyright-Strikes, und nach drei Strikes wird der Kanal gelöscht.
- **Viral ist nicht garantiert.** Rechne mit einigen Wochen, bis YouTube den Kanal einordnet.
- **Upload-Limit:** Das kostenlose Google-Kontingent reicht für etwa 6 Uploads pro Tag.

## Anpassen (alles in `config.toml`)

- **Nur noch ein Format:** z. B. `formats = ["quiz"]`.
- **Themen:** jeweils `themes = "..."` unter `[formats.quiz]`, `[formats.emoji]`, `[formats.fakten]`.
- **Stimme:** z. B. `de-DE-KatjaNeural` für eine weibliche Stimme.
- **Musik:** lizenzfreie `.mp3`-Dateien in `assets/music/` legen, z. B. aus der YouTube Audio Library.
- **Uhrzeiten:** die `cron`-Zeilen in `.github/workflows/post-short.yml` (in UTC, also 1–2 Stunden früher als deutsche Zeit).

## Für Fortgeschrittene: lokal ausführen

```bash
sudo apt install ffmpeg fonts-noto-color-emoji   # bzw. brew install ffmpeg
pip install -r requirements.txt
export ANTHROPIC_API_KEY=... PEXELS_API_KEY=...
python -m shorts.main --no-upload --format quiz  # Video landet in build/<zeitstempel>/short.mp4
```

Statt des OAuth Playgrounds geht für den Refresh-Token auch `python scripts/get_youtube_token.py client_secret.json`
(dafür einen OAuth-Client vom Typ „Desktop-App“ anlegen).
