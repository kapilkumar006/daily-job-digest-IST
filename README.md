# Daily Job Digest @ 1:00 PM IST

This repo sends you a daily email (1:00 PM Asia/Kolkata) with fresh **entry-level**
roles for these targets: **java full stack, java developer, frontend developer,
backend developer, software engineer, software developer**. Preference is **Hyderabad**,
then other Indian cities. It also generates a **personalized LinkedIn outreach message**
for each role.

It uses:
- **SerpAPI** (Google Jobs engine) — quick, broad coverage. Free tier available.
- **Gmail SMTP** to send the email.
- **GitHub Actions** to run every day automatically at 07:30 UTC (which is 1:00 PM IST).

---

## Quick Start (GitHub Actions – recommended)

1. **Create a repo** and upload these files, or just upload the ZIP contents.
2. In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `SERPAPI_KEY` — your SerpAPI key (https://serpapi.com/)
   - `GMAIL_USER` — your Gmail address (e.g. `kapilkumar092001@gmail.com`)
   - `GMAIL_APP_PASSWORD` — a Gmail **App Password** (required if 2FA is on). See: https://support.google.com/accounts/answer/185833
   - `RECIPIENT_EMAIL` — where to send the digest (same as above or any email)
3. Optionally edit `config.yaml` (roles/locations, max results, etc.).
4. Push to `main`. The workflow runs **daily at 07:30 UTC** (1:00 PM IST) and can be run manually via **Actions → Run workflow**.

## Run Locally (optional)
```bash
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
export SERPAPI_KEY=your_key
export GMAIL_USER=you@gmail.com
export GMAIL_APP_PASSWORD=your_app_password
export RECIPIENT_EMAIL=you@gmail.com
python job_digest.py
```

## What it does
- Queries **Google Jobs** via SerpAPI for each role and location.
- Filters for **entry-level / 0–1 year / new grad** hints where possible.
- Dedups results, keeps a `data/seen_jobs.json` so you don't get repeats.
- Emails an HTML digest with job title, company, location, apply link, short description,
  and a **custom LinkedIn outreach message** you can copy/paste.

---

## Customize
Open `config.yaml`:
- `roles` — list of role keywords.
- `locations` — prioritized list; Hyderabad is first by default.
- `max_per_role` — cap per role to keep the email short.
- `entry_level_filters` — phrases we try to match.
- `company_preference` — optional company keywords (e.g., YC, fintech) to boost ranking.

