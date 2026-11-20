"""IT jobs from company career systems that publish open JSON feeds (stdlib only).

Supported sources (configure in config.json → it_sources):
  {"type": "smartrecruiters", "company": "ServiceNow", "id": "ServiceNow"}
  {"type": "greenhouse",      "company": "Example",    "id": "boardtoken"}
  {"type": "lever",           "company": "Sophos",     "id": "sophos"}
  {"type": "amazon",          "company": "Amazon"}

Workday/TCS iBegin/Infosys portals have no stable public feed; for those, keep using
news/aggregator search (or the daily Claude scheduled task).
"""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime, timezone

from .fetch import http_get

CITIES = {
    "Hyderabad": ["hyderabad", "secunderabad", "hitec", "gachibowli", "madhapur"],
    "Visakhapatnam": ["visakhapatnam", "vizag", "vishakhapatnam"],
}

# Canonical skill → regex. Word-boundary aware so "Java" does not match "JavaScript".
SKILLS = {
    "Java": r"\bjava\b(?!\s*script)", "Spring Boot": r"\bspring\s*boot\b", "Python": r"\bpython\b",
    "JavaScript": r"\bjavascript\b|(?<!\.)\bjs\b", "TypeScript": r"\btypescript\b", "React": r"\breact(\.js|js)?\b",
    "Angular": r"\bangular\b", "Node.js": r"\bnode(\.js|js)?\b", ".NET": r"\.net\b|\bdotnet\b", "C#": r"\bc#",
    "C++": r"\bc\+\+", "Go": r"\bgolang\b|\bgo\b(?=\s*(lang|,|/|\)))", "Kotlin": r"\bkotlin\b", "Scala": r"\bscala\b",
    "AWS": r"\baws\b|amazon web services", "Azure": r"\bazure\b", "GCP": r"\bgcp\b|google cloud",
    "Kubernetes": r"\bkubernetes\b|\bk8s\b", "Docker": r"\bdocker\b", "Terraform": r"\bterraform\b",
    "DevOps": r"\bdevops\b", "CI/CD": r"\bci\s*/\s*cd\b", "SQL": r"\bsql\b", "PostgreSQL": r"\bpostgres(ql)?\b",
    "MongoDB": r"\bmongo(db)?\b", "Kafka": r"\bkafka\b", "Spark": r"\b(py)?spark\b", "Snowflake": r"\bsnowflake\b",
    "Databricks": r"\bdatabricks\b", "Machine Learning": r"machine learning|\bml\b", "GenAI": r"gen\s*ai|generative ai",
    "LLM": r"\bllms?\b|large language model", "Agentic AI": r"agentic|ai agents?", "RAG": r"\brag\b|retrieval[- ]augmented",
    "Microservices": r"micro-?services", "REST API": r"\brest(ful)?\b", "Selenium": r"\bselenium\b",
    "Playwright": r"\bplaywright\b", "Salesforce": r"\bsalesforce\b", "SAP": r"\bsap\b", "Oracle": r"\boracle\b",
    "ServiceNow": r"\bservicenow\b", "Power BI": r"power\s*bi", "Linux": r"\blinux\b", "Embedded": r"\bembedded\b",
}


def tag_skills(text: str) -> list[str]:
    t = (text or "").lower()
    return [name for name, rx in SKILLS.items() if re.search(rx, t)]


def exp_range(text: str):
    m = re.search(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\+?\s*(?:years|yrs)", text or "", re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{1,2})\+?\s*(?:years|yrs)", text or "", re.I)
    return (int(m.group(1)), None) if m else (None, None)


def city_of(loc: str, remote: bool) -> str | None:
    l = (loc or "").lower()
    for city, keys in CITIES.items():
        if any(k in l for k in keys):
            return city
    if remote and "india" in l:
        return "Remote India"
    return None


def _strip(html_text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text or "")).strip()


def _record(company, kind, title, loc, remote, desc, posted, apply, source):
    city = city_of(loc, remote)
    if not city:
        return None
    lo, hi = exp_range(desc)
    return {
        "id": re.sub(r"[^a-z0-9]+", "-", f"{company}-{title}-{apply[-24:]}".lower())[:80],
        "company": company, "kind": kind, "title": title.strip(), "city": city,
        "mode": "Remote" if remote else "On-site", "expMin": lo, "expMax": hi,
        "skills": tag_skills(title + " " + desc), "posted": (posted or "")[:10],
        "apply": apply, "source": source,
    }


def smartrecruiters(src):
    out, offset = [], 0
    while offset < 1000:
        url = f"https://api.smartrecruiters.com/v1/companies/{src['id']}/postings?country=in&limit=100&offset={offset}"
        data = json.loads(http_get(url))
        for p in data.get("content", []):
            loc = p.get("location", {})
            loc_s = f"{loc.get('city','')} {loc.get('country','')}"
            remote = bool(loc.get("remote"))
            if not city_of(loc_s, remote):
                continue
            detail = json.loads(http_get(p["ref"])) if p.get("ref") else {}
            sec = detail.get("jobAd", {}).get("sections", {})
            desc = " ".join(_strip(v.get("text", "")) for v in sec.values() if isinstance(v, dict))
            r = _record(src["company"], src.get("kind", "GCC / Product"), p.get("name", ""), loc_s, remote, desc,
                        p.get("releasedDate"), f"https://jobs.smartrecruiters.com/{src['id']}/{p['id']}", p.get("ref", ""))
            if r:
                out.append(r)
        if offset + 100 >= data.get("totalFound", 0):
            break
        offset += 100
    return out


def greenhouse(src):
    data = json.loads(http_get(f"https://boards-api.greenhouse.io/v1/boards/{src['id']}/jobs?content=true"))
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        r = _record(src["company"], src.get("kind", "GCC / Product"), j.get("title", ""), loc, "remote" in loc.lower(),
                    _strip(j.get("content", "")), j.get("updated_at"), j.get("absolute_url", ""), j.get("absolute_url", ""))
        if r:
            out.append(r)
    return out


def lever(src):
    data = json.loads(http_get(f"https://api.lever.co/v0/postings/{src['id']}?mode=json"))
    out = []
    for j in data:
        cat = j.get("categories", {})
        loc = cat.get("location", "") or ""
        remote = (j.get("workplaceType") == "remote") or "remote" in (cat.get("commitment", "") + loc).lower()
        posted = datetime.fromtimestamp(j.get("createdAt", 0) / 1000, tz=timezone.utc).date().isoformat() if j.get("createdAt") else ""
        r = _record(src["company"], src.get("kind", "GCC / Product"), j.get("text", ""), loc + " india" if remote else loc,
                    remote, j.get("descriptionPlain", ""), posted, j.get("hostedUrl", ""), j.get("hostedUrl", ""))
        if r:
            out.append(r)
    return out


def amazon(src):
    out = []
    for city in ("Hyderabad",):
        q = urllib.parse.urlencode({"normalized_country_code[]": "IND", "city[]": city, "category[]": "software-development",
                                    "result_limit": 100, "sort": "recent"})
        data = json.loads(http_get(f"https://www.amazon.jobs/en/search.json?{q}"))
        for j in data.get("jobs", []):
            desc = j.get("basic_qualifications", "") + " " + j.get("preferred_qualifications", "") + " " + j.get("description", "")
            posted = ""
            try:
                posted = datetime.strptime(j.get("posted_date", ""), "%B %d, %Y").date().isoformat()
            except ValueError:
                pass
            url = "https://www.amazon.jobs" + j.get("job_path", "")
            r = _record("Amazon", "GCC / Product", j.get("title", ""), j.get("normalized_location", city), False,
                        _strip(desc), posted, url, url)
            if r:
                out.append(r)
    return out


FETCHERS = {"smartrecruiters": smartrecruiters, "greenhouse": greenhouse, "lever": lever, "amazon": amazon}


def fetch_it_jobs(sources: list[dict], log=print) -> list[dict]:
    jobs = []
    for src in sources:
        try:
            got = FETCHERS[src["type"]](src)
            log(f"[it] {src['company']}: {len(got)} jobs")
            jobs.extend(got)
        except Exception as e:
            log(f"[it] {src.get('company')}: skipped ({e})")
    return jobs
