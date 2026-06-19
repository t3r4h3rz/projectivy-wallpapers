"""
Genera wallpapers.json en formato Overflight a partir de:
- Por defecto: TMDB now_playing (peliculas) + on_the_air (series)
- Opcional: una lista de Trakt, si defines TRAKT_CLIENT_ID + TRAKT_LIST_USER + TRAKT_LIST_SLUG

Pensado para correr una sola vez por ejecucion (no es un servidor),
disparado por un cron de GitHub Actions.
"""
import os
import sys
import json
import time
import requests

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
TRAKT_CLIENT_ID = os.environ.get("TRAKT_CLIENT_ID", "")
TRAKT_LIST_USER = os.environ.get("TRAKT_LIST_USER", "")
TRAKT_LIST_SLUG = os.environ.get("TRAKT_LIST_SLUG", "")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", 30))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "wallpapers.json")

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/original"
TRAKT_BASE = "https://api.trakt.tv"


def tmdb_get(path, params=None):
    params = dict(params or {})
    params["api_key"] = TMDB_API_KEY
    r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def entry_from_tmdb_item(item, media_type):
    backdrop_path = item.get("backdrop_path")
    if not backdrop_path:
        return None
    title = item.get("title") or item.get("name") or "Sin titulo"
    date = item.get("release_date") or item.get("first_air_date") or ""
    overview = item.get("overview", "")
    return {
        "title": f"{title} ({date[:4]})" if date else title,
        "location": (overview[:200] + "...") if len(overview) > 200 else overview,
        "author": "TMDB",
        "url_img": f"{TMDB_IMG_BASE}{backdrop_path}",
    }


def fetch_from_tmdb():
    entries = []
    movies = tmdb_get("/movie/now_playing", {"language": "es-ES", "page": 1}).get("results", [])
    for m in movies[:MAX_ITEMS // 2]:
        e = entry_from_tmdb_item(m, "movie")
        if e:
            entries.append(e)

    shows = tmdb_get("/tv/on_the_air", {"language": "es-ES", "page": 1}).get("results", [])
    for s in shows[:MAX_ITEMS // 2]:
        e = entry_from_tmdb_item(s, "tv")
        if e:
            entries.append(e)

    return entries


def trakt_headers():
    return {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": TRAKT_CLIENT_ID,
    }


def fetch_from_trakt_list():
    url = f"{TRAKT_BASE}/users/{TRAKT_LIST_USER}/lists/{TRAKT_LIST_SLUG}/items"
    r = requests.get(url, headers=trakt_headers(), timeout=15)
    r.raise_for_status()
    items = r.json()[:MAX_ITEMS]

    entries = []
    for item in items:
        media_type = item.get("type")
        media = item.get(media_type) or {}
        tmdb_id = media.get("ids", {}).get("tmdb")
        if not tmdb_id:
            continue
        path = f"/movie/{tmdb_id}" if media_type == "movie" else f"/tv/{tmdb_id}"
        try:
            details = tmdb_get(path, {"language": "es-ES"})
        except Exception as e:
            print(f"Aviso: fallo TMDB para {tmdb_id}: {e}", file=sys.stderr)
            continue
        e = entry_from_tmdb_item(details, media_type)
        if e:
            entries.append(e)
        time.sleep(0.25)
    return entries


def main():
    if not TMDB_API_KEY:
        print("Falta TMDB_API_KEY", file=sys.stderr)
        sys.exit(1)

    use_trakt = TRAKT_CLIENT_ID and TRAKT_LIST_USER and TRAKT_LIST_SLUG
    entries = fetch_from_trakt_list() if use_trakt else fetch_from_tmdb()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Listo: {len(entries)} items escritos en {OUTPUT_FILE} (fuente: {'Trakt' if use_trakt else 'TMDB'})")


if __name__ == "__main__":
    main()
