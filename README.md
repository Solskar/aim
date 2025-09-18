# Rapid Shot Heat Overlay

Outil autonome destiné à suivre en temps réel la Heat du sort **Rapid Shot** dans *Path of Exile 2*. L'application s'appuie exclusivement sur la capture d'écran, le template matching et l'OCR pour respecter les règles du jeu.

## Fonctionnalités principales

- **Overlay transparent & click-through** : jauge circulaire toujours visible mais qui laisse passer les clics.
- **Vision par ordinateur** : localisation multi-échelle du buff Rapid Shot et lecture fiable du compteur de Heat via Tesseract.
- **Modes d'affichage** : jauge centrée ou attachée au curseur avec offset configurable.
- **Personnalisation complète** : taille, largeur d'anneau, gap, couleurs (thèmes), ticks fixes, halo visuel et affichage numérique optionnel.
- **Compatibilité DirectX & Vulkan** : capture écran possible via `dxcam` ou `mss` (Windows Graphics Capture), sélection automatique du backend le plus adapté.
- **Assistant de calibration** : sélection guidée de l'icône, de la barre de buffs et de la zone OCR. Relance possible via raccourcis (Ctrl+K/I/B/O).
- **Sauvegarde automatique** : les paramètres sont stockés dans `config.json` (chemins de template, zone de capture, offsets OCR, etc.).
- **Mode simulation** : un fournisseur interne permet de tester l'interface sans lancer le jeu.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Lancement rapide

```bash
heat-overlay --mode center --debug
```

Par défaut le fournisseur de données est `cv` (vision). Pour tester l'overlay sans dépendances externes, utilisez :

```bash
heat-overlay --provider sim --mode cursor --debug
```

## Options CLI

| Option | Description |
| --- | --- |
| `--mode {center,cursor}` | Choisit le mode d'affichage de la jauge. |
| `--size <int>` | Diamètre de la jauge en pixels. |
| `--ring <int>` | Largeur de l'anneau. |
| `--gap <float>` | Angle libre en degrés. |
| `--threshold <int>` | Valeur déclenchant le halo rouge. |
| `--max <int>` | Valeur maximale de la jauge. |
| `--ticks a,b,c` | Position des ticks fixes. |
| `--cursor-offset x,y` | Décalage appliqué en mode curseur. |
| `--debug` | Affiche la valeur numérique au centre. |
| `--theme {default,dark,neo}` | Choisit un thème prédéfini. |
| `--template PATH` | Spécifie un template d'icône existant. |
| `--buffbar x,y,w,h` | Définit la région de capture de la barre de buffs. |
| `--ocrp ox,oy,w,h` | Définit la zone OCR relative à l'icône. |
| `--tesseract PATH` | Chemin vers `tesseract.exe` portable. |
| `--capture-backend {auto,dxcam,mss}` | Forcer un backend de capture (`mss` recommandé pour Vulkan plein écran). |
| `--provider {cv,sim}` | Sélectionne le fournisseur de Heat. |
| `--config PATH` | Fichier de configuration personnalisé. |
| `--log-level` | Niveau de log (`INFO`, `DEBUG`, ...). |

## Calibration

Au premier lancement l'assistant n'est pas obligatoire : utilisez `Ctrl+K` pour afficher le wizard plein écran.

1. **Icône** : capture de l'icône Rapid Shot ⇒ sauvegardée dans `assets/buff_template_captured.png`.
2. **Barre de buffs** : délimite la zone de recherche pour accélérer le matching.
3. **Zone OCR** : définit une zone relative à l'icône pour extraire le compteur numérique.

Les raccourcis permettent de relancer individuellement chaque étape :

- `Ctrl+I` : recapture l'icône.
- `Ctrl+B` : redéfinit la bande des buffs.
- `Ctrl+O` : recalcule la zone OCR.

Toutes les informations sont écrites dans `config.json` sous la racine du projet (ou le chemin défini via `--config`).

## Fournisseur de Heat

- **cv** : utilise `dxcam` ou `mss` (Windows Graphics Capture) pour capturer l'écran quelle que soit l'API graphique (DirectX, Vulkan), OpenCV pour le template matching multi-échelle et Tesseract pour l'OCR. Le backend est sélectionné automatiquement mais peut être forcé via `--capture-backend`.
- **sim** : fournisseur sinusoïdal utile pour valider l'UI ou enregistrer des démonstrations.

## Packaging en EXE

1. Téléchargez la version portable de Tesseract et placez-la dans un dossier `tesseract/` à côté de l'exécutable.
2. Utilisez PyInstaller :

   ```bash
   pyinstaller --name rapid-shot-overlay --noconsole --onefile \
     --add-data "assets/*;assets" \
     --collect-submodules heat_overlay \
     -p src heat_overlay/app.py
   ```

3. Copiez le dossier portable de Tesseract et `config.json` à côté du binaire généré.

## Dépannage

- Activez les logs détaillés via `--log-level DEBUG` pour surveiller le matching et l'OCR.
- Vérifiez que le template Rapid Shot est net et que la zone OCR couvre strictement les chiffres.
- En cas de changement de résolution ou de scaling Windows, relancez le wizard (Ctrl+K) pour recalculer les offsets relatifs.

## Licence

Projet fourni tel quel, usage personnel recommandé.
