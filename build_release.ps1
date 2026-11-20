<#
.SYNOPSIS
  Builds a release of Signal generator: PyInstaller (dist\signal_generator) + Inno Setup installer (release\signal_generator_setup_<version>.exe).

.DESCRIPTION
  Run it from anywhere:   .\build_release.ps1      (it works from software\lsl-signal-generator)
  The version is read from src\version.py (single place; it is also shown in the window title).
  Requires: the virtual environment .venv (requirements.txt + PyInstaller), and Inno Setup 6 or 7 (iscc.exe).

.PARAMETER SkipBuild
  Do not run PyInstaller: reuse dist\signal_generator (to try changes of the installer script only).

.PARAMETER SkipInstaller
  Run PyInstaller only (it is what build_command.txt does).
#>
param(
    [switch]$SkipBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Fail($message) { Write-Host "ERROR: $message" -ForegroundColor Red; exit 1 }

# PyInstaller and ISCC write their progress to stderr: that is not an error. Native commands are judged by their exit code only
function Invoke-Native($exe, $arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $exe @arguments 2>&1 | ForEach-Object { Write-Host "$_" } } finally { $ErrorActionPreference = $previous }
    return [int]$LASTEXITCODE
}

# ---- Version (single source of truth: src\version.py)
$versionLine = Select-String -Path 'src\version.py' -Pattern '^\s*VERSION\s*=\s*["''](.+?)["'']' | Select-Object -First 1
if (-not $versionLine) { Fail 'VERSION not found in src\version.py' }
$version = $versionLine.Matches[0].Groups[1].Value
Write-Host "Signal generator version $version" -ForegroundColor Cyan

# ---- PyInstaller
if (-not $SkipBuild) {
    $pyinstaller = '.\.venv\Scripts\pyinstaller.exe'
    if (-not (Test-Path $pyinstaller)) { Fail "PyInstaller not found in $pyinstaller (create the venv and install requirements.txt + pyinstaller)" }
    $required = @('.venv\Lib\site-packages\pylsl\lib\lsl.dll', 'src\main.py', 'src\signal_generator.ui', 'src\gui\style.css',
                  'src\gui\images\icons\icon.ico')
    foreach ($f in $required) { if (-not (Test-Path $f)) { Fail "Missing file: $f" } }

    # Same options as build_command.txt
    $arguments = @(
        '--noconfirm', '--clean', '--onedir', '--windowed', 'src/main.py',
        '--name', 'signal_generator', '--icon', 'src/gui/images/icons/icon.ico', '--paths', 'src',
        '--add-data', '.venv/Lib/site-packages/pylsl/lib/lsl.dll;pylsl/lib/',
        '--add-data', 'src/signal_generator.ui;.', '--add-data', 'src/gui/style.css;gui',
        '--add-data', 'src/gui/images;gui/images'
    )
    Write-Host 'Running PyInstaller...' -ForegroundColor Cyan
    $code = Invoke-Native $pyinstaller $arguments
    if ($code -ne 0) { Fail "PyInstaller failed (exit code $code)" }
}
if (-not (Test-Path 'dist\signal_generator\signal_generator.exe')) { Fail 'dist\signal_generator\signal_generator.exe does not exist' }
# PyInstaller 6 puts the resources in _internal, PyInstaller 5 (pinned in requirements.txt) next to the .exe
if (-not ((Test-Path 'dist\signal_generator\signal_generator.ui') -or (Test-Path 'dist\signal_generator\_internal\signal_generator.ui'))) { Fail 'signal_generator.ui is not in dist\signal_generator (is the build complete?)' }

if ($SkipInstaller) { Write-Host 'Done (installer skipped).' -ForegroundColor Green; exit 0 }

# ---- Inno Setup
$candidates = @(
    (Get-Command iscc.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }),
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $candidates) { Fail 'Inno Setup (ISCC.exe) not found. Install it with: winget install JRSoftware.InnoSetup' }
$iscc = @($candidates)[0]

Write-Host "Building the installer with $iscc ..." -ForegroundColor Cyan
$code = Invoke-Native $iscc @("/DAppVersion=$version", 'installer\signal_generator.iss')
if ($code -ne 0) { Fail "Inno Setup failed (exit code $code)" }

$installer = "release\signal_generator_setup_$version.exe"
if (-not (Test-Path $installer)) { Fail "The installer was not created: $installer" }
$size = [math]::Round((Get-Item $installer).Length / 1MB, 1)
Write-Host "Release ready: $installer ($size MB)" -ForegroundColor Green
