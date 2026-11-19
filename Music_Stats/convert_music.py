#!/usr/bin/env python3
"""Wandelt Hör-Verläufe von Deezer und Apple Music in eine JSON-Datei für Music_Stats/index.html um.

Aufruf:
    python3 convert_music.py <Datei oder Ordner> [<Datei oder Ordner> ...] [-o Ausgabe.json]

Erkannt werden:
  - Deezer:      deezer-data_listening_*.csv  (Export "Listening history")
  - Apple Music: der Datenexport von privacy.apple.com ("Informationen zu Apple-Mediendiensten
                 Teil 1 von 2.zip") - die ZIP kann direkt angegeben werden, verschachtelte ZIPs
                 werden im Speicher gelesen. Genutzt werden "Apple Music Play Activity.csv" und,
                 weil darin der Interpret fehlt, "Apple Music Library Tracks.json" sowie
                 "Apple Music - Play History Daily Tracks.csv" und "Apple Music - Container Details.csv"
                 zum Ergänzen der Bands.
Ordner werden rekursiv nach diesen Dateien durchsucht.

Zusätzlich werden für die meistgehörten Bands Link und Bild der Interpreten-Seite bei
Apple Music geholt (iTunes-Suche + Seite music.apple.com; der Browser darf das wegen CORS
nicht selbst). Ergebnisse landen in interpreten_cache.json, spätere Läufe gehen schnell.
Abschalten mit --ohne-bilder.

Die Ausgabe enthält persönliche Hördaten. Sie gehört NICHT ins Repo -
Standard-Ausgabeort ist deshalb dieser Ordner (per .gitignore ausgeschlossen).
IP-Adressen aus dem Deezer-Export werden nicht übernommen.
"""
import csv
import glob
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone

csv.field_size_limit(10_000_000)

# Gerätekennungen -> lesbare Namen
DEVICE_NAMES = {
    "iPhone10_6": "iPhone X", "iPhone10_3": "iPhone X",
    "iPhone11_2": "iPhone XS", "iPhone11_8": "iPhone XR",
    "iPhone12_1": "iPhone 11", "iPhone12_3": "iPhone 11 Pro",
    "iPhone13_2": "iPhone 12", "iPhone13_3": "iPhone 12 Pro",
    "iPhone14_2": "iPhone 13 Pro", "iPhone14_5": "iPhone 13",
    "iPhone15_2": "iPhone 14 Pro", "iPhone15_4": "iPhone 15",
    "iPhone16_1": "iPhone 15 Pro", "iPhone17_1": "iPhone 16 Pro",
    "iPad11_1": "iPad mini", "iPad13_1": "iPad Air", "iPad13_2": "iPad Air",
    "AppleTV6,2": "Apple TV", "AppleTV6_2": "Apple TV",
    "Watch5_9": "Apple Watch",
}
PLATFORM_NAMES = {"electron": "Mac (Desktop-App)", "web": "Browser", "android": "Android",
                  "ios": "iPhone/iPad", "watchos": "Apple Watch"}


def device_label(platform, model):
    model = (model or "").strip()
    if model in DEVICE_NAMES:
        return DEVICE_NAMES[model]
    if model:
        return model.replace("_", ",")
    return PLATFORM_NAMES.get((platform or "").strip().lower(), platform or "Unbekannt")


def read_csv(src):
    """src: Dateipfad oder bereits gelesener Text."""
    text = src if not os.path.isfile(src) else open(src, encoding="utf-8-sig", newline="").read()
    text = text.lstrip("\ufeff")
    sample = text[:4096]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    return list(csv.DictReader(io.StringIO(text, newline=""), delimiter=delim))


def pick(row, *names):
    """Erste vorhandene, nicht-leere Spalte (Apple benennt Spalten gelegentlich um)."""
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            return v.strip()
    return ""


def parse_deezer(path):
    plays = []
    for r in read_csv(path):
        try:
            t = datetime.strptime(r["Date"].strip(), "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
        sec = int(float(r.get("Listening Time") or 0))
        plays.append({
            # Deezer liefert Ortszeit ohne Zeitzone -> als lokale Zeit dieses Rechners lesen.
            # "Date" ist das ENDE der Wiedergabe; Start = Ende - Hördauer.
            # (Offline gehörte Titel tragen alle den Zeitpunkt des späteren Abgleichs.)
            "t": int(t.timestamp()) - sec,
            "title": r.get("Song Title", "").strip(),
            "artist": r.get("Artist", "").strip(),
            "album": r.get("Album Title", "").strip(),
            "sec": sec,
            "src": "deezer",
            "dev": device_label(r.get("Platform Name"), r.get("Platform Model")),
            "id": r.get("ISRC", "").strip(),
        })
    return plays


def parse_iso(s):
    s = s.strip()
    if not s:
        return None
    if s.isdigit():  # Millisekunden seit 1970
        return int(s) // 1000
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


APPLE_DEVICE_TYPES = {"IPHONE": "iPhone", "IPAD": "iPad", "MACINTOSH": "Mac", "APPLETV": "Apple TV",
                      "WATCH": "Apple Watch", "HOMEPOD": "HomePod", "WINDOWS": "Windows", "ANDROID": "Android"}


def apple_device(r):
    m = re.search(r"model/([A-Za-z]+\d+,\d+)", pick(r, "Client Device Name"))
    if m and m.group(1).replace(",", "_") in DEVICE_NAMES:
        return DEVICE_NAMES[m.group(1).replace(",", "_")]
    dt = pick(r, "Device Type").upper()
    return APPLE_DEVICE_TYPES.get(dt, dt.title() if dt else "Unbekannt")


def apple_artist_lookup(library, daily, containers):
    """Play Activity enthält keinen Interpreten: aus Mediathek und Tagesverlauf ergänzen."""
    by_title_album, by_title = {}, defaultdict(Counter)
    for t in library or []:
        title, artist = (t.get("Title") or "").strip(), (t.get("Artist") or "").strip()
        if title and artist:
            by_title_album.setdefault((title.lower(), (t.get("Album") or "").strip().lower()), artist)
            by_title[title.lower()][artist] += 3
    for r in daily or []:
        desc = (r.get("Track Description") or "").strip()
        # "Band - Titel"; Bands mit " - " im Namen: jede Trennstelle als Kandidat
        for m in re.finditer(r" - ", desc):
            artist, title = desc[:m.start()], desc[m.end():]
            by_title[title.lower()][artist] += 1
    # Alben im Verlauf: "Band - Album"
    by_album = defaultdict(Counter)
    for r in containers or []:
        if (r.get("Container Type") or "").upper() == "ALBUM":
            desc = (r.get("Container Description") or "").strip()
            for m in re.finditer(r" - ", desc):
                by_album[desc[m.end():].lower()][desc[:m.start()]] += 1
    def lookup(title, album):
        t = title.lower()
        if (t, album.lower()) in by_title_album:
            return by_title_album[(t, album.lower())]
        c = by_title.get(t) or by_album.get(album.lower())
        return c.most_common(1)[0][0] if c else ""
    return lookup


def parse_apple(src, artist_of=lambda t, a: ""):
    plays = []
    for r in read_csv(src):
        media = pick(r, "Media Type").upper()
        if media and media != "AUDIO":
            continue
        ms = pick(r, "Play Duration Milliseconds", "Play Duration In Milliseconds")
        sec = int(float(ms)) // 1000 if ms else 0
        etype = pick(r, "Event Type").upper()
        # Apple protokolliert Start- und End-Ereignisse; gezählt wird nur, was eine Hördauer hat
        if sec <= 0 or (etype and etype not in ("PLAY_END", "PLAY", "")):
            continue
        t = parse_iso(pick(r, "Event Start Timestamp", "Event Timestamp", "Event Received Timestamp"))
        title = pick(r, "Song Name", "Content Name", "Track Name")
        if t is None or not title:
            continue
        album = pick(r, "Album Name", "Container Album Name")
        plays.append({
            "t": t,
            "title": title,
            "artist": pick(r, "Artist Name", "Artist") or artist_of(title, album) or pick(r, "Container Artist Name"),
            "album": album,
            "sec": sec,
            "src": "apple",
            "dev": apple_device(r),
            "id": pick(r, "Song ID", "Item ID"),
            "pos": int(float(pick(r, "Start Position In Milliseconds") or 0)) // 1000,
        })
    # Apple protokolliert nach Pause/Fortsetzen jedes Stück einzeln: Abschnitte, die mitten im
    # Titel weiterlaufen (Startposition > 0) und an den vorigen Abschnitt desselben Titels
    # anschließen (< 30 min Pause), zählen als eine Wiedergabe.
    plays.sort(key=lambda p: p["t"])
    merged, last = [], {}
    for p in plays:
        key = (p["title"].lower(), p["album"].lower())
        prev = last.get(key)
        if prev is not None and p["pos"] > 1 and p["t"] - (prev["t"] + prev["sec"]) < 1800 \
                and merged and merged[-1] is prev:
            prev["sec"] += p["sec"]
            continue
        merged.append(p)
        last[key] = p
    for p in merged:
        del p["pos"]
    return merged


WANTED = ("deezer-data_listening_", "music play activity", "library tracks.json", "play history daily tracks",
          "container details")


def wanted(name):
    n = os.path.basename(name).lower()
    return any(w in n for w in WANTED) and (n.endswith(".csv") or n.endswith(".json") or n.endswith(".json.zip"))


def zip_members(zf, prefix=""):
    """Gesuchte Dateien aus einer ZIP (auch verschachtelt) als (Name, Text)."""
    for info in zf.infolist():
        name = info.filename
        if name.lower().endswith(".zip") and not name.lower().endswith(".json.zip") or \
                (name.lower().endswith(".json.zip") and wanted(name)):
            with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                yield from zip_members(inner, prefix + name + "/")
        elif wanted(name) and not name.lower().endswith(".zip"):
            yield prefix + name, zf.read(info).decode("utf-8-sig")


def collect(args):
    """Alle gesuchten Dateien als Liste (Name, Text)."""
    out = []
    for a in args:
        if os.path.isdir(a):
            for f in sorted(glob.glob(os.path.join(a, "**", "*"), recursive=True)):
                if f.lower().endswith(".zip"):
                    with zipfile.ZipFile(f) as zf:
                        out += list(zip_members(zf, os.path.basename(f) + "/"))
                elif wanted(f):
                    out.append((f, open(f, encoding="utf-8-sig").read()))
        elif os.path.isfile(a) and a.lower().endswith(".zip"):
            with zipfile.ZipFile(a) as zf:
                out += list(zip_members(zf, os.path.basename(a) + "/"))
        elif os.path.isfile(a):
            out.append((a, open(a, encoding="utf-8-sig").read()))
        else:
            sys.exit(f"Nicht gefunden: {a}")
    return out


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def artist_info(name):
    """{url, img} der Apple-Music-Interpretenseite oder None."""
    term = urllib.parse.quote(name)
    j = json.loads(http_get(f"https://itunes.apple.com/search?entity=musicArtist&limit=5&country=DE&term={term}"))
    res = [x for x in j.get("results", []) if x.get("artistLinkUrl")]
    key = norm(name)
    best = next((x for x in res if norm(x["artistName"]) == key), None) or \
        next((x for x in res if norm(x["artistName"]).startswith(key)), None)
    if not best:
        return None
    url = re.sub(r"[?&]uo=\d+", "", best["artistLinkUrl"])
    img = None
    try:
        m = re.search(r'<meta property="og:image" content="([^"]+)"', http_get(url))
        # Das Bild der Interpretenseite (Bandfoto, sonst zeigt Apple dort ein Album-Cover)
        if m and "/image/thumb/" in m.group(1):
            img = re.sub(r"/\d+x\d+\w*\.(png|jpg|webp)$", "/400x400cc.jpg", m.group(1))
    except Exception:
        pass
    return {"url": url, "img": img}


def fetch_artists(names, cache_path):
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    todo = [n for n in names if norm(n) not in cache]
    if todo:
        print(f"Interpreten-Bilder: {len(todo)} neu abzufragen (ca. {len(todo) * 3.2 / 60:.0f} min) …")
    for i, n in enumerate(todo, 1):
        for attempt in range(3):
            try:
                cache[norm(n)] = artist_info(n)
                break
            except Exception as e:  # 403/429: Apple bremst -> warten und erneut
                time.sleep(20 * (attempt + 1))
        time.sleep(3.2)  # iTunes-Suche erlaubt nur ca. 20 Anfragen pro Minute
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}")
            json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
    return cache


def main():
    args = sys.argv[1:]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musik_daten.json")
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    with_images = "--ohne-bilder" not in args
    args = [a for a in args if a != "--ohne-bilder"]
    if not args:
        sys.exit(__doc__)

    files = collect(args)
    library, daily, containers = [], [], []
    for name, text in files:
        n = os.path.basename(name).lower()
        if "library tracks.json" in n:
            library += json.loads(text)
        elif "play history daily tracks" in n:
            daily += read_csv(text)
        elif "container details" in n:
            containers += read_csv(text)
    artist_of = apple_artist_lookup(library, daily, containers)

    plays = []
    for name, text in files:
        n = os.path.basename(name).lower()
        if n.startswith("deezer"):
            p = parse_deezer(text)
        elif "music play activity" in n:
            p = parse_apple(text, artist_of)
            print(f"  Interpret ergänzt aus Mediathek/Tagesverlauf: {sum(1 for x in p if x['artist'])} von {len(p)}")
        else:
            continue
        print(f"{os.path.basename(name)}: {len(p)} Wiedergaben")
        plays += p
    if not plays:
        sys.exit("Keine Wiedergaben gefunden.")

    # Apple liefert teils keinen Interpreten: über Titel + Album aus den übrigen Daten ergänzen
    known, by_album = {}, defaultdict(Counter)
    for p in plays:
        if p["artist"]:
            known.setdefault((p["title"].lower(), p["album"].lower()), p["artist"])
            known.setdefault((p["title"].lower(), ""), p["artist"])
            if p["album"]:
                by_album[p["album"].lower()][p["artist"]] += 1
    for p in plays:
        if not p["artist"]:
            alb = by_album.get(p["album"].lower()) if p["album"] else None
            p["artist"] = known.get((p["title"].lower(), p["album"].lower())) \
                or known.get((p["title"].lower(), "")) or (alb.most_common(1)[0][0] if alb else "") or "Unbekannt"
    unknown = sum(1 for p in plays if p["artist"] == "Unbekannt")
    if unknown:
        print(f"Ohne Interpret (als „Unbekannt“): {unknown} Wiedergaben")

    # Vereinzelte Ausreißer ganz am Anfang entfernen (Deezer enthält z. B. einen einzelnen
    # Eintrag fast 5 Jahre vor allen anderen): höchstens 5 Einträge, danach > 180 Tage Pause
    # (je Quelle prüfen, da die andere Quelle früher beginnen kann)
    kept = []
    for src in ("deezer", "apple"):
        ps = sorted((p for p in plays if p["src"] == src), key=lambda p: p["t"])
        for i in range(min(5, len(ps) - 1)):
            if ps[i + 1]["t"] - ps[i]["t"] > 180 * 86400:
                for p in ps[:i + 1]:
                    print(f"Ausreißer entfernt: {datetime.fromtimestamp(p['t']):%d.%m.%Y} "
                          f"{p['artist']} – {p['title']} ({p['src']})")
                ps = ps[i + 1:]
                break
        kept += ps
    plays = sorted(kept, key=lambda p: p["t"])

    # Doppelte Einträge (gleicher Zeitpunkt, gleicher Titel) entfernen
    seen, unique = set(), []
    for p in sorted(plays, key=lambda p: p["t"]):
        key = (p["t"], p["id"] or p["title"].lower(), p["src"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    # Kompakt speichern: Bands, Titel und Geräte als Listen, Wiedergaben verweisen per Index.
    # Gleiche Band in anderer Schreibweise (Groß/Klein) wird zusammengeführt.
    bands, band_idx = [], {}
    tracks, track_idx = [], {}
    devices, dev_idx = [], {}
    sources = ["deezer", "apple"]
    rows = []
    for p in unique:
        bk = p["artist"].lower()
        if bk not in band_idx:
            band_idx[bk] = len(bands)
            bands.append(p["artist"])
        b = band_idx[bk]
        tk = (b, p["title"].lower())
        if tk not in track_idx:
            track_idx[tk] = len(tracks)
            tracks.append([p["title"], b, p["album"]])
        if p["dev"] not in dev_idx:
            dev_idx[p["dev"]] = len(devices)
            devices.append(p["dev"])
        rows.append([p["t"], track_idx[tk], p["sec"], sources.index(p["src"]), dev_idx[p["dev"]]])

    # Link + Bild für die meistgehörten Bands (gesamt und je Monat), Index -> {url, img}
    artists = {}
    if with_images:
        plays_per_band, per_month = Counter(), defaultdict(Counter)
        for r in rows:
            if r[2] >= 30:
                b = tracks[r[1]][1]
                plays_per_band[b] += 1
                per_month[datetime.fromtimestamp(r[0]).strftime("%Y-%m")][b] += 1
        top = {b for b, _ in plays_per_band.most_common(200)}
        for c in per_month.values():
            top |= {b for b, _ in c.most_common(3)}
        top.discard(band_idx.get("unbekannt"))
        cache = fetch_artists([bands[b] for b in sorted(top)], os.path.join(os.path.dirname(out), "interpreten_cache.json"))
        for b in top:
            hit = cache.get(norm(bands[b]))
            if hit:
                artists[str(b)] = hit
        print(f"Interpreten mit Apple-Music-Link: {len(artists)}, davon mit Bild: {sum(1 for a in artists.values() if a.get('img'))}")

    def span(src):
        ts = [p["t"] for p in unique if p["src"] == src]
        if not ts:
            return None
        fmt = lambda t: datetime.fromtimestamp(t).strftime("%d.%m.%Y")
        return {"von": fmt(min(ts)), "bis": fmt(max(ts)), "eintraege": len(ts)}

    data = {
        "erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quellen": {s: span(s) for s in sources if span(s)},
        "bands": bands,
        "titel": tracks,
        "geraete": devices,
        "interpreten": artists,
        # [Zeitpunkt (Unix-Sekunden), Titel-Index, gehörte Sekunden, Quelle (0 Deezer, 1 Apple), Geräte-Index]
        "wiedergaben": rows,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n{len(rows)} Wiedergaben, {len(bands)} Bands, {len(tracks)} Titel -> {out} "
          f"({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
