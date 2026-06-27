@echo off
setlocal

echo [1/3] Installing build dependencies...
pip install pyinstaller pywebview
if %errorlevel% neq 0 ( echo FAILED: pip install && exit /b 1 )
pip install -r requirements.txt
if %errorlevel% neq 0 ( echo FAILED: pip install requirements && exit /b 1 )

echo.
echo [2/3] Ensuring Playwright Chromium is present...
playwright install chromium
if %errorlevel% neq 0 ( echo FAILED: playwright install && exit /b 1 )

echo.
echo [3/3] Building shoob.exe...
pyinstaller shoob.spec --clean --distpath .
if %errorlevel% neq 0 ( echo FAILED: pyinstaller && exit /b 1 )

echo.
if exist shoob.exe (
    echo BUILD SUCCESSFUL -^> shoob.exe
) else (
    echo BUILD FAILED: shoob.exe not found
    exit /b 1
)
