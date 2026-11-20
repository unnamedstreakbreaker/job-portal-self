"""Turn a news article into structured job records with the Claude API (stdlib HTTP)."""
from __future__ import annotations

import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"

JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "description": "One entry per distinct recruitment/hiring in the article. Empty if the article has no concrete job opening.",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short recruitment name, e.g. 'APPSC Group-II Services (Notification 37/2026)'"},
                    "org": {"type": "string"},
                    "sector": {"type": "string", "enum": ["Govt", "Private"]},
                    "region": {"type": "string", "enum": ["Andhra Pradesh", "Telangana", "All India", "Other State"]},
                    "location": {"type": "string"},
                    "posts": {"type": "string", "description": "Number of vacancies as text, or 'Not stated'"},
                    "roles": {"type": "string"},
                    "qualification": {"type": "string"},
                    "experience": {"type": "string"},
                    "age": {"type": "string"},
                    "fee": {"type": "string"},
                    "salary": {"type": "string"},
                    "start": {"type": "string", "description": "Application start date YYYY-MM-DD, or empty"},
                    "end": {"type": "string", "description": "Last date to apply / walk-in last day YYYY-MM-DD, or empty"},
                    "selection": {"type": "string"},
                    "apply": {"type": "string", "description": "How/where to apply or walk-in venue"},
                    "website": {"type": "string", "description": "Official website URL if stated, else empty"},
                    "note": {"type": "string", "description": "Caveats, e.g. domicile-only, dates revised. Empty if none."},
                },
                "required": ["title", "org", "sector", "region", "start", "end"],
            },
        }
    },
    "required": ["jobs"],
}

SYSTEM = (
    "You extract job openings in India from news articles. Only record facts stated in the article; "
    "write 'Not stated' when a field is missing. Never invent dates or URLs. Skip results, admit cards, "
    "answer keys, exam-date notices and opinion pieces: they are not openings. Dates must be YYYY-MM-DD. "
    "Use region 'All India' for central government / PSU / nationwide jobs."
)


def extract_jobs(title: str, url: str, text: str, today: str, model: str) -> list[dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set ANTHROPIC_API_KEY")
    body = {
        "model": model,
        "max_tokens": 4000,
        "system": SYSTEM,
        "tools": [{"name": "save_jobs", "description": "Save the job openings found", "input_schema": JOB_SCHEMA}],
        "tool_choice": {"type": "tool", "name": "save_jobs"},
        "messages": [{
            "role": "user",
            "content": f"Today is {today}.\nHeadline: {title}\nURL: {url}\n\nArticle text:\n{text}",
        }],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.load(r)
    for block in resp.get("content", []):
        if block.get("type") == "tool_use":
            return block["input"].get("jobs", [])
    return []
