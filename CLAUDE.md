# Palmera : consignes pour Claude

Jeu de ville ouverte en 3D. three.js r147 (scripts UMD dans `lib/`), une seule page `index.html` (≈2700 lignes),
modèles dans `assets/`. L'utilisateur parle français : réponses en français.

## Façon de travailler (demandée par l'utilisateur)

1. **Une branche par demande**, créée depuis `main` à jour : prendre la branche de travail imposée par la session si
   elle existe, sinon `git checkout -b feature/<sujet-court>`. Ne jamais développer directement sur `main`.
2. Tester en local (voir plus bas), committer, **pousser la branche**.
3. Le workflow **Pages** publie la preview sur `https://adrien426.github.io/Palmera/preview/<slug>/`.
   - Le `<slug>` est le nom de la branche, accents retirés, en minuscules, et les autres caractères remplacés par `-`.
     Par exemple, `feature/Météo` devient `feature-meteo`.
   - Le run attend que la preview soit en ligne. Son résumé et son annotation « notice » donnent le lien exact,
     avec `?v=<commit>` pour éviter le cache du navigateur.
   - Vérifier que le run est vert (outils GitHub `actions_list` / `get_job_logs`), puis **donner le lien** à l'utilisateur.
4. Quand l'utilisateur valide (« c'est bon »), **fusionner dans `main`** et pousser `main` :
   `git checkout main && git pull && git merge --no-ff <branche> && git push origin main`.
   Le site principal https://adrien426.github.io/Palmera/ est alors mis à jour, ainsi que `Palmera-jeu.html` (hors ligne).
5. Pas de pull request sauf demande explicite. Ne jamais modifier `gh-pages` à la main : `tools/pages.py` la réécrit
   à chaque déploiement, et elle n'a qu'un seul commit.

## Code

- `index.html` est découpé en sections `/* ================= NOM`. Pour en avoir la carte :
  `grep -n '/\* =====' index.html`.
- Les modèles sont chargés par `getBuf(f)`, dans cet ordre :
  1. `window.__ASSETS` (version hors ligne) ;
  2. `assets/<f>` ;
  3. `REMOTE` (le dossier `assets/` du site principal).
- Qualité : `REAL` (faible / moyen / base / max) et `FPS` (30…240, 0 = sans limite). « Max ∞ » dans une ligne met tout au Max.
  - Base est la qualité de référence (l'ancien Max). Les tableaux par niveau (`SHD`, `LIFE_N`, `DRV`…) ont une entrée `base`.
  - Max ∞ ajoute : reflets de la ville en temps réel (`CITYENV`, une face de cube par image), AO pleine définition,
    une ville plus dense et une physique plus fine.
- Accessoires d'armes : `OPTICS`, `MOD_FOR`, `MOD_INFO`, `PAINTS` et `player.mods[id]` (1 = monté, 2 = acheté mais retiré).
  Voir aussi `zoomOf` (lunette), `magOf` (chargeur), `decorateGun` (pièces 3D), `updateGunMods` (laser, lampe),
  `scopeUI` (réticule) et `modItems` (pages de l'armurerie).
  - En Max ∞, le régulateur `MAXQ` (`maxTick`) ne coupe jamais d'effet. Il ne change que la définition calculée
    (`maxSteps()` : de 0,6× l'écran, sans descendre sous 1 pixel par pixel CSS, jusqu'au suréchantillonnage 2×).
    Il vérifie chaque changement et revient en arrière si celui-ci fait perdre des images/s.
  - En Faible et Moyen, `GOV` (`govTick`) baisse aussi les effets.
- Intérieurs (section `INTÉRIEURS`) : chaque type de lieu (`INT_KINDS`) a sa pièce 3D, construite à la première visite
  à x ≈ -5600 (`intRoom`, `INT_FURN[type]`).
  - `enterInterior` / `exitInterior` font le fondu et le téléport. Pendant la visite, `player.inside` est défini et
    `playerPos()` renvoie la porte, pour que la ville continue autour.
  - `collideCircle` ne limite plus la carte au-delà de x = -4500. `intCam` garde la caméra dans la pièce.
  - Braquage : viser le caissier (`updateInterior`). La police est prévenue à la sortie.
- Les réglages et la sauvegarde sont dans le `localStorage` : `palmera-save`, `palmera-fps`, etc.
  Les previews et le site principal partagent la même origine, donc la même sauvegarde.
- Points d'accès pour les tests : `window.__palmera` (`startGame`, `giveWeapon`, `cars`, `peds`, `player`, `setLevel`,
  `MODELS`…) et `window.__dbgSet`. Le hash `#nopf` coupe la qualité adaptative, pour des mesures stables.

## Tests

- Servir le dossier : `python3 -m http.server 8000`, puis ouvrir `http://localhost:8000/#nopf`.
- Playwright avec Chromium en WebGL logiciel :
  `chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']})`.
  Le rendu y est lent : utiliser une petite fenêtre (640×360) et le réalisme « moyen ».
- Attendre que `#play` soit cliquable, puis lancer `__palmera.startGame()` et vérifier qu'aucune erreur n'apparaît
  dans la console (`pageerror`).
- Version hors ligne : `python3 tools/build_offline.py`, puis tester `file://…/Palmera-jeu.html`.
