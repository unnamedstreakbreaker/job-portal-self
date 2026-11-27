# Resume AI proxy (Cloudflare Worker)

The **Resume check** button on both pages works in two layers:

| Where the page runs | Instant checks + matching jobs | AI review + rewritten resume |
|---|---|---|
| GitHub Pages site | Yes, in the browser | Through this worker, using **your** Anthropic API key |
| Claude artifact (claude.ai) | Yes, in the browser | Through the viewer's own Claude account (`sample` capability) |

Until the worker is deployed and its URL is set, the GitHub site shows the instant checks and matching jobs, and the rewrite button stays off.

## Deploy (about 10 minutes, free plan)

1. Create a free Cloudflare account, then on your computer:
   ```bash
   cd worker
   npx wrangler login
   npx wrangler kv namespace create RESUME_KV     # copy the id into wrangler.toml
   npx wrangler secret put ANTHROPIC_API_KEY      # paste your sk-ant-... key
   npx wrangler deploy
   ```
   Deploy prints a URL like `https://job-portal-resume.<you>.workers.dev`.
2. Check it: open `https://job-portal-resume.<you>.workers.dev/health` — it should say `{"ok":true}`.
3. Put the URL in **both** pages, in the `RESUME_CFG` line near the end of `site/index.html` and `site/it/index.html`:
   ```html
   <script>window.RESUME_CFG={page:'it',api:'https://job-portal-resume.<you>.workers.dev/resume'}</script>
   ```
   Commit and push; the site republishes.
4. In the Anthropic Console, set a **monthly spend limit** on the key.

## Cost and limits

- Each AI review or rewrite is one Claude call, roughly 4–8k input and 1–3k output tokens — a few US cents with Sonnet. Set `MODEL_ANALYZE` to a Haiku model in `wrangler.toml` to cut the cost of reviews.
- `DAILY_PER_IP` (default 10) and `DAILY_TOTAL` (default 300) cap the calls per day; the `RL` binding allows 3 requests a minute per IP. At the defaults, the worst case is about 300 calls a day.
- The worker only accepts requests from `ALLOWED_ORIGINS`, builds the prompt itself (it cannot be used as a general Claude endpoint), and stores nothing except the daily counters. A determined abuser can still script requests from a server, so keep the spend limit on.

## Local test

```bash
npx wrangler dev   # then set api:'http://localhost:8787/resume' and add http://localhost:8000 to ALLOWED_ORIGINS
```
