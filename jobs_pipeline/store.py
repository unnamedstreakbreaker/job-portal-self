"""SQLite storage with de-duplication, and export to the website's jobs.json."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, timedelta

FIELDS = ["title", "org", "sector", "region", "location", "posts", "roles", "qualification",
          "experience", "age", "fee", "salary", "start", "end", "selection", "apply",
          "website", "source", "note", "added"]


def connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute(f"""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, {', '.join(f'"{f}" TEXT' for f in FIELDS)}, updated TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS seen_urls (url TEXT PRIMARY KEY, seen TEXT)")
    return db


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def job_id(j: dict) -> str:
    """Same org + same post family + same last date → same job, even from different articles."""
    nums = re.findall(r"\d{2,}", j.get("title", ""))
    key = "|".join([_norm(j.get("org"))[:40], _norm(j.get("title"))[:30], "".join(nums[:2]), j.get("end", "")])
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def url_seen(db, url: str) -> bool:
    return db.execute("SELECT 1 FROM seen_urls WHERE url=?", (url,)).fetchone() is not None


def mark_seen(db, url: str, today: str):
    db.execute("INSERT OR IGNORE INTO seen_urls VALUES (?,?)", (url, today))


def upsert(db, j: dict, today: str) -> bool:
    """Insert new job or fill blanks / newer dates on an existing one. Returns True if new."""
    jid = job_id(j)
    row = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    clean = {f: (j.get(f) or "").strip() for f in FIELDS}
    if row is None:
        clean["added"] = today
        db.execute(f"INSERT INTO jobs VALUES (?, {','.join('?' * len(FIELDS))}, ?)",
                   [jid, *[clean[f] for f in FIELDS], today])
        return True
    old = dict(zip(["id", *FIELDS, "updated"], row))
    for f in FIELDS:
        if f == "added":
            continue
        if clean[f] and clean[f] != "Not stated" and (not old[f] or old[f] == "Not stated"):
            old[f] = clean[f]
    if clean["end"] and clean["end"] > (old["end"] or ""):  # date extended
        old["end"] = clean["end"]
    sets = ",".join(f'"{f}"=?' for f in FIELDS)
    db.execute(f"UPDATE jobs SET {sets}, updated=? WHERE id=?", [*[old[f] for f in FIELDS], today, jid])
    return False


def export(db, out_path: str, today: str, focus: str, keep_closed_days: int = 7):
    """Write jobs.json for the site: open/upcoming jobs plus ones closed in the last week."""
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_closed_days)).isoformat()
    rows = db.execute("SELECT * FROM jobs WHERE end='' OR end>=? ORDER BY end", (cutoff,)).fetchall()
    jobs = [dict(zip(["id", *FIELDS, "updated"], r)) for r in rows]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"updated": today, "focus": focus, "jobs": jobs}, f, ensure_ascii=False, indent=1)
    return len(jobs)
