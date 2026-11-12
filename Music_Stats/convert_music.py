#!/usr/bin/env python3
"""Wandelt Hör-Verläufe von Deezer und Apple Music in eine JSON-Datei für Music_Stats/index.html um.

Aufruf:
    python3 convert_music.py <Datei oder Ordner> [<Datei oder Ordner> ...] [-o Ausgabe.json]

Erkannt werden:
  - Deezer:      deezer-data_listening_*.csv  (Export "Listening history")
  - Apple Music: Apple Music Play Activity.csv (aus dem Datenexport von privacy.apple.com,
                 Ordner "Apple Media Services information"; ZIP vorher entpacken)
Ordner werden rekursiv nach diesen Dateien durchsucht.

Die Ausgabe enthält persönliche Hördaten. Sie gehört NICHT ins Repo -
Standard-Ausgabeort ist deshalb dieser Ordner (per .gitignore ausgeschlossen).
IP-Adressen aus dem Deezer-Export werden nicht übernommen.
"""
import csv
import glob
import json
import os
import sys
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


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(f, delimiter=delim))


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


def parse_apple(path):
    plays = []
    for r in read_csv(path):
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
        plays.append({
            "t": t,
            "title": title,
            "artist": pick(r, "Artist Name", "Container Artist Name", "Artist"),
            "album": pick(r, "Album Name", "Container Album Name"),
            "sec": sec,
            "src": "apple",
            "dev": device_label("", pick(r, "Device Type", "Client Platform", "Device Identifier")) or "Unbekannt",
            "id": pick(r, "Song ID", "Item ID", "Content Specific Type"),
        })
    return plays


def find_files(args):
    files = []
    for a in args:
        if os.path.isdir(a):
            files += glob.glob(os.path.join(a, "**", "deezer-data_listening_*.csv"), recursive=True)
            files += glob.glob(os.path.join(a, "**", "*Play Activity*.csv"), recursive=True)
        elif os.path.isfile(a):
            files.append(a)
        else:
            sys.exit(f"Nicht gefunden: {a}")
    return sorted(set(files))


def main():
    args = sys.argv[1:]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musik_daten.json")
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)

    plays = []
    for f in find_files(args):
        name = os.path.basename(f).lower()
        if name.startswith("deezer"):
            p = parse_deezer(f)
        elif "play activity" in name:
            p = parse_apple(f)
        else:
            print(f"Übersprungen (unbekanntes Format): {f}")
            continue
        print(f"{os.path.basename(f)}: {len(p)} Wiedergaben")
        plays += p
    if not plays:
        sys.exit("Keine Wiedergaben gefunden.")

    # Apple liefert teils keinen Interpreten: über Titel + Album aus den übrigen Daten ergänzen
    known = {}
    for p in plays:
        if p["artist"]:
            known.setdefault((p["title"].lower(), p["album"].lower()), p["artist"])
            known.setdefault((p["title"].lower(), ""), p["artist"])
    for p in plays:
        if not p["artist"]:
            p["artist"] = known.get((p["title"].lower(), p["album"].lower())) \
                or known.get((p["title"].lower(), "")) or "Unbekannt"

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
        # [Zeitpunkt (Unix-Sekunden), Titel-Index, gehörte Sekunden, Quelle (0 Deezer, 1 Apple), Geräte-Index]
        "wiedergaben": rows,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n{len(rows)} Wiedergaben, {len(bands)} Bands, {len(tracks)} Titel -> {out} "
          f"({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
