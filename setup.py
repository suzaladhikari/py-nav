#!/usr/bin/env python3
"""Standalone setup utility — creates a virtual environment and installs
required third-party packages (pygame, pygame_gui, pyyaml).

Run this file once to prepare the environment.  After that, use run.py
to launch the application.

Usage:
    python setup.py              # create venv and install deps
    python setup.py --verify     # check if deps are importable (exit 0/1)
    python setup.py --force      # remove existing venv first
"""

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import venv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PYTHON = (3, 10)
VENV_DIR = "venv"

# Hard-coded dependencies — no requirements.txt or pyproject.toml yet.
DEPS = ("pygame", "pygame_gui", "pyyaml")

SPINNER_CHARS = ("|", "/", "—", "\\")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def spinner(stop_event, interval=0.15):
    """Print a spinning animation to stderr until stop_event is set."""
    while not stop_event.is_set():
        for ch in SPINNER_CHARS:
            if stop_event.is_set():
                break
            sys.stderr.write(f"\rInstalling {ch} ")
            sys.stderr.flush()
            stop_event.wait(interval)
    sys.stderr.write("\rInstalling    \r")
    sys.stderr.flush()


def python_version_ok():
    """Return True when running on Python >= 3.10."""
    return sys.version_info >= REQUIRED_PYTHON


def check_ve_modules():
    """Return True when the venv standard-library module is available."""
    try:
        import venv  # noqa: F401 – side-effect of the import
        return True
    except ImportError:
        return False


def ensure_ve_modules():
    """Exit the process if ``venv`` is not importable."""
    if not check_ve_modules():
        print("ERROR: the standard-library 'venv' module is not available.")
        print("Install the python3-venv package (Debian/Ubuntu) or")
        print("python3-venv (Fedora) or equivalent for your distro.")
        sys.exit(1)


def run_subprocess(cmd, *, check=True):
    """Run a subprocess, printing the command first for transparency."""
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)
    return result


def verify_deps():
    """Try importing all required packages inside the venv.

    Returns ``True`` if all imports succeed, ``False`` otherwise.
    """
    if platform.system() == "Windows":
        py_exe = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        py_exe = os.path.join(VENV_DIR, "bin", "python")

    if not os.path.isfile(py_exe):
        return False

    code = "\n".join(
        (
            "import pygame",
            "import pygame_gui",
            "import yaml",
        )
    )
    result = subprocess.run(
        [py_exe, "-c", code],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def main():
    args = sys.argv[1:]

    # --verify: just check if deps import, don't install anything
    if "--verify" in args:
        if not os.path.isdir(VENV_DIR):
            print("No virtual environment found. Run 'python setup.py' first.")
            sys.exit(1)
        if verify_deps():
            print("All dependencies are installed and importable.")
            sys.exit(0)
        else:
            print("ERROR: some dependencies are missing or broken.")
            sys.exit(1)

    force = "--force" in args

    if not python_version_ok():
        print(
            f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} or newer is required."
            f"  Found {sys.version_info.major}.{sys.version_info.minor}."
        )
        sys.exit(1)

    ensure_ve_modules()

    venv_path = VENV_DIR

    if os.path.exists(venv_path):
        if not force:
            print(
                f"ERROR: Virtual environment directory '{venv_path}' already exists."
                "  Run with --force to delete and recreate it."
            )
            sys.exit(1)
        print(f"Removing existing virtual environment: {venv_path}")
        shutil.rmtree(venv_path, ignore_errors=True)

    print("Creating virtual environment in", venv_path)
    venv.create(venv_path, with_pip=True)

    # Determine the pip executable inside the venv.
    if platform.system() == "Windows":
        pip_exe = os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        pip_exe = os.path.join(venv_path, "bin", "pip")

    print("Installing dependencies...\n")
    stop_spinner = threading.Event()
    spinner_thread = threading.Thread(target=spinner, args=(stop_spinner,), daemon=True)
    spinner_thread.start()

    for dep in DEPS:
        print(f"  Installing {dep}...")
        run_subprocess([pip_exe, "install", "-q", dep])

    stop_spinner.set()
    spinner_thread.join()
    print()

    # Verify all deps are importable
    print("Verifying installation...")
    if not verify_deps():
        print("ERROR: some dependencies failed to install or import correctly.")
        print("Try running 'python setup.py --force' to recreate the environment.")
        sys.exit(1)

    print()
    print("Done!  Run 'python run.py' to launch Py-Nav.")


if __name__ == "__main__":
    main()
