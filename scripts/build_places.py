#!/usr/bin/env python
"""
Build config/places.yaml — routing landmarks for every supported city.

WHERE THE COORDINATES COME FROM
-------------------------------
OpenStreetMap, via Nominatim. Not from memory.

The names below are well-known localities and landmarks — Bandra, Connaught
Place, Koramangala — which is ordinary knowledge. Their COORDINATES are not,
and typing plausible-looking latitudes for ninety places would produce a file
that looks authoritative and quietly puts routes in the wrong part of the city.
Every coordinate here is resolved by geocoding the name and is whatever OSM
says it is.

WHAT GETS REJECTED
------------------
A name that does not geocode is dropped. A result that lands outside the city's
bounding box is dropped — Nominatim will happily return a same-named place in
another state, and a "Model Town" that resolves to the wrong city is worse than
no entry at all. Every rejection is printed, so the file's coverage is visible
rather than assumed.

USAGE
-----
    python scripts/build_places.py                  # all cities
    python scripts/build_places.py --city mumbai    # one
    python scripts/build_places.py --dry-run        # report, write nothing

Nominatim's usage policy allows one request per second. Roughly ninety names
means about two minutes. Results are cached to data/raw/osm/places_cache.json,
so re-runs are instant and do not hit the service again.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import unicodedata

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.osm_processor import METRO_BBOX  # noqa: E402

OUT = ROOT / "config" / "places.yaml"
CACHE = ROOT / "data" / "raw" / "osm" / "places_cache.json"
FRONTEND = ROOT / "frontend" / "src" / "data" / "mockData.js"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "QRoute/0.1 (SIH PS26137 quantum-inspired route optimizer)"
MIN_INTERVAL_S = 1.1        # Nominatim asks for no more than 1 request/second

CITY_LABELS = {
    "hyderabad": ("Hyderabad", "Telangana"),
    "bengaluru": ("Bengaluru", "Karnataka"),
    "delhi": ("Delhi", "Delhi"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "mumbai": ("Mumbai", "Maharashtra"),
    "pune": ("Pune", "Maharashtra"),
}

# Localities and landmarks people actually name when giving directions. Chosen
# to spread across each city rather than cluster in one quarter, so a route
# between two of them crosses real distance.
CANDIDATES = {
    "hyderabad": [
        "Hitec City", "Gachibowli", "Madhapur", "Kondapur", "Jubilee Hills",
        "Banjara Hills", "Panjagutta", "Ameerpet", "Begumpet", "Secunderabad",
        "Mehdipatnam", "Charminar", "Dilsukhnagar", "Uppal", "Kukatpally",
        "Miyapur", "LB Nagar", "Shamshabad", "Attapur", "Alwal",
    ],
    "bengaluru": [
        "Koramangala", "Indiranagar", "Whitefield", "Electronic City",
        "Jayanagar", "Malleshwaram", "Hebbal", "Marathahalli", "BTM Layout",
        "Rajajinagar", "Banashankari", "Yeshwanthpur", "KR Puram",
        "Bellandur", "HSR Layout", "Basavanagudi", "Yelahanka",
        "Majestic Bangalore", "MG Road Bangalore", "Kengeri",
    ],
    "delhi": [
        "Connaught Place", "Karol Bagh", "Dwarka", "Rohini", "Saket",
        "Hauz Khas", "Lajpat Nagar", "Janakpuri", "Pitampura", "Vasant Kunj",
        "Chandni Chowk", "Nehru Place", "Mayur Vihar", "Shahdara",
        "Okhla", "Munirka", "Model Town Delhi", "Paschim Vihar",
        "Kalkaji", "Narela",
    ],
    "chennai": [
        "T Nagar", "Adyar", "Velachery", "Anna Nagar", "Guindy", "Mylapore",
        "Tambaram", "Porur", "Perungudi", "Egmore", "Nungambakkam",
        "Ambattur", "Chromepet", "Sholinganallur", "Thiruvanmiyur",
        "Vadapalani", "Kodambakkam", "Royapettah", "Avadi", "Pallavaram",
    ],
    "mumbai": [
        "Bandra", "Andheri", "Colaba", "Dadar", "Powai", "Borivali",
        "Goregaon", "Malad", "Chembur", "Ghatkopar", "Worli", "Juhu",
        "Kurla", "Vikhroli", "Mulund", "Santacruz", "Wadala",
        "Marine Lines", "Bhandup", "Kandivali",
    ],
    "pune": [
        "Koregaon Park", "Hinjewadi", "Kothrud", "Viman Nagar", "Baner",
        "Hadapsar", "Aundh", "Wakad", "Kharadi", "Shivajinagar Pune",
        "Camp Pune", "Warje", "Pimpri", "Chinchwad", "Katraj",
        "Magarpatta", "Bavdhan", "Yerwada", "Dhankawadi", "Nigdi",
    ],
}


def slug(city: str, name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    # City-prefixed, because "camp" and "model_town" are not unique across India
    # and a collision would silently overwrite one city's landmark with another's.
    return f"{city}_{base}"


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")


_last_call = 0.0


def geocode(name: str, city: str, cache: dict) -> dict | None:
    """One geocode, bounded to the city and never faster than the usage policy."""
    global _last_call

    key = f"{city}|{name}"
    if key in cache:
        return cache[key]

    lon_min, lat_min, lon_max, lat_max = METRO_BBOX[city]
    label, state = CITY_LABELS[city]

    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()

    try:
        res = requests.get(
            NOMINATIM,
            params={
                "q": f"{name}, {label}, {state}, India",
                "format": "jsonv2",
                "limit": 1,
                # bounded=1 confines the search to the city's box, which is what
                # stops a same-named place in another state coming back.
                "viewbox": f"{lon_min},{lat_max},{lon_max},{lat_min}",
                "bounded": 1,
                "countrycodes": "in",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        res.raise_for_status()
        raw = res.json()
    except Exception as exc:
        print(f"    {name:<24s} geocoder error: {exc}")
        return None

    if not raw:
        cache[key] = None
        return None

    item = raw[0]
    out = {"lat": float(item["lat"]), "lon": float(item["lon"]),
           "display": item.get("display_name", "")}
    cache[key] = out
    return out


def build_city(city: str, cache: dict) -> tuple[dict, list]:
    lon_min, lat_min, lon_max, lat_max = METRO_BBOX[city]
    label = CITY_LABELS[city][0]
    kept, rejected = {}, []

    print(f"\n{label} ({len(CANDIDATES[city])} candidates)")
    for name in CANDIDATES[city]:
        hit = geocode(name, city, cache)
        if not hit:
            rejected.append((name, "not found"))
            continue
        lat, lon = hit["lat"], hit["lon"]
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            rejected.append((name, f"outside the city box ({lat:.4f},{lon:.4f})"))
            continue
        kept[slug(city, name)] = {
            "name": name, "city": city, "label": label,
            "lat": round(lat, 6), "lon": round(lon, 6),
        }
        print(f"    {name:<24s} {lat:.5f}, {lon:.5f}")

    for name, why in rejected:
        print(f"    {name:<24s} REJECTED — {why}")
    return kept, rejected


def write_yaml(places: dict) -> None:
    lines = [
        "# Routing landmarks, one block per city.",
        "#",
        "# GENERATED — do not hand-edit. Rebuild with:",
        "#     python scripts/build_places.py",
        "#",
        "# Every coordinate is resolved from OpenStreetMap by geocoding the name,",
        "# not typed from memory, and every entry was verified to fall inside its",
        "# city's bounding box. Names that did not geocode, or that resolved to a",
        "# same-named place elsewhere in India, were dropped rather than guessed.",
        "#",
        "# Coordinates are [latitude, longitude]. `city` is the key from",
        "# preprocessing/osm_processor.METRO_BBOX.",
        "",
        "places:",
    ]
    by_city: dict[str, list] = {}
    for key, p in places.items():
        by_city.setdefault(p["city"], []).append((key, p))

    for city in CITY_LABELS:
        rows = by_city.get(city)
        if not rows:
            continue
        lines.append(f"  # ── {CITY_LABELS[city][0]} " + "─" * (46 - len(CITY_LABELS[city][0])))
        width = max(len(k) for k, _ in rows) + 1
        for key, p in rows:
            lines.append(
                f"  {key + ':':<{width}} {{ name: {p['name']}, "
                f"city: {p['city']}, lat: {p['lat']}, lon: {p['lon']} }}"
            )
        lines.append("")
    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_frontend(places: dict) -> None:
    """
    Mirror the same coordinates into the frontend constant.

    Both files are written from one geocoding pass because keeping them in sync
    by hand is a losing game: a coordinate that disagrees between the two routes
    to a different place than the label claims, and nothing on screen would show
    the disagreement.
    """
    rows = [
        f"  {{ id: '{k}', name: '{p['name']}', city: '{p['city']}', "
        f"coords: [{p['lat']}, {p['lon']}] }},"
        for k, p in places.items()
    ]
    block = "export const LOCATIONS = [" + chr(10) + chr(10).join(rows) + chr(10) + "]"

    text = FRONTEND.read_text(encoding="utf-8")
    start = text.index("export const LOCATIONS = [")
    end = text.index(chr(10) + "]", start) + 2
    FRONTEND.write_text(text[:start] + block + text[end:], encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", action="append", choices=list(CITY_LABELS),
                    help="only these cities (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    cities = args.city or list(CITY_LABELS)
    cache = load_cache()
    places, all_rejected = {}, []

    for city in cities:
        kept, rejected = build_city(city, cache)
        places.update(kept)
        all_rejected += [(city, n, w) for n, w in rejected]
        save_cache(cache)

    print(f"\n{'=' * 60}")
    print(f"  resolved {len(places)} landmarks across {len(cities)} cities")
    if all_rejected:
        print(f"  dropped  {len(all_rejected)} that could not be verified")
    print(f"{'=' * 60}")

    if args.dry_run:
        print("dry run — nothing written")
        return 0

    write_yaml(places)
    print(f"wrote {OUT}")
    write_frontend(places)
    print(f"wrote {FRONTEND}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
