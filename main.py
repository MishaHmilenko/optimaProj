#!/usr/bin/env python3
"""Entry point: `python3 main.py --chars [--offline] [command...]`,
`python3 main.py --text`, or no option for a mode-selection dialog."""

import sys

from cli import main

if __name__ == "__main__":
    sys.exit(main())
