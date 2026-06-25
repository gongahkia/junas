# PyInstaller spec for the junas-local desktop SKU.
#
# Build:
#     uv sync --extra local --extra packaging
#     python -m spacy download en_core_web_sm
#     uv run pyinstaller packaging/junas-local.spec
#
# Output: dist/junas-local (single-folder bundle; flip onefile=True for single binary).
#
# Intentionally excludes server-side ML stack so the binary stays under ~120MB compressed.
# pypdf is included optionally; if absent at runtime the engine still handles inline text
# and DOCX.

# ruff: noqa
# flake8: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_all  # type: ignore[import-not-found]

block_cipher = None
ROOT = Path(globals().get("SPECPATH", Path.cwd() / "packaging")).parent
SRC_DIR = ROOT / "src"
ENTRYPOINT = ROOT / "packaging" / "junas_local_entrypoint.py"

# spaCy ships its model as an installed Python package after `spacy download`. collect_all
# bundles the data files alongside the metadata.
spacy_datas, spacy_binaries, spacy_hiddenimports = collect_all("en_core_web_sm")
presidio_datas, presidio_binaries, presidio_hiddenimports = collect_all("presidio_analyzer")
presidio_anon_datas, presidio_anon_binaries, presidio_anon_hiddenimports = collect_all("presidio_anonymizer")

hidden_imports = (
    spacy_hiddenimports
    + presidio_hiddenimports
    + presidio_anon_hiddenimports
    + [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "junas.backend.main",
        "junas.review.engine",
        "junas.review.decisions",
        "junas.review.journal",
        "junas.review.defined_terms",
        "junas.review.entity_linker",
        "junas.anonymize.engine",
        "junas.workflow.privacy_guard",
    ]
)

# heavy server-only modules must never be pulled in by stray transitive imports.
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
    "junas.workflow.layer7_public_evidence",
    "junas.workflow.layer8_llm_adjudicator",
]

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(SRC_DIR)],
    binaries=spacy_binaries + presidio_binaries + presidio_anon_binaries,
    datas=spacy_datas + presidio_datas + presidio_anon_datas,
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
    name="junas-local",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="junas-local",
)
