# Rapid Shot Heat Overlay

Outil autonome destiné à suivre en temps réel la Heat du sort **Rapid Shot** dans *Path of Exile 2*. L'application s'appuie exclusivement sur la capture d'écran, le template matching et l'OCR pour respecter les règles du jeu.

## Fonctionnalités principales

- **Overlay transparent & click-through** : jauge circulaire toujours visible mais qui laisse passer les clics.
- **Vision par ordinateur** : localisation multi-échelle du buff Rapid Shot et lecture fiable du compteur de Heat via Tesseract.
- **Modes d'affichage** : jauge centrée ou attachée au curseur avec offset configurable.
- **Personnalisation complète** : taille, largeur d'anneau, gap, couleurs (thèmes), ticks fixes, halo visuel et affichage numérique optionnel.
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
| `--provider {cv,sim}` | Sélectionne le fournisseur de Heat. |
| `--capture-backend {auto,dxcam,mss,vulkan}` | Choisit le backend de capture (`auto` tente DirectX puis Vulkan). |
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

- **cv** : capture via `dxcam` (DirectX) ou `mss` (capture générique compatible Vulkan) suivant le backend sélectionné (`--capture-backend` ou `vision.capture_backend` dans la config), puis applique OpenCV pour le template matching multi-échelle et Tesseract pour l'OCR. C'est le mode recommandé en jeu.
- **sim** : fournisseur sinusoïdal utile pour valider l'UI ou enregistrer des démonstrations.

## Packaging Windows (EXE + installeur)

Le script `packaging/windows/build_installer.py` automatise la création d'un binaire PyInstaller
et d'un installeur Inno Setup qui embarquent Tesseract en version portable.

1. Préparez un environnement Python sur Windows et installez les dépendances :

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -e .
   pip install pyinstaller
   ```

2. Lancez le script de packaging :

   ```powershell
   python packaging\windows\build_installer.py
   ```

   Le script télécharge automatiquement l'archive portable de Tesseract, copie son contenu dans
   `dist\rapid-shot-overlay\tesseract` puis génère l'installeur
   `dist\installer\RapidShotHeatOverlaySetup.exe` (si `iscc.exe` est disponible).

3. Pour personnaliser le processus, plusieurs options sont disponibles :

   - `--skip-installer` : conserve uniquement le dossier PyInstaller + Tesseract.
   - `--onefile` : génère un exécutable `--onefile` puis crée un dossier bundle contenant Tesseract.
   - `--tesseract-url <URL>` : utilise une autre archive portable de Tesseract.

L'application détecte automatiquement `tesseract/tesseract.exe` lorsqu'il est situé à côté de
`rapid-shot-overlay.exe`, que ce soit dans le dossier PyInstaller ou dans le répertoire
d'installation généré par Inno Setup. Il n'est donc plus nécessaire d'installer Tesseract
séparément.

## Dépannage

- Activez les logs détaillés via `--log-level DEBUG` pour surveiller le matching et l'OCR.
- Vérifiez que le template Rapid Shot est net et que la zone OCR couvre strictement les chiffres.
- En cas de changement de résolution ou de scaling Windows, relancez le wizard (Ctrl+K) pour recalculer les offsets relatifs.

## Licence

Projet fourni tel quel, usage personnel recommandé.
