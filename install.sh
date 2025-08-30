#!/bin/bash

echo "SKCC Awards Calculator - Installation (Linux/Mac)"
echo "================================================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or higher:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-tk"
    echo "  macOS: brew install python-tk"
    echo "  Or download from: https://www.python.org/downloads/"
    exit 1
fi

echo "Python found:"
python3 --version
echo

echo "Installing required packages..."
echo "- httpx (for downloading SKCC roster)"
echo "- beautifulsoup4 (for parsing web pages)"
echo

pip3 install httpx==0.27.0 beautifulsoup4==4.12.3

if [ $? -eq 0 ]; then
    echo
    echo "✅ Installation complete!"
    echo
    echo "You can now run the SKCC Awards Calculator:"
    echo
    echo "1. GUI Mode: python3 scripts/gui.py"
    echo "2. Command Line: python3 scripts/awards_check.py --help"
    echo "3. Check dependencies: python3 check_dependencies.py"
    echo
else
    echo "ERROR: Failed to install packages"
    echo "Try: pip3 install --user httpx beautifulsoup4"
    exit 1
fi
