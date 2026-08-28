"""Stamp cancellation GL rows with their Petty Cash Entry source."""

from redtra_customisation.patches.v16_0.add_petty_cash_entry_audit_links import (
	backfill_submitted_petty_cash_entry_links,
)


def execute():
	backfill_submitted_petty_cash_entry_links()
