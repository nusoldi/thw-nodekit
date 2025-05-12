#!/bin/bash

# Exit on error
set -e

echo "Installing THW-NodeKit..."

# Define installation directory (current directory where script is run)
INSTALL_DIR=$(pwd)

# Check for required dependencies
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.6 or higher."
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 not found. Please install pip for Python 3."
    exit 1
fi

if [ ! -f "$INSTALL_DIR/requirements.txt" ]; then
    echo "ERROR: requirements.txt not found."
    exit 1
fi

# Create lib directory for dependencies
mkdir -p $INSTALL_DIR/lib

# Install dependencies in the lib directory
echo "Installing dependencies..."
pip3 install --target=$INSTALL_DIR/lib -r requirements.txt

# Create a symlink in the XDG standard location
mkdir -p ~/.local/bin
ln -sf $INSTALL_DIR/bin/thw-nodekit ~/.local/bin/thw-nodekit

echo "Installation complete!"
echo ""
echo "To use THW-NodeKit, you have two options:"
echo ""
echo "1. Run using the full path:"
echo "$INSTALL_DIR/bin/thw-nodekit"
echo ""
echo "2. Add ~/.local/bin to your PATH by adding this line to your ~/.bashrc file:"
echo "export PATH=~/.local/bin:\$PATH"
echo ""
echo "Then run 'source ~/.bashrc' and you can use the command 'thw-nodekit' directly."
echo ""
echo "To verify the installation, try running:"
echo "$INSTALL_DIR/bin/thw-nodekit --help"