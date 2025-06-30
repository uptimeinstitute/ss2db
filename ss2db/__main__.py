#!/usr/bin/env python3
"""
Entry point for running ss2db as a module.

This allows the package to be executed as:
    python -m ss2db --help
"""

from ss2db.main import main

if __name__ == "__main__":
    main()