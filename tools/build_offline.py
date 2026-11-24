#!/usr/bin/env python3
"""Fabrique Palmera-jeu.html : le jeu complet dans un seul fichier, jouable sans connexion
(double-clic sur le fichier, clé USB, téléphone...).

Les scripts de lib/ et les fichiers de assets/ sont intégrés dans la page
(les modèles en base64 dans window.__ASSETS, que le jeu lit en premier).

Utilisation :  python3 tools/build_offline.py [dossier_du_jeu] [fichier_de_sortie]
"""
import base64
import json
import os
import re
import sys


def build(root='.', out=None):
    root = os.path.abspath(root)
    out = out or os.path.join(root, 'Palmera-jeu.html')
    with open(os.path.join(root, 'index.html'), encoding='utf-8') as f:
        html = f.read()

    libs = []

    def inline(m):
        with open(os.path.join(root, m.group(1)), encoding='utf-8') as f:
            code = f.read()
        libs.append(m.group(1))
        return '<script>' + code.replace('</script', '<\\/script') + '</script>'

    html = re.sub(r'<script src="(lib/[^"]+)"></script>', inline, html)

    adir = os.path.join(root, 'assets')
    data = {}
    for name in sorted(os.listdir(adir)):
        path = os.path.join(adir, name)
        if name.startswith('.') or not os.path.isfile(path):
            continue
        with open(path, 'rb') as f:
            data[name] = base64.b64encode(f.read()).decode('ascii')

    first = html.index('<script')
    html = (html[:first] + '<script>window.__ASSETS=' + json.dumps(data, separators=(',', ':'))
            + ';</script>\n' + html[first:])
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    return out, len(libs), len(data), len(html.encode('utf-8'))


if __name__ == '__main__':
    out, n_libs, n_assets, size = build(*sys.argv[1:3])
    print(f'{out} : {n_libs} bibliothèques, {n_assets} fichiers de assets/, {size / 1e6:.1f} Mo')
