"""Update the Redtra conversion type to avoid Repack's Finished Good requirement."""

import frappe

from redtra_customisation.override.item_conversion import (
	ITEM_CONVERSION_PURPOSE,
	ITEM_CONVERSION_TYPE,
)


def execute():
	"""Update existing sites that received the earlier Repack-backed type."""
	if not frappe.db.exists("Stock Entry Type", ITEM_CONVERSION_TYPE):
		return

	frappe.db.set_value(
		"Stock Entry Type",
		ITEM_CONVERSION_TYPE,
		"purpose",
		ITEM_CONVERSION_PURPOSE,
		update_modified=False,
	)
