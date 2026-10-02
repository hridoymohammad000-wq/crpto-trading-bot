@echo off
setlocal
set ROOT=%~dp0

echo === Backend tests ===
cd /d "%ROOT%app\backend"
python -m pytest -q
if errorlevel 1 goto :fail

echo.
echo === Frontend install check ===
cd /d "%ROOT%app\frontend"
if not exist node_modules npm ci
if errorlevel 1 goto :fail

echo.
echo === Frontend tests ===
call npm test
if errorlevel 1 goto :fail

echo.
echo === Frontend production build ===
call npm run build
if errorlevel 1 goto :fail

echo.
echo ========================================
echo ALL LOCAL CHECKS PASSED
 echo ========================================
pause
exit /b 0

:fail
echo.
echo ========================================
echo CHECK FAILED - see the error above
 echo ========================================
pause
exit /b 1
