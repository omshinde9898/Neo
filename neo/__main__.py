"""Entry point for Neo."""

from neo.logger import setup_logging
from neo.cli import main

# Initialize logging on startup
setup_logging()

if __name__ == "__main__":
    main()
