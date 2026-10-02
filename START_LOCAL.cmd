@echo off
setlocal
set ROOT=%~dp0

if not exist "%ROOT%app\backend\app\main.py" (
  echo [ERROR] Backend files not found under app\backend.
  pause
  exit /b 1
)
if not exist "%ROOT%app\frontend\package.json" (
  echo [ERROR] Frontend package.json not found under app\frontend.
  pause
  exit /b 1
)
if not exist "%ROOT%app\backend\.env" (
  echo [ERROR] app\backend\.env is missing.
  echo Copy your existing local .env into app\backend before starting.
  pause
  exit /b 1
)

start "Crypto Bot Backend" cmd /k "cd /d \"%ROOT%app\backend\" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "Crypto Bot Frontend" cmd /k "cd /d \"%ROOT%app\frontend\" && if not exist node_modules (npm ci) && npm run dev"

echo.
echo Backend and frontend launch windows opened.
echo Open the URL printed by Vite in the frontend window.
echo.
pause
