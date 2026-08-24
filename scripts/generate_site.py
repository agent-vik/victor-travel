#!/usr/bin/env python3
"""Generate static travel portal.

Data flow (guide wins; data.json never overrides guide)
-------------------------------------------------------
guides/*.md   Source of truth for itinerary body.
              Chinese filename = Chinese title.
              Plain Markdown only (no frontmatter).
              No album / blog links inside.

data.json     Additive portal metadata only:
              file, slug, emoji, title.en, summary, duration.en,
              order, optional album/blog/updated.
              Must not restate or override body facts
              (dates, hotels, transport, duration.zh, title.zh, …).

generate_site.py joins them → index.html, trip/{slug}/, trip/{slug}/{slug}.docx + {slug}_en.docx, sitemap.xml
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import markdown

from guide_docx import write_guide_docx
from guide_render import guide_to_html
from fetch_covers import resolve_for_guides

ROOT = Path(__file__).resolve().parents[1]
GUIDES_DIR = ROOT / "guides"
GUIDES_EN_DIR = GUIDES_DIR / "en"
DATA_PATH = ROOT / "data" / "data.json"
TRIP_DIR = ROOT / "trip"
ASSET_VERSION = "20260824t"
SITE_NAME = "Victor42 · Travel Guides"
TRIP_PREFIX = "trip"

# duration like （4天3晚） or （4天5夜） inside the guide body
DURATION_ZH_RE = re.compile(r"（(\d+天\d+[晚夜])）")


SITE = {
    "origin": "https://travel.victor42.work",
    "parentSite": "https://victor42.work/",
    "parentLabel": {"zh": "小玩意", "en": "Gadgets"},
    "github": "https://github.com/greenzorro/victor-travel",
    "albumHome": "https://album.victor42.work/",
    "blogHome": "https://victor42.eth.limo/",
}

GUIDE_METHOD_POST = {
    "zh": "https://victor42.eth.limo/post/3642/",
    "en": "https://victor42.eth.limo/post-en/3642/",
}
GUIDE_METHOD_TITLE = {
    "zh": "手把手教你制作旅行攻略",
    "en": "A Hands-On Guide to Building Travel Itineraries",
}


TITLE = {
    "zh": "Victor42 · 旅行攻略",
    "en": "Victor42 · Travel Guides",
}

DESCRIPTION = {
    "zh": "历次出行前写好的详细行程：每天去哪、住哪、怎么走，附检查清单；部分攻略带有详细的游记长文与旅行相册。",
    "en": "Detailed itineraries written before each trip—where to go each day, where to stay, how to get around—plus checklists; some guides link to full travelogues and photo albums.",
}


LIST_ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+")
TASK_LI_OPEN_RE = re.compile(r"<li>\s*\[([ xX])\]\s*")


def pick(obj: dict | str | None, lang: str) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return obj.get(lang) or obj.get("zh") or ""


def duration_zh_from_body(body: str) -> str:
    match = DURATION_ZH_RE.search(body)
    return match.group(1) if match else ""


def load_guides() -> list[dict]:
    if not DATA_PATH.exists():
        raise SystemExit(f"missing {DATA_PATH.name}")
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    entries = payload.get("guides") or []
    if not entries:
        raise SystemExit("data.json: guides array is empty")

    guides: list[dict] = []
    for entry in entries:
        filename = entry.get("file")
        slug = entry.get("slug")
        if not filename or not slug:
            raise SystemExit(f"data.json entry missing file/slug: {entry!r}")

        # Reject additive-file attempts to own guide-sourced fields
        title_meta = entry.get("title") or {}
        if isinstance(title_meta, dict) and title_meta.get("zh"):
            raise SystemExit(
                f"{filename}: data.json must not set title.zh "
                "(Chinese title comes from the guide filename)"
            )
        duration_meta = entry.get("duration") or {}
        if isinstance(duration_meta, dict) and duration_meta.get("zh"):
            raise SystemExit(
                f"{filename}: data.json must not set duration.zh "
                "(Chinese duration is parsed from the guide body)"
            )

        path = GUIDES_DIR / filename
        if not path.exists():
            raise SystemExit(f"data.json points to missing guide: {filename}")
        body = path.read_text(encoding="utf-8").strip() + "\n"
        if body.startswith("---"):
            raise SystemExit(
                f"{filename}: guide source must be plain Markdown without frontmatter"
            )

        title_zh = Path(filename).stem
        duration_zh = duration_zh_from_body(body)
        title_en = pick(entry.get("title"), "en")
        duration_en = pick(entry.get("duration"), "en")

        guide = {
            "file": filename,
            "slug": slug,
            "emoji": entry.get("emoji") or "✈️",
            "title": {"zh": title_zh, "en": title_en},
            "summary": entry.get("summary") or {},
            "duration": {"zh": duration_zh, "en": duration_en},
            "order": entry.get("order", 999),
            "body": body,
        }
        en_path = GUIDES_EN_DIR / f"{slug}.md"
        if en_path.exists():
            body_en = en_path.read_text(encoding="utf-8").strip() + "\n"
            if body_en.startswith("---"):
                raise SystemExit(
                    f"{en_path.name}: English guide must be plain Markdown without frontmatter"
                )
            guide["body_en"] = body_en
        if entry.get("album"):
            guide["album"] = entry["album"]
        if entry.get("blog"):
            guide["blog"] = entry["blog"]
        if entry.get("updated"):
            guide["updated"] = entry["updated"]
        guides.append(guide)

    guides.sort(key=lambda g: (g.get("order", 999), g["slug"]))
    return guides


def normalize_markdown_lists(text: str) -> str:
    """Blank line before lists that follow a non-list line (notebook style)."""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if (
            LIST_ITEM_RE.match(line)
            and out
            and out[-1].strip()
            and not LIST_ITEM_RE.match(out[-1])
        ):
            out.append("")
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def enhance_task_list_html(html_text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        checked = match.group(1).lower() == "x"
        attrs = ' type="checkbox" disabled'
        if checked:
            attrs += " checked"
        return f'<li class="task-item"><input{attrs}> '

    return TASK_LI_OPEN_RE.sub(repl, html_text)


def md_to_html(text: str) -> str:
    rendered = markdown.markdown(
        normalize_markdown_lists(text),
        extensions=["extra", "sane_lists", "tables"],
        output_format="html5",
    )
    return enhance_task_list_html(rendered)


def hreflang_for(url: str) -> str:
    safe = escape(url)
    return "\n    ".join(
        [
            f'<link rel="alternate" hreflang="zh-CN" href="{safe}">',
            f'<link rel="alternate" hreflang="en" href="{safe}">',
            f'<link rel="alternate" hreflang="x-default" href="{safe}">',
        ]
    )


def theme_boot_script() -> str:
    return """
    <script>
    (function() {
        const urlParams = new URLSearchParams(window.location.search);
        const urlTheme = urlParams.get('theme');
        if (urlTheme === 'dark' || urlTheme === 'light') {
            localStorage.setItem('theme', urlTheme);
        }
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = savedTheme || (prefersDark ? 'dark' : 'light');
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    })();
    </script>
""".strip()


def render_link_cards(
    guide: dict,
    covers: dict[str, str] | None = None,
    album_thumbs: dict[str, list[str]] | None = None,
) -> str:
    """Optional portal-side links from data.json — never from the guide md."""
    covers = covers or {}
    album_thumbs = album_thumbs or {}
    cards: list[str] = []

    def thumb_single(cover: str) -> str:
        return (
            f'<span class="link-card-thumb">'
            f'<img src="{html.escape(cover)}" alt="" loading="lazy" '
            f'referrerpolicy="no-referrer" decoding="async">'
            f"</span>"
        )

    def thumb_grid(images: list[str]) -> str:
        cells: list[str] = []
        for img in images[:5]:
            cells.append(
                '<span class="link-card-thumb-cell">'
                f'<img src="{html.escape(img)}" alt="" loading="lazy" '
                f'referrerpolicy="no-referrer" decoding="async">'
                "</span>"
            )
        return f'<span class="link-card-thumb link-card-thumb-grid">{"".join(cells)}</span>'

    def card(
        url: str,
        label_zh: str,
        label_en: str,
        *,
        cover: str | None = None,
        grid: list[str] | None = None,
    ) -> str:
        thumb = ""
        extra_cls = ""
        if grid:
            thumb = thumb_grid(grid)
            extra_cls = " has-thumb has-thumb-grid"
        elif cover:
            thumb = thumb_single(cover)
            extra_cls = " has-thumb"
        return (
            f'<a class="link-card{extra_cls}" href="{html.escape(url)}" '
            f'target="_blank" rel="noopener noreferrer">'
            f"{thumb}"
            f'<span class="link-card-body">'
            f'<span class="link-card-label" data-lang="zh">{html.escape(label_zh)}</span>'
            f'<span class="link-card-label" data-lang="en" hidden>{html.escape(label_en)}</span>'
            f'<span class="link-card-url">{html.escape(url)}</span>'
            f"</span></a>"
        )

    if guide.get("blog"):
        cards.append(
            card(guide["blog"], "博客游记", "Travelogue", cover=covers.get(guide["blog"]))
        )
    if guide.get("album"):
        album_url = guide["album"]
        thumbs = album_thumbs.get(album_url) or []
        if thumbs:
            padded = thumbs[:5]
            while len(padded) < 5:
                padded.append(thumbs[len(padded) % len(thumbs)])
            cards.append(
                card(album_url, "旅行相册", "Photo album", grid=padded)
            )
        else:
            cards.append(
                card(
                    album_url,
                    "旅行相册",
                    "Photo album",
                    cover=covers.get(album_url),
                )
            )
    if not cards:
        return ""
    return '<section class="link-cards">' + "".join(cards) + "</section>"


def render_download_section(guide: dict) -> str:
    slug = guide["slug"]
    zh_docx = html.escape(f"{slug}.docx")
    en_docx = html.escape(f"{slug}_en.docx")
    has_en = bool(guide.get("body_en"))
    en_link = (
        f'<a class="download-btn" href="{en_docx}" download>📄 <span>Download Word guide</span></a>'
        if has_en
        else '<p class="guide-download-missing">English Word guide is not available yet.</p>'
    )
    return f"""
        <section class="guide-download panel" aria-labelledby="guide-download-title">
            <h2 class="guide-download-title" id="guide-download-title" data-lang="zh">带走这份攻略</h2>
            <h2 class="guide-download-title" data-lang="en" hidden>Take this guide</h2>
            <p class="guide-download-lead" data-lang="zh">下载 Word 文档，按自己的需要二次加工。</p>
            <p class="guide-download-lead" data-lang="en" hidden>Download the Word file and tailor it to your own trip.</p>
            <div data-lang="zh">
                <a class="download-btn" href="{zh_docx}" download>📄 <span>下载 Word 攻略</span></a>
            </div>
            <div data-lang="en" hidden>
                {en_link}
            </div>
        </section>"""


def render_guide_method_section() -> str:
    url_zh = html.escape(GUIDE_METHOD_POST["zh"])
    url_en = html.escape(GUIDE_METHOD_POST["en"])
    title_zh = html.escape(GUIDE_METHOD_TITLE["zh"])
    title_en = html.escape(GUIDE_METHOD_TITLE["en"])
    return f"""
        <section class="guide-method panel" aria-labelledby="guide-method-title">
            <h2 class="guide-method-title" id="guide-method-title" data-lang="zh">关于旅行攻略</h2>
            <h2 class="guide-method-title" data-lang="en" hidden>About these guides</h2>
            <div class="guide-method-body">
                <p data-lang="zh">其实制作有固定的逻辑，按照特定的顺序把各种因素串起来，行程很快就出来了。</p>
                <p data-lang="en" hidden>There is a repeatable logic behind them—string the right factors together in order and an itinerary falls into place quickly.</p>
                <p data-lang="zh">具体的思路可以看这篇：<a href="{url_zh}" target="_blank" rel="noopener noreferrer">{title_zh}</a></p>
                <p data-lang="en" hidden>Read how I think about it here: <a href="{url_en}" target="_blank" rel="noopener noreferrer">{title_en}</a></p>
            </div>
        </section>"""


def render_meta_chips(guide: dict) -> str:
    dur_zh = pick(guide.get("duration"), "zh")
    dur_en = pick(guide.get("duration"), "en")
    chips: list[str] = []
    if dur_zh:
        chips.append(f'<li data-lang="zh">{html.escape(dur_zh)}</li>')
    if dur_en:
        chips.append(f'<li data-lang="en" hidden>{html.escape(dur_en)}</li>')
    if not chips:
        return ""
    return '<ul class="tag-list meta-chips">' + "\n".join(chips) + "</ul>"


def render_guide_page(
    guide: dict,
    covers: dict[str, str] | None = None,
    album_thumbs: dict[str, list[str]] | None = None,
) -> str:
    origin = SITE["origin"].rstrip("/")
    slug = guide["slug"]
    page_url = f"{origin}/{TRIP_PREFIX}/{slug}/"
    name_zh = pick(guide.get("title"), "zh")
    name_en = pick(guide.get("title"), "en")
    summary_zh = pick(guide.get("summary"), "zh")
    summary_en = pick(guide.get("summary"), "en")
    page_title = f"{name_zh} - {SITE_NAME}"
    body_html_zh = guide_to_html(guide["body"], "zh")
    body_en = guide.get("body_en") or ""
    if body_en:
        body_html_en = guide_to_html(body_en, "en")
    else:
        body_html_en = (
            '<div class="guide-unavailable prose">'
            "<p>English itinerary is not available yet for this trip.</p>"
            "</div>"
        )
    updated = str(guide.get("updated") or date.today().isoformat())
    emoji = html.escape(str(guide.get("emoji") or "✈️"))
    og_image = f"{origin}/assets/og-image.png"

    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": name_zh,
        "alternativeHeadline": name_en,
        "description": summary_zh,
        "url": page_url,
        "inLanguage": ["zh-CN", "en"],
        "dateModified": updated,
        "author": {"@type": "Person", "name": "Victor42", "url": SITE["parentSite"]},
        "publisher": {"@type": "Person", "name": "Victor42", "url": SITE["parentSite"]},
        "image": og_image,
    }

    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": TITLE["zh"],
                "item": origin + "/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": name_zh,
                "item": page_url,
            },
        ],
    }

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(page_title)}</title>

    <meta name="description" content="{html.escape(summary_zh)}">
    <meta name="author" content="Victor42">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{html.escape(page_url)}">

    {hreflang_for(page_url)}

    <meta property="og:type" content="article">
    <meta property="og:title" content="{html.escape(page_title)}">
    <meta property="og:description" content="{html.escape(summary_zh)}">
    <meta property="og:url" content="{html.escape(page_url)}">
    <meta property="og:site_name" content="{SITE_NAME}">
    <meta property="og:locale" content="zh_CN">
    <meta property="og:locale:alternate" content="en_US">
    <meta property="og:image" content="{html.escape(og_image)}">
    <meta property="article:modified_time" content="{html.escape(updated)}">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(name_zh)}">
    <meta name="twitter:description" content="{html.escape(summary_zh)}">
    <meta name="twitter:image" content="{html.escape(og_image)}">

    <meta name="theme-color" content="#2A9D8F">
    <link rel="icon" type="image/svg+xml" href="../../favicon.svg">

    <script src="../../assets/analytics.js"></script>
    <script type="application/ld+json">
{json.dumps(json_ld, ensure_ascii=False, indent=2)}
    </script>
    <script type="application/ld+json">
{json.dumps(breadcrumb_ld, ensure_ascii=False, indent=2)}
    </script>
    <link rel="stylesheet" href="../../assets/style.css?v={ASSET_VERSION}">
    {theme_boot_script()}
    <script type="application/json" id="site-data">{json.dumps(SITE, ensure_ascii=False)}</script>
</head>
<body>
    <button class="theme-toggle" id="theme-toggle" aria-label="切换深色模式" type="button">
        <span class="theme-icon" aria-hidden="true">🌙</span>
    </button>
    <button class="lang-toggle" id="lang-toggle" aria-label="切换语言" type="button">
        <span class="lang-icon" aria-hidden="true">🌐</span>
        <span class="lang-text">EN</span>
    </button>

    <div class="container">
        <header class="guide-detail-header">
            <a class="back-link" href="../../">← {html.escape(SITE_NAME)}</a>
            <div class="detail-emoji" aria-hidden="true">{emoji}</div>
            <h1 class="detail-title" data-lang="zh">{html.escape(name_zh)}</h1>
            <h1 class="detail-title" data-lang="en" hidden>{html.escape(name_en)}</h1>
            <p class="detail-summary" data-lang="zh">{html.escape(summary_zh)}</p>
            <p class="detail-summary" data-lang="en" hidden>{html.escape(summary_en)}</p>
            {render_meta_chips(guide)}
        </header>

        {render_link_cards(guide, covers, album_thumbs)}

        <article class="panel guide-body" data-lang="zh">
{body_html_zh}
        </article>

        <article class="panel guide-body" data-lang="en" hidden>
{body_html_en}
        </article>

        {render_download_section(guide)}

        {render_guide_method_section()}

        <footer class="footer">
            <p id="footer-text"></p>
        </footer>
    </div>

    <script src="../../assets/shared.js?v={ASSET_VERSION}"></script>
    <script src="../../assets/guide.js?v={ASSET_VERSION}"></script>
</body>
</html>
"""


def render_guide_card_html(guide: dict) -> str:
    slug = html.escape(guide["slug"])
    emoji = html.escape(str(guide.get("emoji") or "✈️"))
    name_zh = html.escape(pick(guide.get("title"), "zh"))
    name_en = html.escape(pick(guide.get("title"), "en"))
    summary_zh = html.escape(pick(guide.get("summary"), "zh"))
    summary_en = html.escape(pick(guide.get("summary"), "en"))
    duration_zh = html.escape(pick(guide.get("duration"), "zh"))
    duration_en = html.escape(pick(guide.get("duration"), "en"))
    return f"""
            <a class="guide-card" href="./{TRIP_PREFIX}/{slug}/" aria-label="{name_zh}">
                <div class="guide-emoji" aria-hidden="true">{emoji}</div>
                <h3 class="guide-name" data-lang="zh">{name_zh}</h3>
                <h3 class="guide-name" data-lang="en" hidden>{name_en}</h3>
                <p class="guide-meta" data-lang="zh">{duration_zh}</p>
                <p class="guide-meta" data-lang="en" hidden>{duration_en}</p>
                <p class="guide-summary" data-lang="zh">{summary_zh}</p>
                <p class="guide-summary" data-lang="en" hidden>{summary_en}</p>
            </a>"""

def render_templates_section() -> str:
    return f"""
        <section class="guide-method panel" aria-labelledby="templates-title">
            <h2 class="guide-method-title" id="templates-title" data-lang="zh">空白攻略模板</h2>
            <h2 class="guide-method-title" id="templates-title-en" data-lang="en" hidden>Blank guide templates</h2>
            <div class="guide-method-body">
                <p data-lang="zh">按我自己的写法留了两份空白模板，照着填就能产出一份完整攻略。两种模式：游览版按景点排耗时，度假版按餐食安排日子。</p>
                <p data-lang="en" hidden>Two blank templates in the format I actually use—fill them in to build a complete itinerary. Sightseeing mode schedules attractions by hours; vacation mode schedules days around meals.</p>
                <p>
                    <span data-lang="zh">📄 <a href="./assets/templates/travel-template-sightseeing.docx" download>游览版.docx</a> · <a href="./assets/templates/travel-template-sightseeing.md" download>游览版.md</a> · <a href="./assets/templates/travel-template-vacation.docx" download>度假版.docx</a> · <a href="./assets/templates/travel-template-vacation.md" download>度假版.md</a></span>
                    <span data-lang="en" hidden>📄 <a href="./assets/templates/travel-template-sightseeing_en.docx" download>sightseeing.docx</a> · <a href="./assets/templates/travel-template-sightseeing_en.md" download>sightseeing.md</a> · <a href="./assets/templates/travel-template-vacation_en.docx" download>vacation.docx</a> · <a href="./assets/templates/travel-template-vacation_en.md" download>vacation.md</a></span>
                </p>
            </div>
        </section>"""


def render_index(guides: list[dict]) -> str:
    origin = SITE["origin"].rstrip("/") + "/"
    cards = "\n".join(render_guide_card_html(g) for g in guides)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": TITLE["zh"],
        "url": origin,
        "description": DESCRIPTION["zh"],
        "author": {"@type": "Person", "name": "Victor42", "url": SITE["parentSite"]},
        "hasPart": [
            {
                "@type": "Article",
                "name": pick(g.get("title"), "zh"),
                "url": f"{SITE['origin'].rstrip('/')}/{TRIP_PREFIX}/{g['slug']}/",
            }
            for g in guides
        ],
    }
    web_site_ld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": TITLE["zh"],
        "alternateName": TITLE["en"],
        "url": origin,
        "inLanguage": ["zh-CN", "en"],
    }
    templates_section = render_templates_section()
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(TITLE['zh'])}</title>

    <meta name="description" content="{html.escape(DESCRIPTION['zh'])}">
    <meta name="author" content="Victor42">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{html.escape(origin)}">

    {hreflang_for(origin)}

    <meta property="og:type" content="website">
    <meta property="og:title" content="{html.escape(TITLE['zh'])}">
    <meta property="og:description" content="{html.escape(DESCRIPTION['zh'])}">
    <meta property="og:url" content="{html.escape(origin)}">
    <meta property="og:site_name" content="{SITE_NAME}">
    <meta property="og:locale" content="zh_CN">
    <meta property="og:locale:alternate" content="en_US">
    <meta property="og:image" content="{html.escape(origin + 'assets/og-image.png')}">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(TITLE['zh'])}">
    <meta name="twitter:description" content="{html.escape(DESCRIPTION['zh'])}">
    <meta name="twitter:image" content="{html.escape(origin + 'assets/og-image.png')}">

    <meta name="theme-color" content="#2A9D8F">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
    <link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">

    <script src="./assets/analytics.js"></script>
    <script type="application/ld+json">
{json.dumps(json_ld, ensure_ascii=False, indent=2)}
    </script>
    <script type="application/ld+json">
{json.dumps(web_site_ld, ensure_ascii=False, indent=2)}
    </script>
    <link rel="stylesheet" href="./assets/style.css?v={ASSET_VERSION}">
    {theme_boot_script()}
    <script type="application/json" id="site-data">{json.dumps(SITE, ensure_ascii=False)}</script>
</head>
<body>
    <button class="theme-toggle" id="theme-toggle" aria-label="切换深色模式" type="button">
        <span class="theme-icon" aria-hidden="true">🌙</span>
    </button>
    <button class="lang-toggle" id="lang-toggle" aria-label="切换语言" type="button">
        <span class="lang-icon" aria-hidden="true">🌐</span>
        <span class="lang-text">EN</span>
    </button>

    <div class="container">
        <header class="site-header">
            <a class="parent-link" id="parent-link" href="{html.escape(SITE['parentSite'])}">← 小玩意</a>
            <h1 class="site-title" data-lang="zh">{html.escape(TITLE['zh'])}</h1>
            <h1 class="site-title" data-lang="en" hidden>{html.escape(TITLE['en'])}</h1>
        </header>

        <div class="hero-card">
            <p data-lang="zh">{html.escape(DESCRIPTION['zh'])}</p>
            <p data-lang="en" hidden>{html.escape(DESCRIPTION['en'])}</p>
        </div>

        <div class="guides-grid" id="guides-grid">
{cards}
        </div>

        {templates_section}

        <footer class="footer">
            <p id="footer-text"></p>
        </footer>
    </div>

    <script src="./assets/shared.js?v={ASSET_VERSION}"></script>
    <script src="./assets/main.js?v={ASSET_VERSION}"></script>
</body>
</html>
"""


def build_sitemap(guides: list[dict], lastmod: str) -> str:
    origin = SITE["origin"].rstrip("/") + "/"
    entries = [
        "\n".join(
            [
                "  <url>",
                f"    <loc>{escape(origin)}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>1.0</priority>",
                "  </url>",
            ]
        )
    ]
    for guide in guides:
        loc = f"{SITE['origin'].rstrip('/')}/{TRIP_PREFIX}/{guide['slug']}/"
        entries.append(
            "\n".join(
                [
                    "  <url>",
                    f"    <loc>{escape(loc)}</loc>",
                    f"    <lastmod>{escape(str(guide.get('updated') or lastmod))}</lastmod>",
                    "    <changefreq>monthly</changefreq>",
                    "    <priority>0.9</priority>",
                    "  </url>",
                ]
            )
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


RESERVED_DIRS = {"assets", "guides", "scripts", "trip", ".git"}


def _remove_dir(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)


def clean_generated_dirs(guides: list[dict]) -> None:
    keep = {g["slug"] for g in guides}
    for child in ROOT.iterdir():
        if not child.is_dir() or child.name in RESERVED_DIRS:
            continue
        if (child / "index.html").exists():
            _remove_dir(child)

    TRIP_DIR.mkdir(parents=True, exist_ok=True)
    for child in TRIP_DIR.iterdir():
        if child.is_dir() and child.name not in keep:
            _remove_dir(child)


def main() -> None:
    guides = load_guides()
    clean_generated_dirs(guides)

    print("resolving album/blog covers…")
    media = resolve_for_guides(guides)
    covers = media["covers"]
    album_thumbs = media["album_thumbs"]
    print(f"covers ready ({len(covers)} blog, {len(album_thumbs)} album grids)")

    (ROOT / "index.html").write_text(render_index(guides), encoding="utf-8")
    print("wrote index.html")

    for guide in guides:
        out_dir = TRIP_DIR / guide["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            render_guide_page(guide, covers, album_thumbs), encoding="utf-8"
        )
        page_url = f"{SITE['origin'].rstrip('/')}/{TRIP_PREFIX}/{guide['slug']}/"
        docx_path = out_dir / f"{guide['slug']}.docx"
        legacy_docx = out_dir / "guide.docx"
        if legacy_docx.exists():
            legacy_docx.unlink()
        write_guide_docx(
            pick(guide.get("title"), "zh"),
            guide["body"],
            docx_path,
            source_url=page_url,
            lang="zh",
        )
        if guide.get("body_en"):
            en_docx_path = out_dir / f"{guide['slug']}_en.docx"
            legacy_en = out_dir / f"{guide['slug']}.en.docx"
            if legacy_en.exists():
                legacy_en.unlink()
            write_guide_docx(
                pick(guide.get("title"), "en"),
                guide["body_en"],
                en_docx_path,
                source_url=page_url,
                lang="en",
            )
            print(
                f"wrote {TRIP_PREFIX}/{guide['slug']}/index.html + "
                f"{docx_path.name} + {en_docx_path.name}"
            )
        else:
            print(f"wrote {TRIP_PREFIX}/{guide['slug']}/index.html + {docx_path.name}")

    lastmod = date.today().isoformat()
    (ROOT / "sitemap.xml").write_text(build_sitemap(guides, lastmod), encoding="utf-8")
    print(f"wrote sitemap.xml ({1 + len(guides)} urls)")

    # 空白模板：双语下载副本（docx 由 write_guide_docx 生成，md 从源文件同步）
    templates_dir = ROOT / "assets" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    for zh_src, en_src, slug in [
        ("_Template_旅行攻略-游览.md", "_Template_旅行攻略-游览_en.md", "travel-template-sightseeing"),
        ("_Template_旅行攻略-度假.md", "_Template_旅行攻略-度假_en.md", "travel-template-vacation"),
    ]:
        zh_body = (ROOT / "templates" / zh_src).read_text(encoding="utf-8")
        en_body = (ROOT / "templates" / en_src).read_text(encoding="utf-8")
        write_guide_docx("旅行攻略模板", zh_body, templates_dir / f"{slug}.docx", lang="zh")
        write_guide_docx("Travel Itinerary Template", en_body, templates_dir / f"{slug}_en.docx", lang="en")
        # md 下载副本：从源文件同步，保证与模板正文逐字一致
        (templates_dir / f"{slug}.md").write_text(zh_body, encoding="utf-8")
        (templates_dir / f"{slug}_en.md").write_text(en_body, encoding="utf-8")
    print(f"wrote {len(list(templates_dir.glob('*.docx')))} template docx files")


if __name__ == "__main__":
    main()
