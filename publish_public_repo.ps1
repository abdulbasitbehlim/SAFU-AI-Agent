param(
    [string]$RepoName = "Safu-AI-Agent",
    [string]$Description = "SAFU - Windows-first multi-model personal AI assistant and desktop automation agent"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not on PATH."
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required for automatic publishing. Install it, then run: gh auth login"
}

gh auth status | Out-Host
python scripts/check_public_repo.py
python verify_safu.py

if (-not (Test-Path .git)) {
    git init
}

git add .
python scripts/check_public_repo.py

if (-not (git config user.name)) {
    throw "Set your Git name first: git config --global user.name 'Your Name'"
}
if (-not (git config user.email)) {
    throw "Set your Git email first: git config --global user.email 'you@example.com'"
}

$hasCommit = $true
try { git rev-parse --verify HEAD *> $null } catch { $hasCommit = $false }
if (-not $hasCommit) {
    git commit -m "Initial public release of SAFU"
} elseif (git status --porcelain) {
    git commit -m "Update SAFU public release"
}

# This creates a PUBLIC repository under the GitHub account authenticated by gh.
gh repo create $RepoName --public --description $Description --source . --remote origin --push

Write-Host "Published successfully." -ForegroundColor Green
