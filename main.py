"""
main.py - Entry point for Meshtastic Python Client.

Usage:
    python main.py

Requirements:
    pip install -r requirements.txt
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("meshtastic_client")


def check_dependencies():
    """Check that required packages are installed."""
    missing = []

    try:
        import customtkinter
    except ImportError:
        missing.append("customtkinter")

    try:
        import meshtastic
    except ImportError:
        missing.append("meshtastic")

    try:
        import serial
    except ImportError:
        missing.append("pyserial")

    if missing:
        print("\n" + "="*60)
        print("Missing required packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\nActive Python: {sys.executable}")
        print("\nInstall with THIS Python interpreter:")
        print(f"  {sys.executable} -m pip install -r requirements.txt")
        print("\n(Using 'pip install' alone may install to a different Python.)")
        print("="*60 + "\n")
        return False

    # Optional packages
    try:
        import tkintermapview
    except ImportError:
        print("[INFO] tkintermapview not installed - Map view will use fallback table.")
        print("[INFO] Install with: pip install tkintermapview")

    return True


def main():
    if not check_dependencies():
        sys.exit(1)

    try:
        from meshtastic_app import MeshtasticApp
        app = MeshtasticApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Application closed by user.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
