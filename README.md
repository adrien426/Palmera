# 🌴 Palmera

Une ville ouverte en 3D, jouable directement dans le navigateur (PC, Mac, téléphone).

**▶ Jouer : https://adrien426.github.io/Palmera/**

Version hors ligne, en un seul fichier à télécharger : https://adrien426.github.io/Palmera/Palmera-jeu.html

## Versions en ligne

| Branche | Adresse |
| --- | --- |
| `main` | https://adrien426.github.io/Palmera/ |
| toute autre branche | `https://adrien426.github.io/Palmera/preview/<branche>/` |
| liste des previews | https://adrien426.github.io/Palmera/preview/ |

Dans l'adresse d'une preview, le nom de la branche est écrit en minuscules et les caractères spéciaux deviennent des `-`.
Par exemple, `feature/meteo` donne `preview/feature-meteo/`.

Le workflow **Pages** (`.github/workflows/pages.yml`) se lance à chaque push :

1. Il copie le jeu sur la branche `gh-pages`. Pour `main`, il le met à la racine et y ajoute la version hors ligne. Pour une autre branche, il le met dans `preview/<branche>/`.
2. Il attend que GitHub Pages ait mis la version en ligne. Le lien est dans le résumé du run (onglet *Actions*).
3. Quand une branche est supprimée, sa preview est effacée.

La façon de travailler :

1. Chaque demande est faite sur une nouvelle branche.
2. Le push de la branche crée une preview à tester.
3. Quand la preview est validée, la branche est fusionnée dans `main`, ce qui met à jour le site principal.

### Réglage unique de GitHub Pages

*Settings → Pages → Build and deployment → Source : **Deploy from a branch** → Branch : **gh-pages** / **(root)** → Save*

Tant que Pages publie `main`, le site principal fonctionne mais les previews ne sont pas en ligne. Le résumé du run le signale.

## Contenu du dépôt

| Fichier | Rôle |
| --- | --- |
| `index.html` | le jeu (une seule page : HTML, CSS et JavaScript) |
| `assets/` | modèles 3D (`.glb`) et animations (`.json`) |
| `lib/` | three.js r147 et ses modules (licence MIT) |
| `tools/build_offline.py` | fabrique `Palmera-jeu.html`, le jeu complet dans un seul fichier |
| `tools/pages.py` | publication sur `gh-pages`, utilisée par GitHub Actions |
| `.github/workflows/pages.yml` | déploiement automatique (site principal et previews) |

La branche `gh-pages` est générée automatiquement. Ne la modifie pas à la main.

## Lancer le jeu en local

```bash
python3 -m http.server 8000        # puis ouvrir http://localhost:8000/
python3 tools/build_offline.py     # crée Palmera-jeu.html (double-clic pour jouer sans connexion)
```

Les commandes du jeu (clavier, souris, manette tactile) sont affichées dans le menu.
