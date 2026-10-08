# PyInstaller spec of the packaged server (phase 7, spec 5.2): onedir, console exe that the
# launcher starts without a window. Built by scripts\package.ps1 from backend\:
#   uv run pyinstaller --noconfirm --distpath <dist> --workpath <work> pokker-server.spec
# Output: <dist>\pokker-server\pokker-server.exe + _internal\ (alembic.ini and alembic\ at the
# _internal root, where app.db.session.BACKEND_ROOT = sys._MEIPASS looks for them).
import os

from PyInstaller.utils.hooks import collect_submodules

HERE = os.path.abspath(SPECPATH)  # noqa: F821 (injected by PyInstaller)


def _alembic_datas():
    """alembic\\ tree (env.py, script.py.mako, versions\\*.py) without __pycache__."""
    out = []
    root = os.path.join(HERE, "alembic")
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = os.path.relpath(folder, HERE)
        out += [(os.path.join(folder, f), rel) for f in files]
    return out


hiddenimports = [
    # uvicorn picks these by name at runtime.
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    # alembic\env.py and versions\*.py are data files: their imports are invisible to analysis.
    "alembic.op",
    "alembic.context",
    "alembic.runtime.migration",
    "alembic.ddl.sqlite",
    "logging.config",
    "pokercore",
    *collect_submodules("app"),
]

a = Analysis(
    [os.path.join(HERE, "app", "server_main.py")],
    pathex=[HERE],
    datas=[(os.path.join(HERE, "alembic.ini"), "."), *_alembic_datas()],
    hiddenimports=hiddenimports,
    hookspath=[h for h in [os.path.join(HERE, "pyinstaller_hooks")] if os.path.isdir(h)],
    excludes=["tkinter", "pytest", "IPython", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pokker-server",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="pokker-server", upx=False)
