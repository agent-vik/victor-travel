#!/usr/bin/env python3
"""Render travel guide Markdown as structured HTML (itinerary-aware)."""

from __future__ import annotations

import html
import re

import markdown

from guide_i18n import UI, section_key, section_title

DAY_H_RE = re.compile(r"^### (D\d+)(.*)$")
TASK_RE = re.compile(r"^(\s*)- \[( |x|X)\] (.+)$")
BOLD_ONLY_RE = re.compile(r"^\*\*(.+)\*\*\s*$")
MEAL_RE = re.compile(r"^\*\*(午餐|晚餐|Lunch|Dinner)[：:]\*\*\s*(.*)$", re.I)
SPOT_RE = re.compile(r"^\*\*((?:景点：|Sights?:|Attractions?:).+)\*\*\s*$", re.I)
TIME_RE = re.compile(r"^\*\*(时间：.+|Dates?:.+|Time:.+)\*\*\s*$", re.I)
LOGISTICS_RE = re.compile(
    r"^(跨市交通|市内交通|交通|住宿|"
    r"Intercity transport|Local transport|Transport|Accommodation|Stay)[：:]\s*(.*)$",
    re.I,
)
TRANSPORT_RE = re.compile(
    r"^.+\(.+?\)\s*-\s*.+\(.+?\)$|^.+\(\d{1,2}:\d{2}\)\s*-\s*.+\(\d{1,2}:\d{2}\)$"
)
POI_RE = re.compile(r"^(\s*)- \[( |x|X)\] (.+)$")
GEO_H3_RE = re.compile(r"^### (.+)$")
REF_ORIGIN_RE = re.compile(
    r"^方位和距离相对于(.+)。$|^参考原点：(.+)$|"
    r"^Bearing and distance from (.+)\.$|^Reference point:\s*(.+)$",
    re.I,
)
STAY_KEYS = {"住宿", "Accommodation", "Stay"}


def inline_md(text: str) -> str:
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        out,
    )
    return out


def md_fragment(text: str) -> str:
    if not text.strip():
        return ""
    rendered = markdown.markdown(
        text.strip(),
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    return rendered.strip()


def split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if title is not None:
                sections.append((title, "\n".join(lines).strip()))
            title = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    if title is not None:
        sections.append((title, "\n".join(lines).strip()))
    return sections


def split_days(block: str) -> tuple[str, list[tuple[str, str]]]:
    header_lines: list[str] = []
    days: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in block.splitlines():
        m = DAY_H_RE.match(line)
        if m:
            if current_title is not None:
                days.append((current_title, "\n".join(current_lines).strip()))
            elif header_lines and current_lines:
                header_lines.extend(current_lines)
                current_lines = []
            current_title = line
            current_lines = []
        elif current_title is None:
            header_lines.append(line)
        else:
            current_lines.append(line)
    if current_title is not None:
        days.append((current_title, "\n".join(current_lines).strip()))
    return "\n".join(header_lines).strip(), days


def parse_trip_header(header: str) -> dict:
    meta: dict = {"time": "", "logistics": [], "stays": []}
    lines = [ln for ln in header.splitlines() if ln.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        tm = TIME_RE.match(line)
        if tm:
            meta["time"] = tm.group(0).strip()
            i += 1
            continue
        lm = LOGISTICS_RE.match(line)
        if lm:
            key, rest = lm.group(1), lm.group(2).strip()
            if key in STAY_KEYS and not rest:
                stays: list[str] = []
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith("- "):
                    stays.append(lines[i].strip()[2:].strip())
                    i += 1
                meta["stays"] = stays
                meta["logistics"].append((key, ""))
                continue
            meta["logistics"].append((key, rest))
            i += 1
            continue
        i += 1
    return meta


def parse_day_body(body: str) -> dict:
    parts: dict = {
        "transport": [],
        "meals": [],
        "spots": [],
        "todos": [],
        "paragraphs": [],
    }
    for line in body.splitlines():
        if not line.strip():
            continue
        if TASK_RE.match(line):
            m = TASK_RE.match(line)
            assert m
            parts["todos"].append((m.group(2).lower() == "x", m.group(3).strip()))
            continue
        mm = MEAL_RE.match(line)
        if mm:
            parts["meals"].append((mm.group(1), mm.group(2).strip()))
            continue
        sm = SPOT_RE.match(line)
        if sm:
            parts["spots"].append(sm.group(1))
            continue
        if TRANSPORT_RE.match(line.strip()) or (
            " - " in line and "(" in line and ")" in line and not line.startswith("-")
        ):
            parts["transport"].append(line.strip())
            continue
        parts["paragraphs"].append(line.strip())
    return parts


def render_trip_header(meta: dict, lang: str) -> str:
    bits: list[str] = ['<div class="trip-meta">']
    if meta.get("time"):
        bits.append(f'<p class="trip-time">{inline_md(meta["time"])}</p>')
    logistics = meta.get("logistics") or []
    stays = meta.get("stays") or []
    if logistics or stays:
        bits.append('<dl class="trip-meta-grid">')
        for key, val in logistics:
            if key in STAY_KEYS and stays:
                label = UI[lang]["accommodation"] if key == "住宿" else key
                bits.append(f"<dt>{html.escape(label)}</dt><dd>")
                bits.append('<ul class="trip-stays">')
                for s in stays:
                    bits.append(f"<li>{inline_md(s)}</li>")
                bits.append("</ul></dd>")
            else:
                bits.append(f"<dt>{html.escape(key)}</dt>")
                bits.append(f"<dd>{inline_md(val)}</dd>")
        bits.append("</dl>")
    bits.append("</div>")
    return "\n".join(bits)


def render_day(title_line: str, body: str) -> str:
    m = DAY_H_RE.match(title_line)
    if not m:
        return ""
    badge, rest = m.group(1), m.group(2).strip()
    day_id = badge.lower()
    subtitle = rest if rest else ""

    parts = parse_day_body(body)
    out: list[str] = [
        f'<article class="day-card" id="day-{html.escape(day_id)}">',
        '<header class="day-header">',
        f'<span class="day-badge">{html.escape(badge)}</span>',
        f'<h3 class="day-title">{inline_md(subtitle) if subtitle else html.escape(badge)}</h3>',
        "</header>",
        '<div class="day-body">',
    ]

    for t in parts["transport"]:
        out.append(f'<p class="day-transport">{inline_md(t)}</p>')

    if parts["meals"]:
        out.append('<div class="day-meals">')
        for kind, text in parts["meals"]:
            out.append(
                f'<p class="day-meal"><span class="day-meal-label">{html.escape(kind)}</span>'
                f'<span class="day-meal-text">{inline_md(text)}</span></p>'
            )
        out.append("</div>")

    for spot in parts["spots"]:
        out.append(f'<p class="day-spots"><strong>{html.escape(spot)}</strong></p>')

    if parts["todos"]:
        out.append('<ul class="day-todos">')
        for done, text in parts["todos"]:
            checked = " checked" if done else ""
            cls = " is-done" if done else ""
            out.append(
                f'<li class="day-todo{cls}">'
                f'<input type="checkbox" disabled{checked} aria-hidden="true">'
                f"<span>{inline_md(text)}</span></li>"
            )
        out.append("</ul>")

    for para in parts["paragraphs"]:
        out.append(f'<p class="day-narrative">{inline_md(para)}</p>')

    out.extend(["</div>", "</article>"])
    return "\n".join(out)


def render_itinerary(content: str, lang: str) -> str:
    header, days = split_days(content)
    meta = parse_trip_header(header)

    nav_bits: list[str] = []
    day_bits: list[str] = []
    for title_line, body in days:
        m = DAY_H_RE.match(title_line)
        if m:
            badge = m.group(1)
            nav_bits.append(
                f'<a class="day-nav-link" href="#day-{badge.lower()}">{html.escape(badge)}</a>'
            )
        day_bits.append(render_day(title_line, body))

    nav = ""
    if nav_bits:
        nav = (
            f'<nav class="day-nav" aria-label="{html.escape(UI[lang]["day_nav"])}">'
            + "".join(nav_bits)
            + "</nav>"
        )

    return "\n".join(
        [
            '<section class="guide-section guide-itinerary">',
            f'<h2 class="guide-section-title">{html.escape(section_title("itinerary", lang))}</h2>',
            render_trip_header(meta, lang),
            nav,
            '<div class="day-cards">',
            *day_bits,
            "</div>",
            "</section>",
        ]
    )


def render_checklist(content: str, lang: str) -> str:
    inner = md_fragment(content) if content else "<p></p>"
    return "\n".join(
        [
            '<section class="guide-section guide-checklist">',
            f'<h2 class="guide-section-title">{html.escape(section_title("checklist", lang))}</h2>',
            f'<div class="guide-checklist-body prose">{inner}</div>',
            "</section>",
        ]
    )


def render_tips(content: str, lang: str) -> str:
    blocks: list[str] = []
    current: list[str] = []
    sub_title: str | None = None

    def flush() -> None:
        nonlocal current, sub_title
        if not current and not sub_title:
            return
        if sub_title:
            blocks.append(f'<div class="tips-sub"><h3 class="tips-subtitle">{inline_md(sub_title)}</h3>')
            blocks.append(f'<div class="prose">{md_fragment(chr(10).join(current))}</div></div>')
        else:
            blocks.append(f'<div class="prose">{md_fragment(chr(10).join(current))}</div>')
        current = []
        sub_title = None

    for line in content.splitlines():
        if line.startswith("### "):
            flush()
            sub_title = line[4:].strip()
            continue
        if line.strip() == "---":
            continue
        current.append(line)
    flush()

    body = "\n".join(blocks) if blocks else f'<div class="prose">{md_fragment(content)}</div>'
    return "\n".join(
        [
            '<section class="guide-section guide-tips">',
            f'<h2 class="guide-section-title">{html.escape(section_title("tips", lang))}</h2>',
            f'<div class="guide-tips-body">{body}</div>',
            "</section>",
        ]
    )


def parse_poi_meta(text: str) -> tuple[str, str, bool]:
    """Return (name, meta_html, done). Meta is typically district / bearing / distance / drive."""
    m = POI_RE.match(text)
    if not m:
        return text, "", False
    done = m.group(2).lower() == "x"
    raw = m.group(3).strip()
    meta_match = re.search(
        r"(?:（([^（）]+ / [^（）]+ / [^（）]+)）|\(([^()]+ / [^()]+ / [^()]+)\))$",
        raw,
    )
    if meta_match:
        meta_raw = meta_match.group(1) or meta_match.group(2) or ""
        name = raw[: meta_match.start()].strip()
        bits = [b.strip() for b in meta_raw.split("/")]
        spans = "".join(f"<span>{html.escape(b)}</span>" for b in bits)
        meta_html = f'<span class="poi-meta">{spans}</span>'
        return name, meta_html, done
    return raw, "", done


def render_pois(content: str, lang: str) -> str:
    ref = ""
    groups: list[tuple[str, list[tuple[str, str, bool]]]] = []
    current_group = ""
    current_items: list[tuple[str, str, bool]] = []

    def flush_group() -> None:
        nonlocal current_group, current_items
        if current_group or current_items:
            groups.append((current_group, current_items))
        current_group = ""
        current_items = []

    for line in content.splitlines():
        if not line.strip() or line.strip() == "---":
            continue
        rm = REF_ORIGIN_RE.match(line.strip())
        if rm:
            origin = rm.group(1) or rm.group(2) or rm.group(3) or rm.group(4) or ""
            ref = f'<p class="poi-ref">{html.escape(UI[lang]["poi_ref"])}{html.escape(origin)}</p>'
            continue
        gm = GEO_H3_RE.match(line)
        if gm:
            flush_group()
            current_group = gm.group(1).strip()
            continue
        bm = BOLD_ONLY_RE.match(line.strip())
        if bm:
            flush_group()
            current_group = bm.group(1).strip()
            continue
        if POI_RE.match(line):
            name, meta_html, done = parse_poi_meta(line)
            current_items.append((name, meta_html, done))
            continue
        if current_items:
            current_items[-1] = (
                current_items[-1][0] + " " + line.strip(),
                current_items[-1][1],
                current_items[-1][2],
            )

    flush_group()

    group_html: list[str] = []
    for title, items in groups:
        if not items:
            continue
        title_html = (
            f'<h3 class="poi-group-title">{html.escape(title)}</h3>' if title else ""
        )
        lis: list[str] = []
        for name, meta_html, done in items:
            cls = "poi-item is-selected" if done else "poi-item"
            check = "✓" if done else "○"
            lis.append(
                f'<li class="{cls}">'
                f'<span class="poi-check" aria-hidden="true">{check}</span>'
                f'<span class="poi-name">{html.escape(name)}</span>'
                f"{meta_html}</li>"
            )
        group_html.append(
            f'<div class="poi-group">{title_html}<ul class="poi-list">{"".join(lis)}</ul></div>'
        )

    return "\n".join(
        [
            '<section class="guide-section guide-pois">',
            f'<h2 class="guide-section-title">{html.escape(section_title("pois", lang))}</h2>',
            ref,
            "".join(group_html),
            "</section>",
        ]
    )


def render_generic(title: str, content: str) -> str:
    inner = md_fragment(content) if content else ""
    return "\n".join(
        [
            '<section class="guide-section guide-generic">',
            f'<h2 class="guide-section-title">{html.escape(title)}</h2>',
            f'<div class="prose">{inner}</div>',
            "</section>",
        ]
    )


SECTION_RENDERERS = {
    "itinerary": render_itinerary,
    "checklist": render_checklist,
    "tips": render_tips,
    "pois": render_pois,
}


def guide_to_html(body: str, lang: str = "zh") -> str:
    sections = split_sections(body.strip())
    if not sections:
        return md_fragment(body)

    out: list[str] = ['<div class="guide-structured">']
    for title, content in sections:
        key = section_key(title)
        renderer = SECTION_RENDERERS.get(key) if key else None
        if renderer:
            out.append(renderer(content, lang))
        else:
            out.append(render_generic(title, content))
    out.append("</div>")
    return "\n".join(out)
