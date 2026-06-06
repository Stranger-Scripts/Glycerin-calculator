# build/

Files in this directory let you compile the calculator into a standalone
binary using [PyInstaller](https://pyinstaller.org/). The application source
in `src/` is **not** modified by anything here.

## Files

| File | Purpose |
|---|---|
| `launcher.py` | Entry point used by the bundle. Imports `glycerin_calculator.main:app`, opens a browser, runs uvicorn with reload disabled. |
| `glycerin_calculator.spec` | PyInstaller config: paths, bundled templates/static, hidden imports. |
| `build-linux.sh` | One-shot Linux build script (run from project root). |
| `build-windows.ps1` | One-shot Windows PowerShell build script (run from project root). |

## Building

### Linux (Arch / any modern x86-64 distro)

```bash
chmod +x build/build-linux.sh
./build/build-linux.sh
```

Output ends up in `dist/glycerin-calculator/`.
Users run `./glycerin-calculator` and a browser tab opens at
`http://127.0.0.1:8000`.

### Windows (x86-64)

In PowerShell, from the project root:

```powershell
.\build\build-windows.ps1
```

Output: `dist\glycerin-calculator\glycerin-calculator.exe`.

Note: the unsigned `.exe` will trigger SmartScreen on first run. Users can
click "More info -> Run anyway."

## Cross-compilation

PyInstaller does **not** cross-compile. You must run the Linux build on
Linux and the Windows build on Windows.
