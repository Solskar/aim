# Installateur Windows

Le script `install.ps1` automatise l'installation de Tesseract et de l'application
Python fournie dans ce dépôt. Il s'agit d'un installateur « sans assistance » qui
peut être exécuté directement sur une machine cliente ou intégré dans un installeur
NSIS/Inno Setup existant.

## Pré-requis

- Windows 10/11
- PowerShell 5.1 ou 7+
- Python 3.9 ou supérieur installé localement
- Accès Internet pour télécharger l'installateur Tesseract et les dépendances Python

## Utilisation rapide

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
./install.ps1
```

Le script s'occupe de :

1. Télécharger l'installateur Tesseract 64 bits (`tesseract-ocr-w64-setup-5.3.3.20231005.exe`).
2. Lancer l'installation silencieuse de Tesseract (si nécessaire) et ajouter le chemin
   `Tesseract-OCR` au PATH utilisateur.
3. Créer un environnement virtuel Python dédié et y installer ce package (`pip install .`).
4. Générer des scripts de lancement (`aim.cmd`, `aim.ps1`) qui invoquent l'application
   depuis l'environnement virtuel.

## Paramètres disponibles

- `InstallRoot` : dossier cible de l'installation (`%LOCALAPPDATA%\aim` par défaut).
- `TesseractInstallerUrl` : URL vers un installateur Tesseract alternatif.
- `ForceReinstall` : force la réinstallation complète même si Tesseract et l'environnement
  virtuel existent déjà.

Exemple :

```powershell
./install.ps1 -InstallRoot "C:\\Program Files\\AIM" -ForceReinstall
```

## Intégration dans un installeur graphique

Ce script peut être invoqué depuis un installeur NSIS/Inno Setup en arrière-plan pour
installer silencieusement Tesseract avant de copier votre application. Veillez à exécuter
le script avec les droits administrateur pour permettre l'installation de Tesseract dans
`Program Files`.
