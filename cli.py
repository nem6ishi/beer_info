#!/usr/bin/env python
import sys
import os

# Add the project root to PYTHONPATH to allow imports to work correctly
sys.path.append(os.getcwd())

if __name__ == "__main__":
    from backend.src.cli import main
    main()
