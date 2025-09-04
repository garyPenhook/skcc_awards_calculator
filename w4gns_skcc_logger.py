#!/usr/bin/env python3
"""W4GNS SKCC Logger - QSO Logging Application."""

import os
import sys
import traceback
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_tcl_tk_paths() -> None:  # noqa: PLR0912
    """Ensure Tcl/Tk can be located on Windows.

    When multiple Python installations exist, tkinter may look for Tcl/Tk in the
    wrong base path (e.g., under AppData). We point it at the base interpreter's
    tcl directories if available, and ensure DLLs are on PATH, before importing
    any tkinter modules.
    """
    try:

        def _read_home_from_venv() -> Path | None:
            # Try pyvenv.cfg beside the current interpreter or prefix
            candidates = [Path(sys.prefix), Path(sys.executable).parent.parent, Path.cwd()]
            for root in candidates:
                cfg = root / "pyvenv.cfg"
                if cfg.is_file():
                    with cfg.open("r", encoding="utf-8") as f:
                        for line in f:
                            if line.lower().startswith("home"):
                                _, val = line.split("=", 1)
                                home = Path(val.strip())
                                if home.exists():
                                    return home
            return None

        # Find a Python base that actually has tcl/tk folders
        candidates = []
        env_home = os.environ.get("PYTHONHOME")
        if env_home:
            candidates.append(Path(env_home))
        venv_home = _read_home_from_venv()
        if venv_home:
            candidates.append(venv_home)
        candidates.extend(
            [
                Path(getattr(sys, "base_prefix", sys.prefix)),
                Path(sys.prefix),
                Path("C:/Python313"),
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python313",
            ]
        )

        chosen_base = None
        chosen_tcl = None
        chosen_tk = None
        for base in candidates:
            if not base or not base.exists():
                continue
            for ver in ("8.6", "8.7"):
                tcl_dir = base / "tcl" / f"tcl{ver}"
                tk_dir = base / "tcl" / f"tk{ver}"
                if tcl_dir.is_dir() and tk_dir.is_dir():
                    chosen_base, chosen_tcl, chosen_tk = base, tcl_dir, tk_dir
                    break
            if chosen_base:
                break

        if chosen_base and chosen_tcl and chosen_tk:
            # Point Tcl/Tk explicitly at the discovered base
            os.environ["TCL_LIBRARY"] = str(chosen_tcl)
            os.environ["TK_LIBRARY"] = str(chosen_tk)

            dlls_dir = Path(chosen_base) / "DLLs"
            if dlls_dir.is_dir():
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(str(dlls_dir))  # type: ignore[attr-defined]
                except Exception:
                    pass
                path_entries = os.environ.get("PATH", "").split(os.pathsep)
                dlls_str = str(dlls_dir)
                if dlls_str not in path_entries:
                    os.environ["PATH"] = dlls_str + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        # Don't fail startup if we couldn't adjust paths; the normal import may still work.
        pass


def main():
    """Main entry point with proper exception handling."""
    try:
        # Make sure Tcl/Tk can be resolved before importing tkinter in the GUI.
        if os.name == "nt":
            _ensure_tcl_tk_paths()
        # Import and run the clean QSO form
        from gui.tk_qso_form_clean import main as gui_main

        gui_main()
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure all required packages are installed:")
        print("  pip install httpx beautifulsoup4")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error starting SKCC Logger: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("\nPlease report this error with the traceback above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
