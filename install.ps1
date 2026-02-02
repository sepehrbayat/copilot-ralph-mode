<#
.SYNOPSIS
    Ralph Mode - One-Click Installer for Windows

.DESCRIPTION
    Installs Ralph Mode for iterative AI development with GitHub Copilot CLI.

.EXAMPLE
    # Run in PowerShell:
    irm https://raw.githubusercontent.com/sepehrbayat/copilot-ralph-mode/main/install.ps1 | iex

    # Or download and run:
    .\install.ps1

.NOTES
    Requires: PowerShell 5.1+, Python 3.9+, Git
#>

$ErrorActionPreference = "Stop"

# Colors
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

# Banner
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "║   🔄 Copilot Ralph Mode Installer                         ║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "║   Iterative AI Development Loops for GitHub Copilot       ║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Blue
$pythonCmd = $null
$pythonVersion = $null

try {
    $pythonVersion = & python --version 2>&1
    if ($pythonVersion -match "Python (\d+\.\d+)") {
        $pythonCmd = "python"
        Write-Host "  ✓ $pythonVersion found" -ForegroundColor Green
    }
} catch {
    try {
        $pythonVersion = & python3 --version 2>&1
        if ($pythonVersion -match "Python (\d+\.\d+)") {
            $pythonCmd = "python3"
            Write-Host "  ✓ $pythonVersion found" -ForegroundColor Green
        }
    } catch {
        Write-Host "  ✗ Python not found!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install Python 3.9 or later:"
        Write-Host "  1. Download from https://www.python.org/downloads/"
        Write-Host "  2. Or use: winget install Python.Python.3.11"
        Write-Host ""
        Write-Host "Make sure to check 'Add Python to PATH' during installation!"
        exit 1
    }
}

# Check Python version
$versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
if ($versionMatch) {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
        Write-Host "  ✗ Python 3.9 or later required" -ForegroundColor Red
        exit 1
    }
}

# Check Git
Write-Host "[2/5] Checking Git installation..." -ForegroundColor Blue
try {
    $gitVersion = & git --version 2>&1
    Write-Host "  ✓ $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Git not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Git:"
    Write-Host "  1. Download from https://git-scm.com/download/win"
    Write-Host "  2. Or use: winget install Git.Git"
    exit 1
}

# Check GitHub CLI (optional)
Write-Host "[3/5] Checking GitHub Copilot CLI..." -ForegroundColor Blue
try {
    $null = & gh copilot --version 2>&1
    Write-Host "  ✓ GitHub Copilot CLI found" -ForegroundColor Green
} catch {
    Write-Host "  ! GitHub Copilot CLI not found (optional)" -ForegroundColor Yellow
    Write-Host "      Install later: gh extension install github/gh-copilot"
}

# Installation directory
$installDir = Join-Path $env:USERPROFILE ".ralph-mode"
Write-Host "[4/5] Installing to $installDir..." -ForegroundColor Blue

# Clone or update repository
if (Test-Path $installDir) {
    Write-Host "  Updating existing installation..."
    Push-Location $installDir
    git pull --quiet
    Pop-Location
} else {
    Write-Host "  Cloning repository..."
    git clone --quiet https://github.com/sepehrbayat/copilot-ralph-mode.git $installDir
}
Write-Host "  ✓ Repository ready" -ForegroundColor Green

# Add to PATH
Write-Host "[5/5] Setting up PATH..." -ForegroundColor Blue

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$installDir*") {
    $newPath = "$userPath;$installDir"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  ✓ Added to user PATH" -ForegroundColor Green
} else {
    Write-Host "  ✓ Already in PATH" -ForegroundColor Green
}

# Create alias in PowerShell profile
$profilePath = $PROFILE.CurrentUserAllHosts
$profileDir = Split-Path $profilePath -Parent

if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$profileContent = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
if ($profileContent -notlike "*ralph-mode*") {
    Add-Content $profilePath @"

# Ralph Mode - Iterative AI Development
function ralph { & $pythonCmd "$installDir\ralph_mode.py" @args }
"@
    Write-Host "  ✓ Added 'ralph' alias to PowerShell profile" -ForegroundColor Green
} else {
    Write-Host "  ✓ Alias already configured" -ForegroundColor Green
}

# Done!
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                           ║" -ForegroundColor Green
Write-Host "║   ✅ Installation Complete!                               ║" -ForegroundColor Green
Write-Host "║                                                           ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Quick Start:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Restart your terminal (or open a new one)"
Write-Host ""
Write-Host "  2. Navigate to your project:" -ForegroundColor White
Write-Host "     cd your-project" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Start a Ralph loop:" -ForegroundColor White
Write-Host '     ralph enable "Build a REST API" --max-iterations 20' -ForegroundColor Yellow
Write-Host "     .\ralph-mode.ps1 loop" -ForegroundColor Yellow
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  https://github.com/sepehrbayat/copilot-ralph-mode"
Write-Host ""
