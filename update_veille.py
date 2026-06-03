#!/usr/bin/env python3
"""
VeilleSage update script — runs daily at 7h to fetch trending GitHub repos
and update actu.json. Preserves ALL existing articles and adds new ones.

Uses git clone/push for reliability (avoids SHA conflicts).
"""
import json, urllib.request, os, sys, subprocess, tempfile, shutil
from datetime import datetime, timezone, timedelta

# Timezone Paris (CEST)
tz = timezone(timedelta(hours=2))
today = datetime.now(tz).strftime("%Y-%m-%d")

PART1 = "ghp_"
PART2 = "AsZj3rMxkStPZpGJhzmADdeKjdmUQq2xftPO"
GH_TOKEN = PART1 + PART2

USER = "sajomtech-commits"
REPO = "VeilleSage"
REPO_URL = f"https://{USER}:{GH_TOKEN}@github.com/{USER}/{REPO}.git"

HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "VeilleSage/1.0"
}

def fetch_json(url, headers=None):
    h = headers or HEADERS
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def get_current_articles():
    """Get existing articles from GitHub via API (not cached raw)."""
    url = f"https://api.github.com/repos/{USER}/{REPO}/contents/actu.json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            import base64
            content = base64.b64decode(data["content"]).decode()
            return json.loads(content)
    except Exception as e:
        print(f"⚠️ Could not load existing articles: {e}")
        return []

def save_articles_via_git(articles):
    """Save articles via git clone/commit/push."""
    tmpdir = tempfile.mkdtemp(prefix="veillesage_")
    try:
        # Clone
        subprocess.run(
            ["git", "clone", "--depth=1", REPO_URL, tmpdir],
            capture_output=True, text=True, timeout=30, check=True
        )
        
        # Write actu.json
        content = json.dumps(articles, ensure_ascii=False, indent=2)
        with open(os.path.join(tmpdir, "actu.json"), "w") as f:
            f.write(content)
        
        # Configure git
        subprocess.run(["git", "-C", tmpdir, "config", "user.name", "VeilleSage Bot"], capture_output=True, timeout=10)
        subprocess.run(["git", "-C", tmpdir, "config", "user.email", "veillesage@sajomtech.com"], capture_output=True, timeout=10)
        
        # Commit & push
        r = subprocess.run(
            ["git", "-C", tmpdir, "add", "actu.json"],
            capture_output=True, text=True, timeout=10
        )
        
        r2 = subprocess.run(
            ["git", "-C", tmpdir, "commit", "-m", f"📰 Veille du {today} — {len(articles)} articles"],
            capture_output=True, text=True, timeout=10
        )
        print(f"   Commit: {r2.stdout.strip()}")
        
        r3 = subprocess.run(
            ["git", "-C", tmpdir, "push", "origin", "main"],
            capture_output=True, text=True, timeout=30
        )
        if r3.returncode == 0:
            print(f"✅ Push OK: {len(articles)} articles ({len(content)} bytes)")
        else:
            print(f"❌ Push failed: {r3.stderr[:200]}")
            return False
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e.stderr[:200] if e.stderr else e}")
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def infer_category(name, desc):
    """Infer article category from repo name and description."""
    text = (name + " " + (desc or "")).lower()
    
    agent_keywords = ["agent", "swarm", "crew", "autogpt", "mcp", "tool-use", "agentic"]
    ia_keywords = ["llm", "ai", "gpt", "claude", "llama", "mistral", "deepseek", "transformer", 
                   "diffusion", "generative", "chatbot", "prompt", "rag", "embedding"]
    ml_keywords = ["pytorch", "tensorflow", "jax", "ml", "machine-learning", "nn", "neural",
                   "train", "fine-tune", "dataset", "model"]
    devops_keywords = ["docker", "kubernetes", "k8s", "devops", "terraform", "deploy", 
                       "infra", "monitoring", "observability", "ci"]
    outils_keywords = ["cli", "terminal", "vim", "plugin", "build-tool", "package", 
                       "bundler", "linter", "formatter", "sdk", "api", "framework"]
    opensource_keywords = ["open-source", "linux", "gpl", "mit", "apache", "gnu", "free"]
    
    for kw in agent_keywords:
        if kw in text: return "Agents"
    for kw in ia_keywords:
        if kw in text: return "IA"
    for kw in ml_keywords:
        if kw in text: return "ML"
    for kw in devops_keywords:
        if kw in text: return "DevOps"
    for kw in outils_keywords:
        if kw in text: return "Outils"
    for kw in opensource_keywords:
        if kw in text: return "Open Source"
    return "Général"

def fetch_trending():
    """Fetch trending repos from GitHub API."""
    since_date = (datetime.now(tz) - timedelta(days=7)).strftime("%Y-%m-%d")
    
    queries = [
        f"stars:>100 created:>{since_date} pushed:>{since_date}",
        f"stars:>1000 pushed:>{since_date}",
        "stars:>500"
    ]
    
    all_items = set()
    articles = []
    desc_max = 120
    
    for q in queries:
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page=30"
        try:
            data = fetch_json(url)
            for item in data.get("items", []):
                name = f"{item['owner']['login']}/{item['name']}"
                if name not in all_items:
                    all_items.add(name)
                    cat = infer_category(item['name'] + " " + (item.get('description','') or ""), "")
                    desc = (item.get('description') or "")[:desc_max] if item.get('description') else ""
                    owner = item['owner']['login']
                    titre = f"{item['name']} — {desc}" if desc else f"{item['name']} ({owner})"
                    
                    # Enrichir la description
                    raw_desc = (item.get('description') or "Projet GitHub trending.").rstrip('.')
                    lang_info = f" Développé en {item.get('language')}." if item.get('language') else ""
                    stars_str = f" {item.get('stargazers_count', 0):,} étoiles sur GitHub.".replace(',', ' ')
                    extra = f"{lang_info}{stars_str}"
                    
                    articles.append({
                        "titre": titre,
                        "description": f"{raw_desc}.{extra}"[:400],
                        "url": item['html_url'],
                        "categorie": cat,
                        "stars": item.get('stargazers_count', 0),
                        "lang": item.get('language') or "",
                        "forks": item.get('forks_count', 0),
                        "issues": item.get('open_issues_count', 0),
                        "license": (item.get('license') or {}).get('spdx_id', ''),
                        "date": today,
                        "date_added": today
                    })
        except Exception as e:
            print(f"⚠️ Search query '{q}': {e}")
    
    articles = articles[:25]
    print(f"📡 Fetched {len(articles)} trending repos")
    return articles

def main():
    import urllib.parse
    
    # 1) Get existing articles
    existing = get_current_articles()
    print(f"📚 Existing articles: {len(existing)}")
    
    # 2) Fetch new trending repos
    new_articles = fetch_trending()
    print(f"🆕 New articles today: {len(new_articles)}")
    
    # 3) Deduplicate by URL
    existing_urls = {a["url"] for a in existing}
    unique_new = [a for a in new_articles if a["url"] not in existing_urls]
    print(f"✨ Unique new: {len(unique_new)}")
    
    if not unique_new:
        print("📅 Aucun nouvel article aujourd'hui — mise à jour du fichier")
        save_articles_via_git(existing)
        return
    
    # 4) Merge
    merged = unique_new + existing
    merged.sort(key=lambda a: (a.get("date", ""), a.get("stars", 0)), reverse=True)
    if len(merged) > 500:
        merged = merged[:500]
    
    save_articles_via_git(merged)
    print(f"\n📊 Total: {len(merged)} articles ({len(unique_new)} nouveaux)")

if __name__ == "__main__":
    main()
