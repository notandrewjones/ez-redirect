#!/usr/bin/env python3
"""
EZ Redirect - Service Runner

This script starts the FastAPI backend server.
It handles path setup so it works whether run from the install directory
or from the backend directory directly.
"""

import os
import sys
from pathlib import Path

# Determine the base directory (parent of backend/)
script_path = Path(__file__).resolve()
backend_dir = script_path.parent
base_dir = backend_dir.parent

# Add base directory to Python path so imports work correctly
sys.path.insert(0, str(base_dir))

# Now we can import our modules
import uvicorn
import json


def get_port():
    """Read port from config.json"""
    config_path = backend_dir / "config.json"
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            return int(config.get("port", 8000))
    except Exception:
        return 8000


def main():
    port = get_port()
    
    # Change to base directory so relative paths in the app work
    os.chdir(base_dir)
    
    print(f"Starting EZ Redirect on port {port}...")
    print(f"Base directory: {base_dir}")
    print(f"Web interface: http://localhost:{port}")
    print(f"Redirect URL: http://localhost:{port}/redirect")
    
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()