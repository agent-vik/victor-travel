#!/usr/bin/env python3
"""Resolve cover images for album / blog link cards (hotlink, no download).

- Blog URLs → single cover in covers-cache.json (og:image, else first CDN image).
- Album URLs → first five distinct CDN images in album-thumbs-cache.json (5 equal columns).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "covers-cache.json"
ALBUM_THUMBS_CACHE_PATH = ROOT / "album-thumbs-cache.json"
ALBUM_THUMB_COUNT = 5

UA = "victor-travel-cover-fetch/1.0 (+https://travel.victor42.work/)"
TIMEOUT = 20

OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)["\']'
    r"|<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*(?:property|name)=[\"'](?:og:image|twitter:image)[\"']",
    re.I,
)
CDN_RE = re.compile(
    r"https?://cdn\.victor42\.work/(?:posts|albums)/[^\"'\s<>]+\.(?:webp|jpe?g|png|gif)",
    re.I,
)
SKIP_SUBSTR = (
    "pale-blue-dot",
    "favicon",
    "avatar",
    "logo",
    "/assets/",
)


def _normalize(url: str) -> str:
    url = url.strip().replace("\\/", "/")
    if url.startswith("//"):
        url = "https:" + url
    return url


def _usable(url: str) -> bool:
    low = url.lower()
    if not low.startswith("http"):
        return False
    return not any(s in low for s in SKIP_SUBSTR)


def extract_cover(html: str) -> str | None:
    for m in OG_RE.finditer(html):
        cand = _normalize(m.group(1) or m.group(2) or "")
        if cand and _usable(cand):
            return cand
    for cand in CDN_RE.findall(html):
        cand = _normalize(cand)
        if _usable(cand):
            return cand
    return None


def extract_album_thumbs(html: str, limit: int = ALBUM_THUMB_COUNT) -> list[str]:
    seen: set[str] = set()
    thumbs: list[str] = []
    for cand in CDN_RE.findall(html):
        cand = _normalize(cand)
        if not _usable(cand) or cand in seen:
            continue
        seen.add(cand)
        thumbs.append(cand)
        if len(thumbs) >= limit:
            break
    return thumbs


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    return raw.decode("utf-8", "replace")


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


def load_album_thumbs_cache() -> dict[str, list[str]]:
    if not ALBUM_THUMBS_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(ALBUM_THUMBS_CACHE_PATH.read_text(encoding="utf-8"))
        out: dict[str, list[str]] = {}
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, list):
                continue
            thumbs = [v for v in value if isinstance(v, str) and _usable(v)]
            if thumbs:
                out[key] = thumbs[:ALBUM_THUMB_COUNT]
        return out
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(
        json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_album_thumbs_cache(cache: dict[str, list[str]]) -> None:
    ALBUM_THUMBS_CACHE_PATH.write_text(
        json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_cover(url: str, cache: dict[str, str], *, force: bool = False) -> str | None:
    if not url:
        return None
    if not force and url in cache:
        return cache[url] or None
    try:
        html = fetch_html(url)
        cover = extract_cover(html)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"cover fetch failed {url}: {exc}")
        cover = cache.get(url) or None
        return cover
    if cover:
        cache[url] = cover
    elif url in cache:
        del cache[url]
    return cover


def resolve_album_thumbs(
    url: str, cache: dict[str, list[str]], *, force: bool = False
) -> list[str]:
    if not url:
        return []
    cached = cache.get(url) or []
    if not force and len(cached) >= ALBUM_THUMB_COUNT:
        return cached[:ALBUM_THUMB_COUNT]
    try:
        html = fetch_html(url)
        thumbs = extract_album_thumbs(html)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"album thumbs fetch failed {url}: {exc}")
        return cached[:ALBUM_THUMB_COUNT]
    if thumbs:
        cache[url] = thumbs
    elif url in cache:
        del cache[url]
    return thumbs


def resolve_for_guides(guides: list[dict], *, force: bool = False) -> dict[str, object]:
    """Return blog covers and album thumb grids; updates cache files."""
    cover_cache = load_cache()
    album_cache = load_album_thumbs_cache()
    blog_urls: list[str] = []
    album_urls: list[str] = []
    for g in guides:
        blog = g.get("blog")
        album = g.get("album")
        if blog and blog not in blog_urls:
            blog_urls.append(blog)
        if album and album not in album_urls:
            album_urls.append(album)
    for url in blog_urls:
        resolve_cover(url, cover_cache, force=force)
    for url in album_urls:
        resolve_album_thumbs(url, album_cache, force=force)
        if url not in album_cache:
            resolve_cover(url, cover_cache, force=force)
    save_cache(cover_cache)
    save_album_thumbs_cache(album_cache)
    return {
        "covers": {u: cover_cache[u] for u in blog_urls if u in cover_cache},
        "album_thumbs": {u: album_cache[u] for u in album_urls if u in album_cache},
    }
