@echo off
setlocal
cd /d "%~dp0"
title Elshamii - Startup

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    set "PY=python"
)

if not exist "backend\.venv\Scripts\python.exe" (
    echo [1/6] Creating backend environment...
    %PY% -m venv backend\.venv
    if errorlevel 1 goto :error
)
echo [2/6] Installing backend requirements...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto :error

if not exist "backend\.env" (
    echo [3/6] Creating local backend configuration...
    copy "backend\.env.example" "backend\.env" >nul
)

echo [4/6] Applying database migrations...
backend\.venv\Scripts\python.exe backend\manage.py migrate
if errorlevel 1 goto :error

echo [5/6] Starting local API server...
start "Elshamii Local Server" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000"
echo Waiting for the local API...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try{$c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',8000); $c.Close(); $ok=$true; break}catch{Start-Sleep -Seconds 1} }; if(-not $ok){exit 1}"
if errorlevel 1 goto :error

if not exist "desktop\.venv\Scripts\python.exe" (
    %PY% -m venv desktop\.venv
    if errorlevel 1 goto :error
)
echo [6/6] Installing desktop requirements and launching Elshamii...
desktop\.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
if errorlevel 1 goto :error
cd desktop
"%~dp0desktop\.venv\Scripts\python.exe" main.py
exit /b 0

:error
echo.
echo Elshamii could not start. Check the error above.
pause
exit /b 1
