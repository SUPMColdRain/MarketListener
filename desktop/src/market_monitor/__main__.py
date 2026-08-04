"""Allow ``python -m market_monitor``."""

import sys

from market_monitor.cli import main

if __name__ == "__main__":
    sys.exit(main())
