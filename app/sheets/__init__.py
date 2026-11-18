"""Optional Google Sheets integration. Off unless GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_FILE are set."""
from __future__ import annotations

import logging

from app.config import Settings
from app.sheets.service import SheetsSync

__all__ = ["SheetsSync", "create_sheets"]

log = logging.getLogger(__name__)


def create_sheets(settings: Settings) -> SheetsSync | None:
    """The real Google-backed sync, or None when the feature is off or cannot be set up."""
    if not settings.sheets_enabled:
        if settings.google_sheet_id.strip() or settings.google_service_account_file.strip():
            log.warning("Google Sheets is off: set both GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_FILE")
        return None
    try:
        import gspread  # noqa: F401  (checked here so a missing package is reported once, at startup)
    except ImportError:
        log.error("Google Sheets is configured but gspread is not installed: pip install -r requirements.txt")
        return None
    from app.sheets.gspread_backend import GspreadBackend

    backend = GspreadBackend(settings.google_sheet_id.strip(), settings.google_service_account_file.strip())
    return SheetsSync(backend, settings)
