@echo off
REM ============================================================
REM SpaceMouseDrawingMode - Deployment Script
REM Run from the SpaceMouseDrawingMode folder to install the
REM add-in into Fusion 360 for the current user.
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   SpaceMouseDrawingMode Deployment
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "SOURCE_PATH=%SCRIPT_DIR%SpaceMouseDrawingMode.bundle\Contents"
set "DEPLOY_PATH=%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\SpaceMouseDrawingMode"

if not exist "%SOURCE_PATH%" (
    echo ERROR: Source bundle not found!
    echo Expected: %SOURCE_PATH%
    echo.
    echo Make sure you run this script from the SpaceMouseDrawingMode folder.
    goto :error
)

echo Source:      %SOURCE_PATH%
echo Destination: %DEPLOY_PATH%
echo.

REM Check if Fusion 360 is running
tasklist /FI "IMAGENAME eq Fusion360.exe" 2>NUL | find /I /N "Fusion360.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo WARNING: Fusion 360 is currently running.
    echo Close Fusion 360 first, or reload the add-in manually after install.
    echo.
    set /p "CONTINUE=Continue anyway? (Y/N): "
    if /i not "!CONTINUE!"=="Y" goto :cancelled
    echo.
)

REM Remove old install
if exist "%DEPLOY_PATH%" (
    echo [1/2] Removing old version...
    rmdir /S /Q "%DEPLOY_PATH%"
    if exist "%DEPLOY_PATH%" (
        echo ERROR: Could not remove old version. Is Fusion 360 running?
        goto :error
    )
) else (
    echo [1/2] No existing install found ^(fresh install^).
)

REM Copy new files
echo [2/2] Installing...
xcopy "%SOURCE_PATH%" "%DEPLOY_PATH%" /E /I /H /Y >NUL
if errorlevel 1 (
    echo ERROR: Failed to copy files.
    goto :error
)

echo.
echo ============================================================
echo   INSTALLATION COMPLETE!
echo ============================================================
echo.
echo Installed to: %DEPLOY_PATH%
echo.
echo Next steps:
echo   1. Open Fusion 360 (or restart if already running)
echo   2. Go to Utilities ^> Add-Ins (Shift+S)
echo   3. Under "My Add-Ins" find SpaceMouseDrawingMode and click Run
echo   4. A "SpaceMouse" panel will appear in the Design workspace toolbar
echo.
goto :end

:cancelled
echo.
echo Deployment cancelled.
goto :end

:error
echo.
echo ============================================================
echo   DEPLOYMENT FAILED
echo ============================================================
echo.

:end
echo Press any key to close...
pause >NUL
