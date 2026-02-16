#!/bin/bash
# Set up a python virtual environment and install dependencies

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Environment setup complete. Activate with 'source venv/bin/activate'"
