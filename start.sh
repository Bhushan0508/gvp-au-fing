#!/bin/bash

# Check if torchvision is installed, if not install it
python -c "import torchvision" 2>/dev/null || pip install torchvision==0.15.2

# Upgrade marshmallow to fix version_info issue
pip install --upgrade marshmallow

# Start the Flask app
python -u backend/app.py
