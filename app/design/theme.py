from __future__ import annotations

from pathlib import Path
from typing import Final

# -----------------------------------------------------------------------------
# Design system root
# -----------------------------------------------------------------------------

DESIGN_DIR: Final[Path] = Path(__file__).resolve().parent
ASSETS_DIR: Final[Path] = DESIGN_DIR / "assets"
CSS_DIR: Final[Path] = DESIGN_DIR / "css"

# -----------------------------------------------------------------------------
# Brand assets
# -----------------------------------------------------------------------------

LOGO_FILE: Final[Path] = ASSETS_DIR / "PPC.png"

# -----------------------------------------------------------------------------
# CSS architecture
# Order matters:
# 1) tokens / globals
# 2) layout
# 3) page-level modules
# 4) form controls
# 5) interactive elements
# 6) navigation
# 7) data display
# -----------------------------------------------------------------------------

CSS_FILE_ORDER: Final[tuple[str, ...]] = (
    "main.css",
    "layout.css",
    "auth.css",
    "dashboard.css",
    "projects.css",
    "search_reports.css",
    "forms.css",
    "buttons.css",
    "sidebar.css",
    "tables.css",
    "responsive.css",
    "luxury_2026.css",
    "mobile_fast.css",
)

CSS_FILES: Final[tuple[Path, ...]] = tuple(CSS_DIR / name for name in CSS_FILE_ORDER)
