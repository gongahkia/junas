# PyInstaller spec for the menu-bar stdio sidecar.
#
# Build:
#     uv sync --extra packaging
#     uv run pyinstaller packaging/aki-sidecar.spec
#
# Output: dist/aki-sidecar/aki-sidecar

# ruff: noqa
# flake8: noqa
from pathlib import Path

block_cipher = None
ROOT = Path(globals().get("SPECPATH", Path.cwd() / "packaging")).parent
SRC_DIR = ROOT / "src"
ENTRYPOINT = ROOT / "packaging" / "aki_sidecar_entrypoint.py"

hidden_imports = [
    "junas.cli",
    "junas.desktop.sidecar_protocol",
]

excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "transformers",
    "sentence_transformers",
    "accelerate",
    "redis",
    "xgboost",
    "sklearn",
    "pandas",
    "tensorflow",
    "spacy",
    "presidio_analyzer",
    "presidio_anonymizer",
    "fastapi",
    "uvicorn",
]

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="aki-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="aki-sidecar",
)
