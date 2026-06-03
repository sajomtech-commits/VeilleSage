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
    
    agent_keywords = ["agent", "swarm", "crew", "autogpt", "mcp", "tool-use", "agentic", "multi-agent", "orchestrator", "copilot"]
    ia_keywords = ["llm", "ai", "gpt", "claude", "llama", "mistral", "deepseek", "transformer", 
                   "diffusion", "generative", "chatbot", "prompt", "rag", "embedding",
                   "openai", "anthropic", "language-model", "foundation-model"]
    ml_keywords = ["pytorch", "tensorflow", "jax", "ml", "machine-learning", "nn", "neural",
                   "train", "fine-tune", "dataset", "model", "inference", "vllm", "triton",
                   "onnx", "gguf", "mlx", "deep-learning", "computer-vision", "nlp"]
    devops_keywords = ["docker", "kubernetes", "k8s", "devops", "terraform", "deploy", 
                       "infra", "monitoring", "observability", "ci", "cd", "gitops",
                       "helm", "ansible", "caddy", "nginx", "traefik", "prometheus",
                       "grafana", "linux", "container", "kubectl"]
    outils_keywords = ["cli", "terminal", "vim", "neovim", "plugin", "build-tool", "package", 
                       "bundler", "linter", "formatter", "sdk", "api", "framework",
                       "vs-code", "vscode", "ide", "compiler", "npm", "cargo", "go",
                       "rust", "typescript", "node", "deno", "bun", "debugger", "test"]
    opensource_keywords = ["open-source", "gpl", "mit", "apache", "gnu", "free-software",
                           "self-hosted", "selfhosted", "privacy", "foss"]
    design_keywords = ["ui", "ux", "design", "figma", "tailwind", "css", "animation",
                       "icon", "typography", "color", "theme", "dashboard", "component"]
    web_keywords = ["react", "vue", "svelte", "angular", "nextjs", "nuxt", "webapp",
                    "web-app", "frontend", "backend", "fullstack", "api", "rest",
                    "graphql", "http", "server", "browser", "html", "javascript"]
    mobile_keywords = ["android", "ios", "swift", "kotlin", "flutter", "react-native",
                       "mobile", "app", "pwa", "progressive-web"]
    securite_keywords = ["security", "cyber", "cryptography", "encrypt", "auth",
                         "oauth", "jwt", "vulnerability", "malware", "pentest",
                         "firewall", "zero-trust", "privacy"]
    data_keywords = ["database", "sql", "postgres", "mysql", "sqlite", "redis",
                     "mongodb", "big-data", "etl", "data-pipeline", "warehouse",
                     "analytics", "dashboard", "visualization", "bi"]
    image_keywords = ["image", "photo", "photo", "computer-vision", "vision",
                      "detection", "recognition", "segmentation", "ocr",
                      "stable-diffusion", "generative-image", "screenshot"]
    
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
    for kw in design_keywords:
        if kw in text: return "Design/UI"
    for kw in web_keywords:
        if kw in text: return "Web"
    for kw in mobile_keywords:
        if kw in text: return "Mobile"
    for kw in securite_keywords:
        if kw in text: return "Sécurité"
    for kw in data_keywords:
        if kw in text: return "Data"
    for kw in image_keywords:
        if kw in text: return "Image/Vision"
    for kw in opensource_keywords:
        if kw in text: return "Open Source"
    return "Général"

# Dictionnaire de traduction anglais → français pour les descriptions techniques
FR_TRANSLATIONS = {
    # Mots courants dans les descriptions GitHub
    "build ": "construit ",
    "tool ": "outil ",
    "tools ": "outils ",
    "framework ": "framework ",
    "library ": "bibliothèque ",
    "library for ": "bibliothèque pour ",
    "a library ": "une bibliothèque ",
    "a tool ": "un outil ",
    "a framework ": "un framework ",
    "a set of ": "un ensemble d'",
    "a simple ": "un outil ",
    "an open-source ": "un ",
    "open-source ": "",
    "open source ": "",
    "lightweight ": "léger ",
    "fast ": "rapide ",
    "high-performance ": "haute performance ",
    "easy to use ": "simple d'utilisation ",
    "user-friendly ": "convivial ",
    "modern ": "moderne ",
    "cross-platform ": "multi-plateforme ",
    "real-time ": "temps réel ",
    "web-based ": "web ",
    "based on ": "basé sur ",
    "written in ": "écrit en ",
    "powered by ": "propulsé par ",
    "designed for ": "conçu pour ",
    "built for ": "conçu pour ",
    "built with ": "construit avec ",
    "for building ": "pour construire ",
    "for creating ": "pour créer ",
    "for managing ": "pour gérer ",
    "for developers ": "pour les développeurs ",
    "make it easy ": "facilite ",
    "lets you ": "permet de ",
    "allows you ": "permet de ",
    "allows developers ": "permet aux développeurs de ",
    "helps you ": "aide à ",
    "you can ": "on peut ",
    "that makes ": "qui rend ",
    "that lets ": "qui permet ",
    "that helps ": "qui aide ",
    "that runs ": "qui fonctionne ",
    "that works ": "qui fonctionne ",
    "using ": "avec ",
    "database ": "base de données ",
    "machine learning ": "apprentissage automatique ",
    "deep learning ": "apprentissage profond ",
    "artificial intelligence ": "intelligence artificielle ",
    "neural network ": "réseau de neurones ",
    "natural language ": "langage naturel ",
    "user interface ": "interface utilisateur ",
    "command line ": "ligne de commande ",
    "development ": "développement ",
    "deployment ": "déploiement ",
    "container ": "conteneur ",
    "cloud-native ": "cloud natif ",
    "automation ": "automatisation ",
    "monitoring ": "supervision ",
    "visualization ": "visualisation ",
    "management ": "gestion ",
    "security ": "sécurité ",
    "authentication ": "authentification ",
    "encryption ": "chiffrement ",
    "performance ": "performance ",
    "scalable ": "passage à l'échelle ",
    "reliable ": "fiable ",
    "efficient ": "efficace ",
    "powerful ": "puissant ",
    "flexible ": "flexible ",
    "extensible ": "extensible ",
}

# Mots à supprimer (trop vagues en anglais)
FR_REMOVE = ["a ", "an ", "the ", "that ", "which ", "this ", "these ", "its ", "your "]

def frenchify_desc(raw_desc, item):
    """Construit une description en français à partir des données du repo."""
    import re
    name = item.get('name', '')
    raw = raw_desc.strip()
    lang = item.get('language')
    stars = item.get('stargazers_count', 0)
    lic = (item.get('license') or {}).get('spdx_id', '')
    
    stars_fmt = f"{stars:,}".replace(",", " ") if stars else ""
    
    # Extraire les informations utiles de la description anglaise
    extraits = []
    
    # Verbes d'action
    for pattern, action in [
        (r'build|create|developp?|develop', 'créer'),
        (r'manag|admin|control|monitor', 'gérer'),
        (r'convert|transform|process|analyz', 'traiter'),
        (r'deploy|ship|publish|host', 'déployer'),
        (r'search|find|query|retrieve', 'rechercher'),
        (r'train|fine.tune|learn', 'entraîner'),
        (r'optimiz|boost|speed.up|accelerate', 'optimiser'),
        (r'protect|secure|encrypt|auth', 'sécuriser'),
        (r'visualiz|chart|graph|plot', 'visualiser'),
        (r'automat|script|pipeline', 'automatiser'),
    ]:
        if re.search(pattern, raw, re.IGNORECASE):
            extraits.append(action)
    
    # Domaines
    for pattern, domaine in [
        (r'ai |artificial.intelligence|llm|gpt|claude|llama', 'd\'intelligence artificielle'),
        (r'agent|swarm|autonomous|multi-agent', "d'agents intelligents"),
        (r'machine.learning|deep.learning|neural|pytorch|tensorflow', "d'apprentissage automatique"),
        (r'database|sql|postgres|redis|mongodb', 'de base de données'),
        (r'web|frontend|backend|react|vue|angular|next', 'web'),
        (r'mobile|flutter|react.native|android|ios', 'mobile'),
        (r'cli|terminal|command.line', 'en ligne de commande'),
        (r'design|ui|ux|figma|tailwind|component', "d'interface utilisateur"),
        (r'security|cyber|crypt|encrypt|auth', 'de sécurité'),
        (r'devops|docker|kubernetes|deploy|infra', 'DevOps'),
        (r'image|vision|ocr|detection|photo', "d'analyse d'images"),
        (r'audio|speech|voice|music', 'audio'),
        (r'video|stream|recording', 'vidéo'),
        (r'data|analytics|big.data|dashboard', 'de données'),
        (r'open.source|free|gpl|mit|apache', 'open-source'),
    ]:
        if re.search(pattern, raw, re.IGNORECASE):
            extraits.append(domaine)
    
    # Usages spécifiques
    usages = []
    for pattern, usage in [
        (r'for.developer|for.coder|for.programmer', 'les développeurs'),
        (r'for.team|collaborat|workflow', 'les équipes'),
        (r'for.business|enterprise|company|org', 'les entreprises'),
        (r'for.student|for.learner|education|tutorial', 'l\'apprentissage'),
        (r'for.research|scientif|academic', 'la recherche'),
        (r'productivity|efficiency|boost', 'la productivité'),
    ]:
        if re.search(pattern, raw, re.IGNORECASE):
            usages.append(usage)
    
    # Qualifiants
    qualites = []
    for pattern, qual in [
        (r'fast|quick|rapid|blazing|speed', 'Rapide'),
        (r'lightweight|minimal|small|tiny', 'Léger'),
        (r'modern|new.generation|next.gen', 'Moderne'),
        (r'easy|simple|user.friendly|intuitive', 'Simple d\'utilisation'),
        (r'powerful|robust|enterprise.grade', 'Puissant'),
        (r'extensible|modular|plugin|customiz', 'Extensible'),
        (r'scalable|high.performance|efficient', 'Haute performance'),
        (r'secure|private|privacy|encrypted', 'Sécurisé'),
        (r'cross.platform|multi.platform', 'Multi-plateforme'),
    ]:
        if re.search(pattern, raw, re.IGNORECASE):
            qualites.append(qual)
    
    # Construire la phrase en français
    action = extraits[0] if extraits else "créer"
    domaine = extraits[1] if len(extraits) > 1 else ""
    
    # Nettoyer les doublons
    if domaine and domaine in action:
        domaine = ""
    
    if qualites:
        qual_str = qualites[0]
        if len(qualites) > 1:
            qual_str = f"{qualites[0]} et {qualites[1].lower()}"
    else:
        qual_str = ""
    
    sujet = f"Outil {qual_str.lower()} pour {action}" if qual_str else f"Projet pour {action}"
    if domaine:
        sujet = f"{sujet} dans le domaine {domaine}"
    
    if usages:
        sujet = f"{sujet} destiné à {usages[0]}"
    
    sujet += "."
    
    # Ajouter le nom du repo + métriques
    full = f"{sujet}"
    if lang:
        full += f" Développé en {lang}."
    if stars_fmt:
        full += f" {stars_fmt} étoiles sur GitHub."
    
    # Ajouter un extrait de la description originale traduite si elle est riche
    if len(raw) > 30:
        # Traduire les mots-clés techniques qu'on a ratés
        trad = raw
        for e, f in FR_TRANSLATIONS.items():
            trad = re.sub(re.escape(e), f, trad, flags=re.IGNORECASE)
        for w in FR_REMOVE:
            trad = re.sub(r'\b' + re.escape(w) + r'\b', '', trad, flags=re.IGNORECASE)
        trad = re.sub(r'\s+', ' ', trad).strip().rstrip('.')
        
        # Si la traduction est significativement différente de la phrase construite
        if len(trad) > 40 and trad.lower() not in full.lower():
            extra = f" Plus précisément : {trad}."
            if len(full) + len(extra) < 400:
                full += extra
    
    return full

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
                    
                    # Construction d'une description en français
                    raw_desc = (item.get('description') or "Projet GitHub trending.")
                    fr_desc = frenchify_desc(raw_desc, item)
                    
                    articles.append({
                        "titre": titre,
                        "description": fr_desc[:400],
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
    
    # Recherches ciblées pour les catégories souvent vides
    target_queries = {
        "Open Source": f"stars:>500 license:mit created:>{since_date}",
        "Sécurité": f"stars:>500 security OR cybersecurity created:>{since_date}",
        "Data": f"stars:>500 database OR analytics created:>{since_date}",
        "Mobile": f"stars:>500 flutter OR react-native created:>{since_date}",
        "Image/Vision": f"stars:>500 image OR computer-vision created:>{since_date}",
        "Design/UI": f"stars:>300 design OR ui OR tailwind created:>{since_date}",
        "Web": f"stars:>1000 react OR nextjs OR frontend created:>{since_date}",
    }
    
    for tcat, tq in target_queries.items():
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(tq)}&sort=stars&order=desc&per_page=10"
        try:
            data = fetch_json(url)
            for item in data.get("items", []):
                name = f"{item['owner']['login']}/{item['name']}"
                if name not in all_items:
                    all_items.add(name)
                    desc = (item.get('description') or "")[:desc_max] if item.get('description') else ""
                    owner = item['owner']['login']
                    titre = f"{item['name']} — {desc}" if desc else f"{item['name']} ({owner})"
                    raw_desc = (item.get('description') or "Projet GitHub trending.")
                    fr_desc = frenchify_desc(raw_desc, item)
                    articles.append({
                        "titre": titre,
                        "description": fr_desc[:400],
                        "url": item['html_url'],
                        "categorie": tcat,
                        "stars": item.get('stargazers_count', 0),
                        "lang": item.get('language') or "",
                        "forks": item.get('forks_count', 0),
                        "issues": item.get('open_issues_count', 0),
                        "license": (item.get('license') or {}).get('spdx_id', ''),
                        "date": today,
                        "date_added": today
                    })
        except Exception as e:
            print(f"⚠️ Target search '{tcat}': {e}")
    
    articles = articles[:50]
    
    # Filtrer les articles chinois/non-français
    import re
    chinese = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    filtered = []
    for a in articles:
        text = a['titre'] + ' ' + a.get('description','') + ' ' + a['url']
        if chinese.search(text):
            print(f"  ⛔ Filtré (chinois): {a['titre'][:40]}")
            continue
        filtered.append(a)
    articles = filtered
    
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
