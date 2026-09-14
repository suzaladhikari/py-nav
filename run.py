#!/usr/bin/env python3
"""Primary launcher for Py-Nav.

Strategy
--------
1. Verify Python >= 3.10 and that the ``venv`` stdlib module is present.
2. Check if required packages (pygame, pygame_gui, pyyaml) are importable
   in the current environment. If so, run ``main/main.py`` directly.
3. If deps are missing in the global env, fall back to venv bootstrap:
   - If venv exists and deps verify → launch via venv Python
   - If venv exists but deps are broken → remove and recreate
   - If venv doesn't exist → create via setup.py
4. Repeat at most ``MAX_RELAUNCH`` times to avoid infinite loops.

On success (main.py exits 0) or a fatal error, the process terminates.

Directory layout
----------------
``main/``     – contains setup.py, main.py.
``venv/``     – sibling of main/, created by setup.py.
"""

import os
import platform
import shutil
import subprocess
import sys
import venv  # noqa: F401  – used for the availability check

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PYTHON = (3, 10)
VENV_DIR = "venv"
MAX_RELAUNCH = 3
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Required third-party packages — kept in sync with setup.py and main.py.
_REQUIRED_IMPORTS = ("pygame", "pygame_gui", "yaml")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def python_version_ok():
    """Return True when running on Python >= 3.10."""
    return sys.version_info >= REQUIRED_PYTHON


def _venv_python():
    """Return the path to the Python executable inside the venv.

    run.py lives at repo root, so SCRIPT_DIR is the repo root.
    The venv lives at repo_root/venv, which is where setup.py creates it.
    """
    if platform.system() == "Windows":
        return os.path.join(SCRIPT_DIR, VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(SCRIPT_DIR, VENV_DIR, "bin", "python")


def _venv_dir():
    """Return the path to the venv directory."""
    return os.path.join(SCRIPT_DIR, VENV_DIR)


def _verify_global_deps():
    """Check if required packages are importable in the current Python.

    Returns ``True`` when all packages import without error.
    """
    code = "\n".join(f"import {mod}" for mod in _REQUIRED_IMPORTS)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def verify_deps():
    """Try importing all required packages inside the venv.

    Returns ``True`` if all imports succeed, ``False`` otherwise.
    """
    py_exe = _venv_python()
    if not os.path.isfile(py_exe):
        return False

    code = "\n".join(f"import {mod}" for mod in _REQUIRED_IMPORTS)
    result = subprocess.run(
        [py_exe, "-c", code],
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _direct_launch():
    """Run ``main.py`` in the current Python process.

    Returns ``True`` on success (exit 0), ``False`` on failure.
    """
    main_script = os.path.join(SCRIPT_DIR, "main", "main.py")
    result = subprocess.run([sys.executable, main_script], cwd=SCRIPT_DIR)
    return result.returncode == 0


def _launch_venv():
    """Launch Py-Nav via the venv Python. Exits with the subprocess's return code."""
    venv_py = _venv_python()
    if not os.path.isfile(venv_py):
        return False

    print()
    print(f"Launching Py-Nav via venv Python: {venv_py}")
    print()
    main_script = os.path.join(SCRIPT_DIR, "main", "main.py")
    result = subprocess.run([venv_py, main_script], cwd=SCRIPT_DIR)
    sys.exit(result.returncode)


def _remove_venv():
    """Remove the venv directory if it exists."""
    venv_path = _venv_dir()
    if os.path.exists(venv_path):
        print(f"Removing existing virtual environment: {venv_path}")
        shutil.rmtree(venv_path, ignore_errors=True)


def _run_setup():
    """Execute setup.py --force to create venv and install deps.

    Returns True if setup succeeded, False otherwise.
    """
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "main", "setup.py"), "--force"],
        cwd=SCRIPT_DIR,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Relaunch counter
# ---------------------------------------------------------------------------

_relaunch_count = 0


def main():
    global _relaunch_count

    if not python_version_ok():
        print(
            f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} or newer is required."
            f"  Found {sys.version_info.major}.{sys.version_info.minor}."
        )
        sys.exit(1)

    try:
        import venv as _  # noqa: F401
    except ImportError:
        print("ERROR: the standard-library 'venv' module is not available.")
        sys.exit(1)

    print("=" * 60)
    print("  Py-Nav Launcher")
    print("=" * 60)
    print()

    # Step 1: Check if deps are in global Python, then launch directly.
    if _verify_global_deps():
        print("Dependencies found in current Python — launching directly.")
        if _direct_launch():
            print()
            print("Py-Nav exited cleanly.")
            sys.exit(0)
    else:
        print("Dependencies not found in current Python. Will try virtual environment...")

    # Step 2: Try venv bootstrap.
    venv_exists = os.path.isdir(_venv_dir())

    if venv_exists and verify_deps():
        # Venv exists and deps are good — launch it.
        _launch_venv()
    else:
        # Venv is missing or broken — clean up and recreate.
        if venv_exists:
            print()
            print("Dependencies not verified in existing venv.")
            print("Removing and recreating...")
        else:
            print()
            print("No virtual environment found.")
            print("Creating one...")

        _remove_venv()

        for attempt in range(1, MAX_RELAUNCH + 1):
            _relaunch_count = attempt
            print()
            print(f"Running setup.py (attempt {_relaunch_count}/{MAX_RELAUNCH})...")
            if _run_setup():
                print()
                _launch_venv()
            print()
            print(f"ERROR: setup.py failed (attempt {_relaunch_count}/{MAX_RELAUNCH}).")
            if _relaunch_count < MAX_RELAUNCH:
                print("Will retry...")
        print()
        print(f"ERROR: setup failed after {MAX_RELAUNCH} attempts.")
        print("Try running 'python setup.py --force' manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
