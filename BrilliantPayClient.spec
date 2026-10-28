# PyInstaller build definition for the Windows desktop client.
from PyInstaller.utils.hooks import collect_all


webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")

a = Analysis(
    ["desktop_client.py"],
    pathex=[],
    binaries=webview_binaries,
    datas=webview_datas,
    hiddenimports=webview_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BrilliantPay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="BrilliantPay",
)
