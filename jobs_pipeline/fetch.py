"""Fetch news items from RSS feeds and pull readable article text (stdlib only)."""
from __future__ import annotations

import email.utils
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; DailyJobsIndiaBot/1.0; +https://example.com/bot)"


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-IN,en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(3_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def parse_rss(xml_text: str) -> list[dict]:
    items = []
    root = ET.fromstring(xml_text)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate")
        desc = html.unescape(re.sub(r"<[^>]+>", " ", it.findtext("description") or "")).strip()
        try:
            published = email.utils.parsedate_to_datetime(pub) if pub else None
        except (TypeError, ValueError):
            published = None
        items.append({"title": title, "link": link, "published": published, "summary": desc})
    return items


def fetch_feeds(feeds: list[str], lookback_days: int, must_match: list[str], log=print) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    seen, out = set(), []
    for url in feeds:
        try:
            items = parse_rss(http_get(url))
        except Exception as e:  # one bad feed must not stop the run
            log(f"[feed] skip {url[:80]}… ({e})")
            continue
        for it in items:
            if it["link"] in seen:
                continue
            if it["published"] and it["published"] < cutoff:
                continue
            text = (it["title"] + " " + it["summary"]).lower()
            if not any(k in text for k in must_match):
                continue
            seen.add(it["link"])
            out.append(it)
    log(f"[feed] {len(out)} candidate articles")
    return out


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        elif tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "td") and not self.depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth and data.strip():
            self.parts.append(data.strip() + " ")


def article_text(url: str, max_chars: int = 12000) -> str:
    """Best-effort readable text. Google News links redirect; urllib follows them."""
    try:
        p = _TextExtractor()
        p.feed(http_get(url))
        text = re.sub(r"\n\s*\n+", "\n", "".join(p.parts))
        return text[:max_chars]
    except Exception:
        return ""
