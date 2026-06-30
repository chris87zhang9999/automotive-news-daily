"""Build static site from all reports/*.md → site/index.html."""
import logging
import sys
from pathlib import Path
from src.site_builder import build_site

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

REPORTS_DIR = Path("reports")
SITE_DIR = Path("site")

if __name__ == "__main__":
    build_site(reports_dir=REPORTS_DIR, site_dir=SITE_DIR)
    sys.exit(0)
