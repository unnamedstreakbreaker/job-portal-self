# Daily Jobs India

**Live pages:** `site/index.html` (Daily Jobs India — govt, private & IT) and `site/it/` (IT Jobs Finder — job types, places, AP districts, saved/applied tracker).

This project reads Indian news every day and lists the government and private jobs it finds, with eligibility, start date, last date, location, fee, salary and how to apply. It covers Andhra Pradesh and Telangana first, then major all-India jobs.

```
RSS news feeds ──► article text ──► Claude (structured extraction) ──► SQLite (dedupe) ──► site/jobs.json ──► static site
```

- **No dependencies.** It needs Python 3.10 or later and uses only the standard library.
- **Cost:** about 60 articles a day on Claude Haiku costs a few cents.
- **Deduplication:** when the same job appears in several articles, it becomes one record. Missing fields are filled in from later articles, and an extended last date is picked up automatically.

## IT jobs tab

`site/it_jobs.json` powers the **IT Jobs** tab. On the page you type your tech stack (for example "Java, Spring Boot, AWS"), and jobs are ranked by how many of your skills they ask for. Matched skills are highlighted, and you can filter by experience, city, company type and posting date.

`run_daily.py` refreshes the list from company job boards that publish open JSON feeds (`jobs_pipeline/it_fetch.py`):

| Type | Example in `config.json → it_sources` |
|---|---|
| SmartRecruiters | `{"type": "smartrecruiters", "company": "ServiceNow", "id": "ServiceNow"}` |
| Greenhouse | `{"type": "greenhouse", "company": "Name", "id": "<board token>"}` |
| Lever | `{"type": "lever", "company": "Sophos", "id": "sophos"}` |
| Amazon | `{"type": "amazon", "company": "Amazon"}` |

The pipeline keeps Hyderabad, Visakhapatnam and remote-India roles, tags skills with word-boundary rules (so "Java" never matches "JavaScript"), and reads experience from the text. Jobs posted more than 45 days ago, and walk-ins whose date has passed, are dropped. Entries you add by hand are kept.

TCS, Infosys, Accenture (Workday) and other big portals have no stable public feed. Add their jobs by hand, or let the Claude scheduled task research them.

## Run it locally

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run_daily.py --seed site/jobs.json   # first time only: load today's starter list
python run_daily.py                         # fetch news, extract jobs, rebuild site/jobs.json
cd site && python -m http.server 8000       # open http://localhost:8000
```

## Deploy free with GitHub Actions and Pages

1. Push this folder to a new GitHub repo.
2. Go to **Settings → Secrets → Actions** and add `ANTHROPIC_API_KEY`.
3. Go to **Settings → Pages** and set the source to **GitHub Actions**.
4. `.github/workflows/daily.yml` runs every day at 05:47 IST. It updates the data, commits it and redeploys the site. To run it immediately, use **Run workflow** on the Actions tab.

The `site/` folder is plain static files, so you can also host it on Netlify, Vercel, Cloudflare Pages or any VPS. On a VPS, set up a cron job:

```
47 5 * * * cd /opt/jobs-india && ANTHROPIC_API_KEY=... /usr/bin/python3 run_daily.py >> run.log 2>&1
```

## Customise

- **`config.json`**: add or remove news feeds. Any Google News search can be a feed: `https://news.google.com/rss/search?q=YOUR+QUERY&hl=en-IN&gl=IN&ceid=IN:en`. You can also add official RSS feeds or Telugu news feeds; Claude reads Telugu.
- **`region_keywords`**: the town and district names used to tag AP and Telangana jobs.
- **`model`**: switch to `claude-sonnet-5-5` for more accurate extraction from messy pages.
- **Ideas for later:** a Telegram or WhatsApp alert for new jobs that close within 7 days, and a filter by qualification (10th, ITI, Degree, B.Tech).

## Accuracy

Each job links to the article it came from. The extraction prompt forbids made-up dates or URLs, and jobs without any dates are dropped. News sites sometimes publish stale or conflicting dates, so the site tells readers to confirm on the official website.
