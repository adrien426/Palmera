#!/usr/bin/env python3
"""Publie le jeu sur la branche gh-pages (GitHub Pages).

  branche par défaut (main)  ->  https://<compte>.github.io/<dépôt>/                    (+ Palmera-jeu.html)
  toute autre branche        ->  https://<compte>.github.io/<dépôt>/preview/<branche>/
  liste des previews         ->  https://<compte>.github.io/<dépôt>/preview/

- gh-pages ne garde qu'un seul commit : le dépôt ne grossit pas à chaque déploiement.
- Deux déploiements en même temps ne s'écrasent pas : l'envoi se fait avec --force-with-lease
  et on recommence sur la dernière version de gh-pages si quelqu'un est passé entre-temps.
- Les previews des branches qui n'existent plus sont effacées à chaque passage.

Utilisation (GitHub Actions, voir .github/workflows/pages.yml) :
  python3 tools/pages.py deploy --branch <nom>     publie la branche (code du dossier courant)
  python3 tools/pages.py prune                     efface les previews des branches supprimées
Variables : GITHUB_REPOSITORY, GH_TOKEN, DEFAULT_BRANCH (main par défaut),
            PAGES_REMOTE (dépôt git à utiliser à la place de GitHub, pour les tests).
"""
import argparse
import base64
import datetime
import html
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request

PAGES_BRANCH = 'gh-pages'
PREVIEW_DIR = 'preview'
OFFLINE_FILE = 'Palmera-jeu.html'
# ce qui n'est pas publié (outils, docs, fichiers git)
EXCLUDE = {'tools', 'test', 'tests', 'node_modules', '_site', OFFLINE_FILE}
EXCLUDE_EXT = ('.md', '.py')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REPO = os.environ.get('GITHUB_REPOSITORY', 'adrien426/Palmera')
DEFAULT_BRANCH = os.environ.get('DEFAULT_BRANCH') or 'main'
TOKEN = os.environ.get('GH_TOKEN', '')
LOCAL_TEST = bool(os.environ.get('PAGES_REMOTE'))


# ---------------------------------------------------------------- utilitaires

def log(*a):
    print(*a, flush=True)


def annotate(kind, msg):
    """Avertissement visible sur la page du run GitHub Actions."""
    if os.environ.get('GITHUB_ACTIONS'):
        print(f'::{kind}::' + msg.replace('%', '%25').replace('\r', '').replace('\n', '%0A'), flush=True)
    else:
        log(f'[{kind}] {msg}')


def git(*args, cwd, check=True):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)} : {r.stderr.strip() or r.stdout.strip()}')
    return r


def slug(branch):
    """feature/Météo v2 -> feature-meteo-v2 : un nom de dossier sûr pour l'adresse de la preview."""
    s = unicodedata.normalize('NFKD', branch).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9_-]+', '-', s).strip('-_')
    return s or 'branche'


def site_base():
    """Adresse du site : celle donnée par l'API Pages si possible, sinon calculée."""
    owner, name = REPO.split('/', 1)
    if name.lower() == f'{owner.lower()}.github.io':
        return f'https://{owner.lower()}.github.io/'
    return f'https://{owner.lower()}.github.io/{name}/'


def write_output(key, value):
    path = os.environ.get('GITHUB_OUTPUT')
    if path:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')


def write_summary(md):
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(md + '\n')
    else:
        log(md)


# ---------------------------------------------------------------- contenu du site

def build_site(out, branch, is_main, sha, message):
    """Copie le jeu dans out/ (+ version.json, + version hors ligne pour main)."""
    os.makedirs(out)
    for name in sorted(os.listdir(ROOT)):
        if name.startswith('.') or name in EXCLUDE or name.endswith(EXCLUDE_EXT):
            continue
        if name == PREVIEW_DIR:
            raise SystemExit(f'Le dossier {PREVIEW_DIR}/ est réservé aux previews : renomme-le.')
        src, dst = os.path.join(ROOT, name), os.path.join(out, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    index = os.path.join(out, 'index.html')
    if not is_main and os.path.exists(index):
        with open(index, encoding='utf-8') as f:
            page = f.read()
        page = re.sub(r'<title>(.*?)</title>',
                      lambda m: f'<title>{m.group(1)} · preview {html.escape(branch)}</title>', page, count=1)
        with open(index, 'w', encoding='utf-8') as f:
            f.write(page)

    if is_main:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import build_offline
            _, n_libs, n_assets, size = build_offline.build(out, os.path.join(out, OFFLINE_FILE))
            log(f'{OFFLINE_FILE} : {n_libs} bibliothèques, {n_assets} fichiers, {size / 1e6:.1f} Mo')
        except Exception as e:  # le site reste publié même si la version hors ligne échoue
            annotate('warning', f'Version hors ligne non générée : {e}')

    info = {'branch': branch, 'commit': sha, 'message': message,
            'date': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    with open(os.path.join(out, 'version.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=1)


def preview_index(wt):
    """(Re)crée preview/index.html : la liste des previews en ligne."""
    pdir = os.path.join(wt, PREVIEW_DIR)
    rows = []
    for name in os.listdir(pdir):
        vfile = os.path.join(pdir, name, 'version.json')
        if os.path.isfile(vfile):
            with open(vfile, encoding='utf-8') as f:
                v = json.load(f)
            rows.append((v.get('date', ''), name, v))
    rows.sort(reverse=True)
    items = '\n'.join(
        f'<li><a href="{html.escape(name)}/?v={html.escape(v.get("commit", "")[:7])}">{html.escape(v.get("branch", name))}</a>'
        f'<span>{html.escape(v.get("message", ""))}</span>'
        f'<small>{html.escape(v.get("date", "").replace("T", " ").rstrip("Z"))} UTC · {html.escape(v.get("commit", "")[:7])}</small></li>'
        for _, name, v in rows) or '<li><span>Aucune preview pour le moment.</span></li>'
    page = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Palmera · previews</title><meta name="robots" content="noindex">
<style>
:root{{--bg:#f6f3ee;--fg:#141821;--mut:#5b6472;--card:#fff;--line:#e3ddd3;--acc:#d9466f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#070a12;--fg:#f6f3ee;--mut:#aeb8c6;--card:#101522;--line:#1f2738;--acc:#ff3d8b}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:32px 16px}}
h1{{font-size:28px;margin:0 0 4px}} p{{color:var(--mut);margin:0 0 24px}}
a{{color:var(--acc);font-weight:600}}
ul{{list-style:none;padding:0;margin:0;display:grid;gap:10px}}
li{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;display:grid;gap:2px}}
li span{{overflow-wrap:anywhere}} small{{color:var(--mut)}}
</style></head><body><main>
<h1>🌴 Palmera · previews</h1>
<p>Une version du jeu par branche. Version principale : <a href="../">jouer</a>.</p>
<ul>
{items}
</ul>
</main></body></html>
'''
    with open(os.path.join(pdir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)


def prune(wt, branches):
    """Efface les previews des branches supprimées ; renvoie les noms effacés."""
    pdir = os.path.join(wt, PREVIEW_DIR)
    if not os.path.isdir(pdir):
        return []
    live = {slug(b) for b in branches if b not in (DEFAULT_BRANCH, PAGES_BRANCH)}
    gone = [n for n in sorted(os.listdir(pdir)) if os.path.isdir(os.path.join(pdir, n)) and n not in live]
    for n in gone:
        shutil.rmtree(os.path.join(pdir, n))
    if not any(os.path.isdir(os.path.join(pdir, n)) for n in os.listdir(pdir)):
        shutil.rmtree(pdir)
    else:
        preview_index(wt)
    return gone


def clear_root(wt):
    """Vide la racine de gh-pages sauf .git et les previews (pour y mettre la nouvelle version de main)."""
    for name in os.listdir(wt):
        if name in ('.git', PREVIEW_DIR):
            continue
        p = os.path.join(wt, name)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        else:
            os.remove(p)


def copy_into(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)


# ---------------------------------------------------------------- gh-pages

def remote_url():
    return os.environ.get('PAGES_REMOTE') or f'https://github.com/{REPO}.git'


def open_worktree():
    wt = tempfile.mkdtemp(prefix='gh-pages-')
    git('init', '-q', cwd=wt)
    git('config', 'user.name', 'github-actions[bot]', cwd=wt)
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com', cwd=wt)
    url = remote_url()
    if TOKEN and url.startswith('https://github.com/'):
        auth = base64.b64encode(f'x-access-token:{TOKEN}'.encode()).decode()
        git('config', 'http.https://github.com/.extraheader', f'AUTHORIZATION: basic {auth}', cwd=wt)
    git('remote', 'add', 'origin', url, cwd=wt)
    return wt


def remote_branches(wt):
    out = git('ls-remote', '--heads', 'origin', cwd=wt).stdout
    return [line.split('refs/heads/', 1)[1] for line in out.splitlines() if 'refs/heads/' in line]


def publish(change, message, attempts=6):
    """Applique change(worktree, branches) sur la dernière version de gh-pages et l'envoie.
    Renvoie (commit publié, a_changé)."""
    wt = open_worktree()
    try:
        for attempt in range(1, attempts + 1):
            branches = remote_branches(wt)
            if PAGES_BRANCH in branches:
                git('fetch', '-q', '--depth=1', '--no-tags', 'origin',
                    f'+refs/heads/{PAGES_BRANCH}:refs/remotes/origin/{PAGES_BRANCH}', cwd=wt)
                base = git('rev-parse', f'refs/remotes/origin/{PAGES_BRANCH}', cwd=wt).stdout.strip()
                git('checkout', '-q', '-f', '--detach', base, cwd=wt)
            else:
                base = ''
                git('read-tree', '--empty', cwd=wt)
            git('clean', '-qfdx', cwd=wt)

            change(wt, branches)
            with open(os.path.join(wt, '.nojekyll'), 'w'):
                pass
            git('add', '-A', cwd=wt)
            tree = git('write-tree', cwd=wt).stdout.strip()
            if base and tree == git('rev-parse', f'{base}^{{tree}}', cwd=wt).stdout.strip():
                log('gh-pages est déjà à jour.')
                return base, False
            commit = git('commit-tree', tree, '-m', message, cwd=wt).stdout.strip()
            r = git('push', '-q', f'--force-with-lease=refs/heads/{PAGES_BRANCH}:{base}', 'origin',
                    f'{commit}:refs/heads/{PAGES_BRANCH}', cwd=wt, check=False)
            if r.returncode == 0:
                log(f'gh-pages mis à jour ({commit[:7]}).')
                return commit, True
            log(f'Envoi refusé (essai {attempt}/{attempts}), quelqu\'un a publié en même temps : on recommence.\n'
                f'{r.stderr.strip()}')
            time.sleep(attempt * 2 + random.random() * 3)
        raise SystemExit('Impossible de mettre à jour gh-pages après plusieurs essais.')
    finally:
        shutil.rmtree(wt, ignore_errors=True)


# ---------------------------------------------------------------- GitHub Pages

def api(path):
    base = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
    req = urllib.request.Request(f'{base}/repos/{REPO}{path}', headers={
        'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'palmera-pages'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # réseau
        log(f'API Pages injoignable : {e}')
        return 0, None


SETUP_HINT = ('Settings → Pages → Build and deployment → Source : « Deploy from a branch » → '
              f'Branch : « {PAGES_BRANCH} » et « / (root) » → Save')


def check_pages():
    """Vérifie que GitHub Pages publie bien gh-pages. Renvoie (adresse du site, problème ou None)."""
    if LOCAL_TEST or not TOKEN:
        return site_base(), 'test local : vérification de GitHub Pages sautée'
    status, info = api('/pages')
    if status == 404:
        return site_base(), f'GitHub Pages n’est pas activé sur ce dépôt. Réglage unique : {SETUP_HINT}'
    if status != 200 or not info:
        return site_base(), None  # pas le droit de lire la config : on suppose que c'est bon
    url = (info.get('html_url') or site_base()).rstrip('/') + '/'
    src = info.get('source') or {}
    if info.get('build_type') == 'workflow':
        return url, f'GitHub Pages est réglé sur « GitHub Actions ». Réglage unique : {SETUP_HINT}'
    if src.get('branch') != PAGES_BRANCH or src.get('path', '/') != '/':
        return url, (f'GitHub Pages publie la branche « {src.get("branch")} » {src.get("path", "/")} au lieu de '
                     f'« {PAGES_BRANCH} » : les previews ne sont pas en ligne. Réglage unique : {SETUP_HINT}')
    return url, None


def wait_online(url, sha, timeout):
    """Attend que GitHub Pages serve ce commit (url/version.json)."""
    if timeout <= 0:
        return False
    log(f'Attente de la mise en ligne de {url} …')
    end = time.time() + timeout
    while time.time() < end:
        try:
            req = urllib.request.Request(f'{url}version.json?nocache={random.randrange(1 << 30)}',
                                         headers={'Cache-Control': 'no-cache', 'User-Agent': 'palmera-pages'})
            with urllib.request.urlopen(req, timeout=20) as r:
                if json.load(r).get('commit') == sha:
                    return True
        except Exception:
            pass
        time.sleep(10)
    return False


# ---------------------------------------------------------------- commandes

def head_info():
    r = git('log', '-1', '--format=%H%n%s', cwd=ROOT, check=False)
    lines = r.stdout.splitlines() if r.returncode == 0 else []
    return (lines[0] if lines else ''), (lines[1] if len(lines) > 1 else '')


def cmd_deploy(a):
    sha, subject = head_info()
    sha = a.sha or sha
    branch = a.branch
    is_main = branch == DEFAULT_BRANCH
    target = '' if is_main else f'{PREVIEW_DIR}/{slug(branch)}'
    tmp = tempfile.mkdtemp(prefix='site-')
    try:
        site = os.path.join(tmp, 'site')
        build_site(site, branch, is_main, sha, a.message or subject)

        def change(wt, branches):
            if is_main:
                clear_root(wt)
                copy_into(site, wt)
            else:
                dst = os.path.join(wt, target)
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                copy_into(site, dst)
            if DEFAULT_BRANCH in branches:  # garde-fou : liste des branches incomplète -> on n'efface rien
                gone = prune(wt, branches + [branch])
                if gone:
                    log('Previews effacées (branches supprimées) : ' + ', '.join(gone))
            if not is_main:
                preview_index(wt)

        label = 'main' if is_main else f'preview {slug(branch)}'
        publish(change, f'Palmera · {label} ({sha[:7]})')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    base, problem = check_pages()
    url = base + (target + '/' if target else '')
    play = f'{url}?v={sha[:7]}'
    write_output('url', play)
    online = False
    if problem:
        annotate('warning', problem)
    else:
        online = wait_online(url, sha, a.wait)
        if not online and a.wait > 0:
            annotate('warning', f'Pas encore en ligne après {a.wait} s : GitHub Pages met parfois plus longtemps. '
                                f'Réessaie le lien dans une minute.')

    title = 'version principale' if is_main else f'preview « {branch} »'
    lines = [f'### 🌴 Palmera · {title}', '',
             f'**[▶ Jouer à cette version]({play})**  ', f'`{play}`', '',
             f'- Branche `{branch}` · commit `{sha[:7]}`' + (f' · {subject}' if subject else '')]
    if is_main:
        lines.append(f'- Version hors ligne (un seul fichier) : {base}{OFFLINE_FILE}')
    lines.append(f'- Toutes les previews : {base}{PREVIEW_DIR}/')
    lines.append(f'- Statut : {"✅ en ligne" if online else ("⚠️ " + problem if problem else "⏳ publication en cours")}')
    write_summary('\n'.join(lines))
    annotate('notice', f'{title} : {play}')


def cmd_prune(a):
    gone_all = []

    def change(wt, branches):
        if DEFAULT_BRANCH not in branches:
            log('Liste des branches incomplète : rien n’est effacé.')
            return
        gone_all[:] = prune(wt, branches)

    publish(change, 'Palmera · nettoyage des previews')
    msg = ('Previews effacées : ' + ', '.join(gone_all)) if gone_all else 'Aucune preview à effacer.'
    log(msg)
    write_summary(f'### 🌴 Palmera · nettoyage\n\n{msg}')


def main():
    p = argparse.ArgumentParser(description='Publication de Palmera sur GitHub Pages (gh-pages).')
    sub = p.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('deploy', help='publie la branche courante')
    d.add_argument('--branch', required=True, help='nom de la branche publiée')
    d.add_argument('--sha', default='', help='commit publié (par défaut : HEAD)')
    d.add_argument('--message', default='', help='description (par défaut : message du commit)')
    d.add_argument('--wait', type=int, default=0 if LOCAL_TEST else 300,
                   help='secondes d’attente de la mise en ligne (0 = ne pas attendre)')
    sub.add_parser('prune', help='efface les previews des branches supprimées')
    a = p.parse_args()
    {'deploy': cmd_deploy, 'prune': cmd_prune}[a.cmd](a)


if __name__ == '__main__':
    main()
