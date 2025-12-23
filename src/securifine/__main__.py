"""Entry point for running SecuriFine as a module.

Allows execution via: python -m securifine
"""

import sys

from securifine.cli import main

if __name__ == "__main__":
    sys.exit(main())
