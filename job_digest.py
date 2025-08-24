import os, json, time, smtplib, ssl, textwrap
import requests
import yaml
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

assert SERPAPI_KEY, "Missing SERPAPI_KEY env"
assert GMAIL_USER, "Missing GMAIL_USER env"
assert GMAIL_APP_PASSWORD, "Missing GMAIL_APP_PASSWORD env"
assert RECIPIENT_EMAIL, "Missing RECIPIENT_EMAIL env"

CONFIG_PATH = Path("config.yaml")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
SEEN_PATH = DATA_DIR / "seen_jobs.json"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_seen():
    if SEEN_PATH.exists():
        try:
            return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_seen(seen):
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")

def serpapi_google_jobs(query, location, num=20):
    # Docs: https://serpapi.com/google-jobs-api
    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "num": num
    }
    r = requests.get("https://serpapi.com/search", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def is_entry_level(job, filters):
    text = " ".join([
        job.get("title",""),
        job.get("company_name",""),
        job.get("description",""),
        " ".join(job.get("detected_extensions", {}).keys())
    ]).lower()
    return any(f.lower() in text for f in filters)

def rank_job(job, company_preference):
    score = 0
    title = job.get("title","").lower()
    company = job.get("company_name","").lower()
    desc = job.get("description","").lower()
    if "intern" in title:
        score -= 2
    if "senior" in title or "lead" in title or "staff" in title or "principal" in title:
        score -= 3
    for kw in company_preference or []:
        if kw.lower() in company or kw.lower() in desc:
            score += 1
    # Newer jobs tend to float in Google Jobs; detected_extensions may include "posted_at"
    return score

def job_key(job):
    # Construct a stable key
    base = f"{job.get('title','')}|{job.get('company_name','')}|{job.get('location','')}"
    # include apply options if present
    apply_list = job.get("apply_options") or []
    if apply_list:
        base += "|" + "|".join(sorted([a.get("title","") + a.get("link","") for a in apply_list]))
    return base

def best_apply_link(job):
    # Prefer direct company links if available
    apply_list = job.get("apply_options") or []
    if not apply_list:
        return job.get("apply_link") or job.get("share_link") or job.get("job_id")
    # Try to pick a company site link
    company = (job.get("company_name") or "").lower()
    for opt in apply_list:
        lnk = opt.get("link","").lower()
        title = opt.get("title","").lower()
        if "company" in title or (company and company in lnk):
            return opt.get("link")
    return apply_list[0].get("link")

def outreach_message(job, your_name="Kapil"):
    role = job.get("title","").strip()
    company = job.get("company_name","").strip()
    location = job.get("location","").strip()
    # Short, personalized, entry-level focused note
    return textwrap.dedent(f"""
    Hi {{first_name or "there"}} 👋,

    I’m {your_name}, a junior developer focused on modern web stacks (JS/React) and Java fundamentals.
    I spotted the **{role}** opening at **{company}** in {location} and I’m excited about the role.
    I’ve built projects like:
    • Responsive React apps with clean component patterns and hooks
    • REST/JSON integrations and basic Node/Express APIs
    • Solid HTML/CSS, accessibility, and Git workflows

    If relevant, I’d love to share a quick link to my portfolio/GitHub and discuss how I could ramp up quickly.
    Could you point me to the best person to speak with, or share the next steps?

    Thanks,
    {your_name}
    """).strip()

def build_email_html(digest_items):
    parts = []
    parts.append("<h2>Daily Entry-level Roles (Hyderabad first)</h2>")
    for role, location, jobs in digest_items:
        if not jobs:
            continue
        parts.append(f"<h3>{role.title()} — {location}</h3>")
        parts.append("<ul>")
        for j in jobs:
            title = j.get("title","")
            company = j.get("company_name","")
            loc = j.get("location","")
            link = best_apply_link(j) or j.get("share_link") or "#"
            desc = (j.get("description","") or "").replace("\n"," ").strip()
            short = (desc[:220] + "…") if len(desc) > 220 else desc
            li = f"""
            <li style='margin-bottom:10px'>
              <div><strong>{title}</strong> — {company} ({loc})</div>
              <div><a href="{link}">Apply / Details</a></div>
              <div style='font-size:0.95em;color:#333;margin-top:4px'>{short}</div>
              <details style='margin-top:6px'>
                <summary>LinkedIn outreach (click to expand)</summary>
                <pre style='white-space:pre-wrap;font-family:ui-monospace, SFMono-Regular, Menlo, monospace;'>{outreach_message(j)}</pre>
              </details>
            </li>
            """
            parts.append(li)
        parts.append("</ul>")
    return "\n".join(parts)

def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    part = MIMEText(html_body, "html", "utf-8")
    msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [RECIPIENT_EMAIL], msg.as_string())

def main():
    cfg = load_config()
    seen = load_seen()

    digest = []
    new_seen = dict(seen)
    total_found = 0

    for role in cfg["roles"]:
        for location in cfg["locations"]:
            query = f"{role} entry level"
            try:
                payload = serpapi_google_jobs(query, location, num=20)
            except Exception as e:
                print("Error fetching:", role, location, e)
                continue

            jobs = payload.get("jobs_results", []) or []
            # filter entry-level
            jobs = [j for j in jobs if is_entry_level(j, cfg["entry_level_filters"])]
            # rank & sort
            jobs = sorted(jobs, key=lambda j: -rank_job(j, cfg.get("company_preference")))

            # dedup vs seen and within this batch
            unique = []
            used_keys = set()
            for j in jobs:
                key = job_key(j)
                if key in used_keys:
                    continue
                if key in seen:
                    continue
                used_keys.add(key)
                unique.append(j)

            unique = unique[: cfg["max_per_role"]]
            total_found += len(unique)
            digest.append((role, location, unique))

            # mark as seen
            for j in unique:
                new_seen[job_key(j)] = {
                    "first_seen": int(time.time()),
                    "title": j.get("title",""),
                    "company": j.get("company_name",""),
                    "location": j.get("location",""),
                }

    if total_found == 0:
        html = "<p>No new matching entry-level roles today (based on filters). We'll check again tomorrow.</p>"
    else:
        html = build_email_html(digest)

    subject = f"[Daily Jobs] {total_found} new entry-level roles — {time.strftime('%Y-%m-%d')}"
    send_email(subject, html)
    save_seen(new_seen)
    print("Sent:", subject)

if __name__ == "__main__":
    main()
