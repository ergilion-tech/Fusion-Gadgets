# ============================================================
# MENSEKI_Addin - Self-Extracting Installer Builder
# Creates a SINGLE executable file that extracts and installs
# ============================================================

param(
    [string]$Version = "0.1.2"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MENSEKI_Addin Self-Extracting Installer Builder" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$addinPath = Join-Path $scriptDir "MENSEKI_Addin"
$outputDir = Join-Path $scriptDir "dist"

if (-not (Test-Path $addinPath)) {
    Write-Host "ERROR: MENSEKI_Addin folder not found!" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

Write-Host "Version: $Version"
Write-Host ""

# Step 1: Prepare add-in
Write-Host "[1/4] Preparing add-in..." -ForegroundColor White
$stagingDir = Join-Path $env:TEMP "MENSEKI_SFX_$([guid]::NewGuid().ToString('N').Substring(0,8))"
$addinStage = Join-Path $stagingDir "MENSEKI_Addin"
Copy-Item $addinPath $addinStage -Recurse
Write-Host "      Done." -ForegroundColor Green

# Step 2: Create ZIP
Write-Host "[2/4] Creating compressed archive..." -ForegroundColor White
$zipPath = Join-Path $env:TEMP "MENSEKI_bundle.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $addinStage -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "      Done." -ForegroundColor Green

# Step 3: Convert to Base64
Write-Host "[3/4] Encoding archive..." -ForegroundColor White
$zipBytes = [System.IO.File]::ReadAllBytes($zipPath)
$base64 = [Convert]::ToBase64String($zipBytes)
$zipSizeKB = [math]::Round($zipBytes.Length / 1KB, 1)
Write-Host "      Archive size: $zipSizeKB KB" -ForegroundColor Gray
Write-Host "      Done." -ForegroundColor Green

# Step 4: Create self-extracting CMD/PowerShell hybrid
Write-Host "[4/4] Building self-extracting installer..." -ForegroundColor White

$batchPart = @'
<# : batch script
@echo off
setlocal
title MENSEKI Add-In Installer
echo.
echo ============================================================
echo   MENSEKI Add-In - Self-Extracting Installer
echo   Surface Area / Length / Volume Calculator for Fusion 360
echo ============================================================
echo.
echo Extracting and installing...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& {[ScriptBlock]::Create((Get-Content -Raw '%~f0')).Invoke()}"
pause
goto :EOF
#>

'@

$psPart1 = @'
$ErrorActionPreference = "Stop"

Write-Host ""

$base64Data = @"
'@

$psPart2 = @'
"@

try {
    $deployPath = "$env:APPDATA\Autodesk\Autodesk Fusion 360\API\AddIns\MENSEKI_Addin"
    $extractDir = "$env:TEMP\MENSEKI_Extract_$([guid]::NewGuid().ToString('N').Substring(0,8))"

    $fusion = Get-Process -Name "Fusion360" -ErrorAction SilentlyContinue
    if ($fusion) {
        Write-Host "WARNING: Fusion 360 is running. Restart it after installation." -ForegroundColor Yellow
        Write-Host ""
    }

    # Ensure target parent directory exists
    $addInsDir = "$env:APPDATA\Autodesk\Autodesk Fusion 360\API\AddIns"
    if (-not (Test-Path $addInsDir)) {
        New-Item -ItemType Directory -Path $addInsDir -Force | Out-Null
    }

    if (Test-Path $deployPath) {
        Write-Host "[1/3] Removing old version..." -ForegroundColor White
        Remove-Item $deployPath -Recurse -Force
        Start-Sleep -Milliseconds 500
    } else {
        Write-Host "[1/3] Fresh installation." -ForegroundColor Gray
    }

    Write-Host "[2/3] Extracting and installing..." -ForegroundColor White
    New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

    $zipPath = Join-Path $extractDir "bundle.zip"
    $zipBytes = [Convert]::FromBase64String($base64Data)
    [System.IO.File]::WriteAllBytes($zipPath, $zipBytes)

    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    $addinSource = Get-ChildItem -Path $extractDir -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "MENSEKI_Addin.manifest") } |
        Select-Object -First 1

    if ($addinSource) {
        Move-Item $addinSource.FullName $deployPath -Force
    } else {
        throw "MENSEKI_Addin not found in archive"
    }

    Write-Host "[3/3] Cleaning up..." -ForegroundColor White
    Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  INSTALLATION SUCCESSFUL!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installed to: $deployPath"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Open Fusion 360 (or restart if running)"
    Write-Host "  2. Go to Utilities > Add-Ins (or press Shift+S)"
    Write-Host "  3. Find 'MENSEKI_Addin' and click Run"
    Write-Host "  4. Optionally check 'Run on Startup'"
    Write-Host ""
    Write-Host "Commands will appear in the Inspect panel:"
    Write-Host "  - Length  (total length of selected edges)"
    Write-Host "  - Area    (total area of selected faces)"
    Write-Host "  - Volume  (total volume of selected bodies)"
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  INSTALLATION FAILED" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""

    if (Test-Path $extractDir) {
        Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
'@

# Combine all parts
$fullScript = $batchPart + $psPart1 + "`n" + $base64 + "`n" + $psPart2

# Save as .cmd file
$cmdPath = Join-Path $outputDir "MENSEKI_Addin_v${Version}_Setup.cmd"
[System.IO.File]::WriteAllText($cmdPath, $fullScript, [System.Text.Encoding]::ASCII)

Write-Host "      Done." -ForegroundColor Green

# Cleanup
Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

# Get size
$fileSize = (Get-Item $cmdPath).Length
$fileSizeKB = [math]::Round($fileSize / 1KB, 1)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Created: $cmdPath" -ForegroundColor Cyan
Write-Host "Size:    $fileSizeKB KB" -ForegroundColor White
Write-Host ""
Write-Host "This is a SINGLE FILE self-extracting installer!" -ForegroundColor Yellow
Write-Host "Users just double-click it to install the add-in."
Write-Host ""
