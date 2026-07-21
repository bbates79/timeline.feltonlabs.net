#!/usr/bin/env python3
"""
Daily update script for Global Conflict Timeline
Fetches latest news from Signal and updates timeline data
"""
import json
import urllib.request
import urllib.parse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Configuration
REPO_DIR = Path.cwd()
DATA_FILE = REPO_DIR / "data.json"
SIGNAL_ENDPOINT = "https://signal.feltonlabs.net/digest"

# Categories to fetch for conflict timeline
CATEGORIES = ["conflict", "world", "politics"]

# How many articles to pull per category
LIMIT = 10

# Git configuration
GITHUB_USER = "bbates79"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN environment variable is required")


def fetch_category(category: str, limit: int = 10) -> dict:
    """Fetch articles from Signal for a specific category."""
    params = f"format=json&category={category}&limit={limit}"
    url = f"{SIGNAL_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "HermesAgent-Timeline/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception as e:
        print(f"Warning: Failed to fetch {category}: {e}")
        return {"articles": [], "generated": None}


def fetch_all_conflict_news(categories, limit=10):
    """Fetch news from all specified categories."""
    all_articles = []
    seen_titles = set()
    
    for cat in categories:
        data = fetch_category(cat, limit)
        if data.get("generated"):
            print(f"  Fetched {cat}: {data.get('count', 0)} articles")
        
        for article in data.get("articles", []):
            title = article.get("title", "")
            if title not in seen_titles:
                seen_titles.add(title)
                all_articles.append(article)
    
    # Sort by published date, newest first
    all_articles.sort(
        key=lambda x: x.get("published", x.get("title", "")),
        reverse=True,
    )
    return all_articles


def load_current_data():
    """Load existing timeline data."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"items": [], "headline": ""}


def make_timeline_item(article, idx):
    """Convert a Signal article into a timeline entry."""
    published = article.get("published", "")
    date_str = published[:10] if published else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    summary = article.get("summary", "").strip()
    if not summary:
        summary = article.get("title", "")
    
    # Extract category from article if available
    category = article.get("category", "conflict")
    
    return {
        "id": idx,
        "date": date_str,
        "time": datetime.now().strftime("%H:%M"),
        "title": article.get("title", "Untitled"),
        "source": article.get("source", "Unknown"),
        "summary": summary,
        "details": summary,
        "category": category,
        "link": article.get("link", ""),
        "published": published,
    }


def build_timeline_items(articles, existing_items=None):
    """Build timeline items list from articles, preserving existing data."""
    existing = existing_items or []
    existing_titles = {item.get("title") for item in existing}
    
    items = list(existing)
    for i, article in enumerate(articles, 1):
        title = article.get("title", "")
        if title not in existing_titles:
            items.insert(0, make_timeline_item(article, len(items) + i))
    
    # Deduplicate and keep unique titles
    seen = set()
    unique_items = []
    for item in items:
        title = item.get("title", "")
        if title not in seen:
            seen.add(title)
            unique_items.append(item)
    
    return unique_items[:30]  # Keep last 30 entries


def run_git_command(args, cwd=None):
    """Run a git command and capture output."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd or str(REPO_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Git error: {result.stderr}")
    return result


def commit_and_push():
    """Commit and push changes to GitHub."""
    # Check if anything changed
    status = run_git_command(["status", "--porcelain"])
    if not status.stdout.strip():
        print("Nothing to commit.")
        return
    
    # Add all changes
    run_git_command(["add", "."])
    
    # Commit
    today = datetime.now().strftime("%B %d, %Y")
    run_git_command([
        "commit",
        "-m",
        f"Daily update: {today}",
    ])
    
    # Push
    push_result = run_git_command([
        "push",
        f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/timeline.feltonlabs.net.git",
        "main",
    ])
    if push_result.returncode == 0:
        print(" Successfully pushed to GitHub")
    else:
        print(f"Warning: Push failed: {push_result.stderr}")


def main():
    print("=" * 60)
    print("Global Conflict Timeline - Daily Update")
    print("=" * 60)
    
    # Check repo exists
    if not REPO_DIR.exists():
        print(f"ERROR: Repository directory not found: {REPO_DIR}")
        return 1
    
    os.chdir(REPO_DIR)
    
    # Pull latest changes first
    print("\nPulling latest changes...")
    pull_result = run_git_command(["pull", "origin", "main"])
    if pull_result.returncode != 0:
        print(f"Warning: Pull failed: {pull_result.stderr}")
    
    # Fetch current data.json
    existing_data = load_current_data()
    existing_items = existing_data.get("items", [])
    
    # Fetch latest news from Signal
    print("\nFetching latest news from Signal...")
    articles = fetch_all_conflict_news(CATEGORIES, LIMIT)
    print(f"  Found {len(articles)} new/existing articles")
    
    if not articles:
        print("No articles fetched. Exiting.")
        return 0
    
    # Build timeline with latest generated timestamp
    latest_timestamp = datetime.now(timezone.utc).isoformat()
    timeline_items = build_timeline_items(articles, existing_items)
    
    # Update headline
    headline = existing_data.get("headline", "Global Conflict Timeline")
    today = datetime.now().strftime("%B %d, %Y")
    if not headline:
        headline = f"Global Conflict Timeline - {today}"
    else:
        # Update the date if it's different
        parts = headline.split(" - ")
        if len(parts) > 1:
            headline = f"{parts[0]} - {today}"
        else:
            headline = f"{headline} - {today}"
    
    # Prepare new data
    new_data = {
        "last_updated": latest_timestamp,
        "headline": headline,
        "items": timeline_items,
        "categories": CATEGORIES,
        "limit": LIMIT,
    }
    
    # Check if there are actual changes
    if json.dumps(existing_data, sort_keys=True) == json.dumps(new_data, sort_keys=True):
        print("No changes to data.json")
        return 0
    
    # Write updated data
    with open(DATA_FILE, 'w') as f:
        json.dump(new_data, f, indent=2)
    print(f"Updated data.json with {len(timeline_items)} timeline items")
    
    # Commit and push
    print("\nCommitting and pushing changes...")
    commit_and_push()
    
    print("\nDaily update complete!")
    print(f"Repository: https://github.com/{GITHUB_USER}/timeline.feltonlabs.net")
    print(f"Website: https://bbates79.github.io/timeline.feltonlabs.net/")
    
    return 0


if __name__ == "__main__":
    exit(main() or 0)
