import os
from pathlib import Path

block_cipher = None

# Find Playwright browsers to bundle (chromium and chromium_headless_shell).
# At runtime, main.py sets PLAYWRIGHT_BROWSERS_PATH = _MEIPASS/browsers so
# Playwright resolves browsers from the bundle instead of the host system.
_ms_playwright = Path(
    os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '')
    or Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright'
)
_browser_datas = [
    (str(entry), f'browsers/{entry.name}')
    for entry in _ms_playwright.iterdir()
    if entry.is_dir() and entry.name.startswith('chromium')
] if _ms_playwright.exists() else []

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('scraper.py', '.'),
        *_browser_datas,
    ],
    hiddenimports=['flask', 'webview', 'playwright'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='shoob',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    icon='logo.ico',
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
