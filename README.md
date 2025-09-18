# AIM

Ce dépôt fournit un utilitaire OCR Python ainsi qu'un script d'installation Windows
capable d'installer automatiquement Tesseract OCR. L'objectif est de proposer un
installateur unique afin de ne plus avoir à installer Tesseract manuellement.

## Aperçu

- **CLI Python** : la commande `aim-cli` (ou `python -m aim`) permet de lancer un OCR
  sur une image en s'appuyant sur `pytesseract` et Tesseract.
- **Installateur Windows** : `installers/windows/install.ps1` télécharge et installe
  automatiquement Tesseract, configure les variables d'environnement et installe ce
  projet dans un environnement virtuel dédié.

## Installation sur Windows

1. Installez Python 3.9 ou supérieur sur la machine cible (activer l'option « Ajouter
   Python au PATH » est recommandé).
2. Téléchargez le contenu de ce dépôt ou incluez-le dans le package de distribution
   de votre application.
3. Ouvrez un terminal PowerShell **en tant qu'administrateur** (Tesseract s'installe
   sous `Program Files`).
4. Exécutez l'installateur :

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass -Force
   ./installers/windows/install.ps1
   ```

   Le script :

   - Télécharge la dernière version 64 bits de Tesseract fournie par
     [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) ;
   - Installe silencieusement Tesseract si nécessaire et ajoute son répertoire au PATH ;
   - Crée (ou met à jour) un environnement virtuel Python dans `%LOCALAPPDATA%\aim` ;
   - Installe ce package Python et ses dépendances (`pytesseract`, `Pillow`, ...)
     dans l'environnement créé ;
   - Génère des scripts de lancement (`aim.cmd` / `aim.ps1`) pointant vers l'environnement.

### Options de l'installateur

Le script accepte quelques paramètres utiles :

```powershell
./installers/windows/install.ps1 -InstallRoot "C:\\MonAppli" -ForceReinstall
```

- `-InstallRoot` : répertoire cible (par défaut `%LOCALAPPDATA%\aim`).
- `-TesseractInstallerUrl` : URL personnalisée vers un installateur Tesseract.
- `-ForceReinstall` : force la recréation de l'environnement virtuel et la
  réinstallation de Tesseract même s'ils existent déjà.

## Utilisation de la CLI

Une fois l'installation terminée :

```powershell
# Affiche la version de Tesseract détectée
C:\Users\<Vous>\AppData\Local\aim\aim.cmd --show-version

# Lance un OCR sur une image
C:\Users\<Vous>\AppData\Local\aim\aim.cmd "C:\\chemin\\vers\\mon_image.png" --lang fra
```

Vous pouvez également utiliser `python -m aim` depuis l'environnement virtuel installé.

## Désinstallation

1. Supprimez le dossier d'installation (par défaut `%LOCALAPPDATA%\aim`).
2. Facultatif : supprimez la clé d'environnement utilisateur `TESSDATA_PREFIX` et
   retirez le chemin `C:\Program Files\Tesseract-OCR` de votre PATH utilisateur si
   vous ne souhaitez plus Tesseract sur la machine.

## Développement

Pour contribuer au projet :

```bash
python -m venv .venv
source .venv/bin/activate  # sous Windows : .venv\\Scripts\\activate
pip install --upgrade pip
pip install -e .
```

Les sources principales se trouvent dans `src/aim`. La CLI est implémentée dans
`src/aim/cli.py` et le script d'installation se trouve dans `installers/windows`.
