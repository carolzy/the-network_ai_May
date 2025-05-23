#!/bin/bash

# Change to the directory where this script is located
cd "$(dirname "$0")"

# Activate the virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the start_server.py script
echo "Starting the server..."
python3 start_server.py
