#!/usr/bin/env python3
"""Wandelt den Apple-Health-Export in eine JSON-Datei für Fitness_Stats/index.html um.

Aufruf:
    python3 convert_fitness.py <Ordner mit export.xml | export.xml | Export.zip> [-o Ausgabe.json]

Übernommen werden Crosstrainer-, Lauf- (outdoor und indoor) und Geh-Trainings mit:
  - Kennzahlen des Trainings (Dauer, Distanz, Kalorien, Herzfrequenz, Laufleistung, Höhenmeter, Wetter …)
  - Zeitreihen in 10-Sekunden-Schritten: Herzfrequenz, zurückgelegte Distanz, Laufleistung
  - GPS-Strecke (aus workout-routes/*.gpx, vereinfacht)
  - Verlauf von Ruhepuls und VO2max als Hintergrund

Der Export enthält Gesundheitsdaten. Die Ausgabe gehört NICHT ins Repo -
Standard-Ausgabeort ist dieser Ordner (per .gitignore ausgeschlossen).
"""
import io
import json
import math
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from bisect import bisect_right
from datetime import datetime, timezone

TYPES = {
    "HKWorkoutActivityTypeElliptical": "cross",
    "HKWorkoutActivityTypeRunning": "run",
    "HKWorkoutActivityTypeWalking": "walk",
}
STEP = 10  # Sekunden pro Zeitreihen-Punkt

# Messwerte, die während eines Trainings als Zeitreihe gesammelt werden
SERIES = {
    "HKQuantityTypeIdentifierHeartRate": "hr",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "dist",
    "HKQuantityTypeIdentifierRunningPower": "pow",
}
# Messwerte für den Langzeit-Verlauf (ein Wert pro Tag)
DAILY = {
    "HKQuantityTypeIdentifierRestingHeartRate": "ruhepuls",
    "HKQuantityTypeIdentifierVO2Max": "vo2max",
}
# Workout-Statistiken (neuere Exporte) -> Feldname, Aggregat
STATS = {
    "HKQuantityTypeIdentifierHeartRate": [("hrAvg", "average"), ("hrMin", "minimum"), ("hrMax", "maximum")],
    "HKQuantityTypeIdentifierActiveEnergyBurned": [("kcal", "sum")],
    "HKQuantityTypeIdentifierBasalEnergyBurned": [("kcalBasal", "sum")],
    "HKQuantityTypeIdentifierDistanceWalkingRunning": [("distStat", "sum")],
    "HKQuantityTypeIdentifierStepCount": [("steps", "sum")],
    "HKQuantityTypeIdentifierRunningPower": [("powAvg", "average"), ("powMax", "maximum")],
    "HKQuantityTypeIdentifierRunningSpeed": [("speedAvg", "average"), ("speedMax", "maximum")],
    "HKQuantityTypeIdentifierRunningStrideLength": [("stride", "average")],
    "HKQuantityTypeIdentifierRunningGroundContactTime": [("gct", "average")],
    "HKQuantityTypeIdentifierRunningVerticalOscillation": [("vosc", "average")],
}


def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


def ts(s):
    return parse_time(s).timestamp()


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def unit_value(text):
    """'123 cm' / '68 degF' / '6500 %' -> (Zahl, Einheit)"""
    if not text:
        return None, ""
    parts = text.strip().split(" ", 1)
    return num(parts[0]), parts[1] if len(parts) > 1 else ""


def to_km(value, unit):
    if value is None:
        return None
    return {"km": 1, "m": 0.001, "mi": 1.609344, "yd": 0.0009144, "ft": 0.0003048}.get(unit, 1) * value


def to_kcal(value, unit):
    if value is None:
        return None
    return value / 4.184 if unit == "kJ" else value


def open_export(path):
    """Gibt (Datei-Objekt für export.xml, Funktion zum Lesen von GPX-Dateien) zurück."""
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        # deutsche Exporte heißen "Export.xml"; export_cda.xml ist ein anderes Format
        xml_name = next(n for n in z.namelist() if n.lower().endswith("/export.xml") or n.lower() == "export.xml")
        root = xml_name[: -len("export.xml")]

        def read_gpx(rel):
            name = root + rel.lstrip("/")
            return z.read(name) if name in z.namelist() else None
        return lambda: z.open(xml_name), read_gpx
    if os.path.isdir(path):
        for base, _, files in os.walk(path):
            found = [f for f in files if f.lower() == "export.xml"]
            if found:
                path = os.path.join(base, found[0])
                break
        else:
            sys.exit("Keine export.xml gefunden.")
    folder = os.path.dirname(os.path.abspath(path))

    def read_gpx(rel):
        p = os.path.join(folder, rel.lstrip("/"))
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f.read()
        return None
    return lambda: open(path, "rb"), read_gpx


def top_elements(opener):
    """Alle Elemente direkt unter <HealthData> nacheinander; danach wird der Baum geleert,
    damit auch Exporte mit mehreren GB nicht den Speicher füllen."""
    depth, root = 0, None
    for event, el in ET.iterparse(opener(), events=("start", "end")):
        if event == "start":
            if root is None:
                root = el
            depth += 1
            continue
        depth -= 1
        if depth == 1:
            yield el
            root.clear()


def read_workouts(opener):
    workouts = []
    for el in top_elements(opener):
        if el.tag != "Workout":
            continue
        kind = TYPES.get(el.get("workoutActivityType"))
        if kind:
            w = {
                "kind": kind,
                "start": ts(el.get("startDate")),
                "end": ts(el.get("endDate")),
                "dur": None,
                "source": el.get("sourceName", ""),
                "device": "",
            }
            d = num(el.get("duration"))
            if d is not None:
                w["dur"] = d * {"min": 60, "s": 1, "hr": 3600}.get(el.get("durationUnit"), 60)
            # ältere Exporte: Summen direkt am Workout
            w["distTot"] = to_km(num(el.get("totalDistance")), el.get("totalDistanceUnit"))
            w["kcalTot"] = to_kcal(num(el.get("totalEnergyBurned")), el.get("totalEnergyBurnedUnit"))
            dev = el.get("device") or ""
            if "name:" in dev:
                w["device"] = dev.split("name:", 1)[1].split(",", 1)[0].strip()
            meta, pauses, laps = {}, [], []
            route = None
            for c in el:
                if c.tag == "MetadataEntry":
                    meta[c.get("key")] = c.get("value")
                elif c.tag == "WorkoutStatistics":
                    for field, agg in STATS.get(c.get("type"), []):
                        v = num(c.get(agg))
                        if v is None:
                            continue
                        u = c.get("unit", "")
                        if field == "distStat":
                            v = to_km(v, u)
                        elif field.startswith("kcal"):
                            v = to_kcal(v, u)
                        elif field == "gct" and u == "s":
                            v *= 1000
                        elif field == "vosc" and u == "m":
                            v *= 100
                        elif field == "stride" and u == "cm":
                            v /= 100
                        elif field.startswith("speed") and u == "km/hr":
                            v /= 3.6
                        w[field] = v
                elif c.tag == "WorkoutEvent":
                    et = c.get("type", "")
                    if et in ("HKWorkoutEventTypePause", "HKWorkoutEventTypeMotionPaused"):
                        pauses.append(["p", ts(c.get("date"))])
                    elif et in ("HKWorkoutEventTypeResume", "HKWorkoutEventTypeMotionResumed"):
                        pauses.append(["r", ts(c.get("date"))])
                    elif et == "HKWorkoutEventTypeLap":
                        laps.append(ts(c.get("date")))
                elif c.tag == "WorkoutRoute":
                    for f in c.iter("FileReference"):
                        route = f.get("path")
            indoor = meta.get("HKIndoorWorkout")
            if kind == "run":
                w["kind"] = "run_in" if indoor == "1" else "run_out"
            elev, eu = unit_value(meta.get("HKElevationAscended"))
            if elev is not None:
                w["elev"] = elev / 100 if eu == "cm" else elev * 0.3048 if eu == "ft" else elev
            mets, _ = unit_value(meta.get("HKAverageMETs"))
            if mets is not None:
                w["mets"] = mets
            temp, tu = unit_value(meta.get("HKWeatherTemperature"))
            if temp is not None:
                w["temp"] = (temp - 32) * 5 / 9 if tu == "degF" else temp
            hum, _ = unit_value(meta.get("HKWeatherHumidity"))
            if hum is not None:
                w["hum"] = hum / 100 if hum > 100 else hum
            w["route"] = route
            w["pauses"] = pauses
            workouts.append(w)
    return workouts


def collect_series(opener, workouts):
    """Zweiter Durchlauf: Messwerte innerhalb der Trainingszeiten + Tageswerte."""
    workouts.sort(key=lambda w: w["start"])
    starts = [w["start"] for w in workouts]
    # Im Export können Geräte anderer Personen stecken (geteilte Health-Daten, mehrere iPhones).
    # Gezählt wird nur, was die Uhr aufgezeichnet hat, mit der das Training lief -
    # sonst wird z. B. die Distanz von iPhone und Uhr doppelt addiert.
    main_source = max(set(w["source"] for w in workouts), key=[w["source"] for w in workouts].count)
    for w in workouts:
        w["_raw"] = {k: [] for k in SERIES.values()}
    daily = {k: {} for k in DAILY.values()}
    for el in top_elements(opener):
        if el.tag != "Record":
            continue
        typ = el.get("type")
        if typ not in DAILY and typ not in SERIES:
            continue
        src = el.get("sourceName", "")
        if typ in DAILY:
            if src != main_source:
                continue
            v = num(el.get("value"))
            if v is not None:
                day = el.get("startDate")[:10]
                daily[DAILY[typ]].setdefault(day, []).append(v)
        elif typ in SERIES:
            t0, t1 = ts(el.get("startDate")), ts(el.get("endDate"))
            i = bisect_right(starts, t1) - 1
            # Messwerte können zwei Trainings überlappen -> rückwärts prüfen
            while i >= 0 and workouts[i]["end"] + 60 >= t0:
                w = workouts[i]
                if src == w["source"] and w["start"] - 5 <= t1 and t0 <= w["end"] + 5:
                    v = num(el.get("value"))
                    if v is not None:
                        key = SERIES[typ]
                        if key == "dist":
                            v = to_km(v, el.get("unit")) * 1000  # Meter
                        w["_raw"][key].append((t0, t1, v))
                    break
                i -= 1
    return {k: sorted([d, round(sum(v) / len(v), 1)] for d, v in days.items()) for k, days in daily.items()}


def build_series(w):
    """Rohwerte -> gleichmäßige Zeitreihen (Offset in Sekunden ab Start, alle STEP Sekunden)."""
    n = int(math.ceil((w["end"] - w["start"]) / STEP)) + 1
    out = {}
    hr = w["_raw"]["hr"]
    if hr:
        buckets = [[] for _ in range(n)]
        for t0, _, v in hr:
            i = int((t0 - w["start"]) // STEP)
            if 0 <= i < n:
                buckets[i].append(v)
        # kurze Messlücken (bis 30 s) mit dem letzten Wert füllen, längere offen lassen
        vals, last, gap = [], None, 0
        for b in buckets:
            if b:
                last, gap = round(sum(b) / len(b)), 0
            else:
                gap += 1
            vals.append(last if gap <= 3 else None)
        out["hr"] = vals
    pw = w["_raw"]["pow"]
    if pw:
        buckets = [[] for _ in range(n)]
        for t0, _, v in pw:
            i = int((t0 - w["start"]) // STEP)
            if 0 <= i < n:
                buckets[i].append(v)
        out["pow"] = [round(sum(b) / len(b)) if b else None for b in buckets]
    dist = w["_raw"]["dist"]
    if dist:
        # kumulierte Distanz: jedes Intervall gleichmäßig über seine Dauer verteilt
        cum = [0.0] * n
        for t0, t1, v in dist:
            a, b = t0 - w["start"], max(t1, t0 + 0.001) - w["start"]
            rate = v / (b - a)
            for i in range(max(0, int(a // STEP)), min(n - 1, int(b // STEP)) + 1):
                lo, hi = max(a, i * STEP), min(b, (i + 1) * STEP)
                if hi > lo:
                    cum[i] += rate * (hi - lo)
        acc, vals = 0.0, []
        for c in cum:
            acc += c
            vals.append(round(acc, 1))
        out["dist"] = vals
    return out


def parse_gpx(data, start):
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    pts = []
    for p in root.iter(f"{ns}trkpt"):
        lat, lon = float(p.get("lat")), float(p.get("lon"))
        ele = p.find(f"{ns}ele")
        tm = p.find(f"{ns}time")
        t = None
        if tm is not None and tm.text:
            t = datetime.fromisoformat(tm.text.replace("Z", "+00:00")).timestamp() - start
        pts.append((lat, lon, float(ele.text) if ele is not None else None, t))
    if len(pts) < 2:
        return None
    # vereinfachen: nur Punkte mit mind. 15 m Abstand zum vorherigen
    keep, last = [], None
    for p in pts:
        if last is None or haversine(last, p) >= 15:
            keep.append(p)
            last = p
    if keep[-1] is not pts[-1]:
        keep.append(pts[-1])
    return [[round(lat, 5), round(lon, 5), None if e is None else round(e, 1), None if t is None else round(t)]
            for lat, lon, e, t in keep]


def haversine(a, b):
    r = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def main():
    args = sys.argv[1:]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitness_daten.json")
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    opener, read_gpx = open_export(args[0])

    print("Lese Trainings …")
    workouts = read_workouts(opener)
    if not workouts:
        sys.exit("Keine Crosstrainer-, Lauf- oder Geh-Trainings gefunden.")
    print(f"{len(workouts)} Trainings gefunden. Lese Messwerte (das dauert bei großen Exporten etwas) …")
    daily = collect_series(opener, workouts)

    result = []
    for w in workouts:
        series = build_series(w)
        dist_km = w.get("distStat") or w.get("distTot")
        if not dist_km and series.get("dist"):
            dist_km = series["dist"][-1] / 1000
        item = {
            "start": int(w["start"]),
            "end": int(w["end"]),
            "art": w["kind"],
            "dauer": round(w["dur"] or (w["end"] - w["start"])),
            "km": round(dist_km, 3) if dist_km else None,
            "kcal": round(w.get("kcal") or w.get("kcalTot") or 0) or None,
        }
        for k in ("hrAvg", "hrMin", "hrMax", "powAvg", "powMax", "speedAvg", "speedMax",
                  "stride", "gct", "vosc", "steps", "elev", "mets", "temp", "hum"):
            if w.get(k) is not None:
                item[k] = round(w[k], 2)
        # Ø/Max-Herzfrequenz aus der Zeitreihe, falls die Statistik fehlt (ältere Exporte)
        hr = [v for v in series.get("hr", []) if v]
        if hr and "hrAvg" not in item:
            item["hrAvg"], item["hrMax"], item["hrMin"] = round(sum(hr) / len(hr)), max(hr), min(hr)
        if w["device"]:
            item["geraet"] = w["device"]
        # Ausreißer markieren (die Seite blendet sie standardmäßig aus)
        # Gehen darf lang dauern (Ausflüge) - nur wenn es dabei kaum vorangeht, ist es verdächtig
        slow_walk = w["kind"] == "walk" and (not item["km"] or item["dauer"] / item["km"] > 45 * 60)
        if item["dauer"] > 3 * 3600 and (w["kind"] != "walk" or slow_walk):
            item["verdacht"] = "lang"  # vermutlich vergessen, das Training zu beenden
        elif w["kind"] == "walk" and item["km"] and item["km"] > 0.5 and item["dauer"] / item["km"] < 7 * 60:
            item["verdacht"] = "fahrzeug"  # schneller als 7 min/km "gehend": lief im Auto/Zug weiter
        if w["pauses"]:
            item["pausen"] = [[k, int(t - w["start"])] for k, t in w["pauses"]]
        if series:
            item["reihen"] = series
        if w["route"]:
            gpx = read_gpx(w["route"])
            if gpx:
                route = parse_gpx(gpx, w["start"])
                if route:
                    item["strecke"] = route
        result.append(item)

    data = {
        "erstellt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schritt": STEP,
        "trainings": result,
        "verlauf": daily,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    counts = {}
    for w in result:
        counts[w["art"]] = counts.get(w["art"], 0) + 1
    print(f"\n{len(result)} Trainings {counts} -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
