"""Build script for packaging Customer Billing System into a standalone Windows .exe.

Run:
    python build_installer.py

Requires PyInstaller:
    python -m pip install pyinstaller
"""

import os
import sys
import subprocess


def build_exe():
    print("=" * 60)
    print("Building Customer Billing System Standalone Windows App (.exe)")
    print("=" * 60)

    # 1. Ensure pyinstaller is installed
    try:
        import PyInstaller
        print("[1/3] PyInstaller is installed.")
    except ImportError:
        print("[1/3] Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Build command arguments
    # Bundling customtkinter and assets
    here = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(here, "main.py")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=POS_Billing_System",
        "--noconsole",
        "--onedir",
        "--clean",
        "--collect-all=customtkinter",
        "--collect-all=fpdf",
        "--collect-all=qrcode",
        main_script,
    ]

    print("[2/3] Running PyInstaller build...")
    print(f"Command: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=here)

    print("\n" + "=" * 60)
    print("[3/3] BUILD COMPLETE!")
    print(f"Your executable is ready in: {os.path.join(here, 'dist', 'POS_Billing_System')}")
    print("You can run 'POS_Billing_System.exe' directly without Python!")
    print("=" * 60)


if __name__ == "__main__":
    build_exe()
