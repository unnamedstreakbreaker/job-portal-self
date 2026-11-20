#!/usr/bin/env python3
"""Daily pipeline: news feeds → article text → Claude extraction → SQLite → site/jobs.json

Usage:
  ANTHROPIC_API_KEY=sk-... python run_daily.py            # full run
  python run_daily.py --export-only                        # just rebuild site/jobs.json
  python run_daily.py --seed site/jobs.json                # import an existing jobs.json into the DB
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jobs_pipeline import fetch, extract, store, it_fetch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))


def guess_region(job: dict, cfg: dict) -> str:
    if job.get("region") in ("Andhra Pradesh", "Telangana", "All India"):
        return job["region"]
    text = " ".join(str(job.get(k, "")) for k in ("title", "org", "location")).lower() + " "
    for region, words in cfg["region_keywords"].items():
        if any(w in text for w in words):
            return region
    return job.get("region") or "All India"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "data", "jobs.db"))
    ap.add_argument("--out", default=os.path.join(HERE, "site", "jobs.json"))
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--seed", help="import jobs from an existing jobs.json")
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(HERE, "config.json")))
    today = datetime.now(IST).date().isoformat()
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    db = store.connect(args.db)

    if args.seed:
        data = json.load(open(args.seed))
        n = sum(store.upsert(db, j, j.get("added") or today) for j in data["jobs"])
        db.commit()
        print(f"[seed] {n} new jobs imported")

    if not args.export_only and not args.seed:
        articles = fetch.fetch_feeds(cfg["feeds"], cfg["lookback_days"], cfg["must_match_any"])
        new = done = 0
        for art in articles:
            if done >= cfg["max_articles_per_run"]:
                break
            if store.url_seen(db, art["link"]):
                continue
            text = fetch.article_text(art["link"]) or art["summary"]
            try:
                jobs = extract.extract_jobs(art["title"], art["link"], text, today, cfg["model"])
            except Exception as e:
                print(f"[extract] failed: {art['title'][:70]} ({e})")
                continue
            for j in jobs:
                if not j.get("end") and not j.get("start"):
                    continue  # no dates → not actionable
                j["region"] = guess_region(j, cfg)
                j["source"] = art["link"]
                new += store.upsert(db, j, today)
            store.mark_seen(db, art["link"], today)
            db.commit()
            done += 1
            time.sleep(0.5)
        print(f"[run] {done} articles processed, {new} new jobs")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    n = store.export(db, args.out, today, "Andhra Pradesh & Telangana first, plus major all-India jobs")
    print(f"[export] {n} jobs → {args.out}")

    if not args.export_only and not args.seed:
        update_it_jobs(cfg, os.path.join(os.path.dirname(args.out), "it_jobs.json"), today)


def update_it_jobs(cfg: dict, path: str, today: str):
    """Merge fresh ATS postings into it_jobs.json, keeping manually added entries and dropping stale ones."""
    from datetime import date
    sources = [s for s in cfg.get("it_sources", []) if "type" in s]
    fresh = it_fetch.fetch_it_jobs(sources)
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        data = {"scope": "IT companies · Hyderabad, Visakhapatnam, Remote India", "jobs": []}
    by_id = {j["id"]: j for j in data.get("jobs", [])}
    by_url = {j.get("apply"): j["id"] for j in by_id.values() if j.get("apply")}
    for j in fresh:
        key = by_url.get(j.get("apply"), j["id"])  # same posting found by research → merge, keep its id
        merged = {**by_id.get(key, {}), **{k: v for k, v in j.items() if v not in (None, "", [])}}
        merged["id"] = key
        by_id[key] = merged
    max_age = cfg.get("it_max_age_days", 45)
    t = date.fromisoformat(today)

    def keep(j):
        if j.get("applyBy") and j["applyBy"] < today:
            return False
        if j.get("posted"):
            try:
                return (t - date.fromisoformat(j["posted"])).days <= max_age
            except ValueError:
                return True
        return True

    jobs = sorted(filter(keep, by_id.values()), key=lambda j: j.get("posted") or "", reverse=True)
    data.update({"updated": today, "jobs": jobs})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[it] {len(fresh)} fetched, {len(jobs)} IT jobs → {path}")


if __name__ == "__main__":
    main()
