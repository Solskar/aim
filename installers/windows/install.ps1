[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "aim"),
    [string]$TesseractInstallerUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe",
    [switch]$ForceReinstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Message)
    Write-Host "`n== $Message ==" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Message)
    Write-Host "  -> $Message" -ForegroundColor Green
}

function Resolve-ProjectRoot {
    $scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
    return (Resolve-Path (Join-Path $scriptDir "..\..")).Path
}

function Get-TesseractPath {
    $candidates = @(
        "$env:ProgramFiles\\Tesseract-OCR\\tesseract.exe",
        "$env:ProgramFiles(x86)\\Tesseract-OCR\\tesseract.exe",
        "$env:LOCALAPPDATA\\Programs\\Tesseract-OCR\\tesseract.exe"
    )

    $command = Get-Command -Name tesseract.exe -ErrorAction SilentlyContinue
    if ($null -ne $command -and $command.Source) {
        $candidates += $command.Source
    }

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Download-TesseractInstaller {
    param([string]$Url)

    $target = Join-Path ([IO.Path]::GetTempPath()) "tesseract-installer-$([Guid]::NewGuid()).exe"
    Write-Step "Téléchargement de Tesseract depuis $Url"
    Invoke-WebRequest -Uri $Url -OutFile $target -UseBasicParsing
    return $target
}

function Install-Tesseract {
    param(
        [string]$Url,
        [switch]$Force
    )

    if (-not $Force) {
        $existing = Get-TesseractPath
        if ($null -ne $existing) {
            Write-Step "Tesseract déjà détecté : $existing"
            return $existing
        }
    }

    $installer = Download-TesseractInstaller -Url $Url
    try {
        Write-Step "Installation silencieuse de Tesseract..."
        $process = Start-Process -FilePath $installer -ArgumentList '/SILENT', '/ALLUSERS' -PassThru -Wait -WindowStyle Hidden
        if ($process.ExitCode -ne 0) {
            throw "L'installation de Tesseract a échoué avec le code $($process.ExitCode)."
        }
    }
    finally {
        Remove-Item -LiteralPath $installer -ErrorAction SilentlyContinue
    }

    $path = Get-TesseractPath
    if (-not $path) {
        throw "Impossible de localiser Tesseract après l'installation."
    }

    return $path
}

function Update-UserPath {
    param([string]$Directory)

    $resolved = (Resolve-Path -LiteralPath $Directory).Path
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @()
    if ($current) {
        $entries = $current -split ';' | Where-Object { $_ }
    }

    foreach ($entry in $entries) {
        if ([string]::Equals($entry.TrimEnd('\'), $resolved.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
            return
        }
    }

    $newPath = if ($current) { "$current;$resolved" } else { $resolved }
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    $env:PATH = "$resolved;" + $env:PATH
}

function Configure-TesseractEnvironment {
    param([string]$TesseractExecutable)

    $tesseractDir = Split-Path -Path $TesseractExecutable -Parent
    Update-UserPath -Directory $tesseractDir
    [Environment]::SetEnvironmentVariable('TESSDATA_PREFIX', $tesseractDir, 'User')
    $env:TESSDATA_PREFIX = $tesseractDir
    Write-Step "Variables d'environnement mises à jour pour Tesseract ($tesseractDir)."
}

function Get-PythonCommand {
    $python = Get-Command -Name python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return @{ Path = $python.Source; Args = @() }
    }

    $pyLauncher = Get-Command -Name py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{ Path = $pyLauncher.Source; Args = @('-3') }
    }

    throw "Python 3 n'a pas été détecté. Installez Python 3.9+ avant de lancer ce script."
}

function Invoke-ExternalCommand {
    param(
        [hashtable]$Command,
        [string[]]$Arguments
    )

    & $Command.Path @($Command.Args + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        $argumentList = ($Arguments -join ' ')
        throw "La commande '$($Command.Path) $argumentList' a échoué avec le code $LASTEXITCODE."
    }
}

function Ensure-VirtualEnvironment {
    param(
        [hashtable]$PythonCommand,
        [string]$VenvPath,
        [switch]$Force
    )

    if ($Force -and (Test-Path -LiteralPath $VenvPath)) {
        Write-Step "Suppression de l'environnement virtuel existant ($VenvPath)."
        Remove-Item -LiteralPath $VenvPath -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $VenvPath)) {
        Write-Step "Création de l'environnement virtuel ($VenvPath)."
        Invoke-ExternalCommand -Command $PythonCommand -Arguments @('-m', 'venv', $VenvPath)
    }
    else {
        Write-Step "Environnement virtuel existant détecté ($VenvPath)."
    }

    $venvPython = Join-Path $VenvPath 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "L'environnement virtuel semble corrompu : python.exe est introuvable."
    }

    return @{ Path = $venvPython; Args = @() }
}

function Install-PythonProject {
    param(
        [hashtable]$PythonCommand,
        [string]$ProjectRoot,
        [switch]$Force
    )

    Write-Step "Mise à jour de pip et des outils de build."
    Invoke-ExternalCommand -Command $PythonCommand -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel')

    if ($Force) {
        Write-Step "Réinstallation forcée du package aim."
        Invoke-ExternalCommand -Command $PythonCommand -Arguments @('-m', 'pip', 'install', '--upgrade', '--force-reinstall', $ProjectRoot)
    }
    else {
        Invoke-ExternalCommand -Command $PythonCommand -Arguments @('-m', 'pip', 'install', '--upgrade', $ProjectRoot)
    }
}

function Ensure-Launchers {
    param(
        [string]$InstallPath,
        [string]$VenvPath
    )

    $cmdPath = Join-Path $InstallPath 'aim.cmd'
    $cmdContent = "@echo off`r`n\"%~dp0venv\\Scripts\\python.exe\" -m aim %*`r`n"
    Set-Content -Path $cmdPath -Value $cmdContent -Encoding ASCII

    $ps1Path = Join-Path $InstallPath 'aim.ps1'
    $ps1Content = "& \"$VenvPath\\Scripts\\python.exe\" -m aim @args"
    Set-Content -Path $ps1Path -Value $ps1Content -Encoding UTF8

    Write-Step "Scripts de lancement générés :`n  - $cmdPath`n  - $ps1Path"
}

function Ensure-InstallRoot {
    param([string]$Path)

    $directory = New-Item -ItemType Directory -Path $Path -Force
    return (Resolve-Path -LiteralPath $directory.FullName).Path
}

$projectRoot = Resolve-ProjectRoot
$installPath = Ensure-InstallRoot -Path $InstallRoot

Write-Section "Installation de AIM"
Write-Step "Dossier projet : $projectRoot"
Write-Step "Dossier d'installation : $installPath"

$tesseractExe = Install-Tesseract -Url $TesseractInstallerUrl -Force:$ForceReinstall
Configure-TesseractEnvironment -TesseractExecutable $tesseractExe

$python = Get-PythonCommand
$venvCommand = Ensure-VirtualEnvironment -PythonCommand $python -VenvPath (Join-Path $installPath 'venv') -Force:$ForceReinstall
Install-PythonProject -PythonCommand $venvCommand -ProjectRoot $projectRoot -Force:$ForceReinstall
Ensure-Launchers -InstallPath $installPath -VenvPath (Join-Path $installPath 'venv')

Write-Section "Installation terminée"
Write-Host "Tesseract installé à : $tesseractExe"
Write-Host "AIM est disponible via : $(Join-Path $installPath 'aim.cmd')"
Write-Host "Vous devrez peut-être rouvrir votre terminal pour prendre en compte les nouvelles variables d'environnement."
