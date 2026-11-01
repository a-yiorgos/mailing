#!/bin/bash
# Setup script for mailing list manager virtual environment

set -e

echo "Creating virtual environment..."
python3 -m venv venv

# Activate and install (though no external deps needed)
echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing any requirements..."
pip install -r requirements.txt

echo "Virtual environment setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the mailing list manager:"
echo "  python mailing.py"
