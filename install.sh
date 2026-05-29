#!/usr/bin/env bash
set -e

echo "============================================"
echo " Meshtastic Python Client - Linux Setup"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found."
    echo "Install with: sudo apt install python3 python3-pip   (Ubuntu/Debian)"
    echo "          or: sudo dnf install python3 python3-pip   (Fedora/RHEL)"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PYTHON_VERSION"

# Check tkinter
python3 -c "import tkinter" 2>/dev/null || {
    echo ""
    echo "WARNING: tkinter not found. Install it with:"
    echo "  Ubuntu/Debian: sudo apt install python3-tk"
    echo "  Fedora:        sudo dnf install python3-tkinter"
    echo "  Arch:          sudo pacman -S tk"
    echo ""
    echo "Press Enter to continue anyway, or Ctrl+C to exit and install tkinter first."
    read -r
}

# Install pip packages
echo "Using Python: $(python3 -c 'import sys; print(sys.executable)')"
echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Add user to dialout group for serial access (Linux)
if id -nG "$USER" | grep -qw "dialout"; then
    echo "User already in dialout group (serial access OK)"
else
    echo ""
    echo "Adding $USER to 'dialout' group for serial port access..."
    sudo usermod -a -G dialout "$USER"
    echo "NOTE: You may need to log out and back in for serial port access to work."
fi

echo ""
echo "============================================"
echo " Installation complete!"
echo " Run the app with:  python3 main.py"
echo "     or:            ./run.sh"
echo "============================================"
