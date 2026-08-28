"""Link submitted petty-cash vouchers to their Payment and GL Entries."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.petty_cash_custom_fields import PETTY_CASH_LINK_CUSTOM_FIELDS
from redtra_customisation.redtra_customisation.doctype.petty_cash_entry.petty_cash_entry import (
	link_payment_entry_and_gl_entries,
)


def execute():
	create_custom_fields(PETTY_CASH_LINK_CUSTOM_FIELDS, ignore_validate=True)
	backfill_submitted_petty_cash_entry_links()


def backfill_submitted_petty_cash_entry_links():
	"""Backfill only Payment Entries that prove they belong to the submitted voucher."""
	for entry in frappe.get_all(
		"Petty Cash Entry", filters={"docstatus": ("in", (1, 2))}, fields=["name", "company"]
	):
		payment_entries = frappe.get_all(
			"Petty Cash Entry Account",
			filters={"parent": entry.name, "parenttype": "Petty Cash Entry", "payment_entry": ("is", "set")},
			pluck="payment_entry",
		)
		for payment_entry_name in payment_entries:
			if not _is_linked_payment_entry(entry, payment_entry_name):
				continue
			link_payment_entry_and_gl_entries(entry.name, payment_entry_name)

		if payment_entries:
			frappe.db.set_value(
				"Petty Cash Entry",
				entry.name,
				"payment_entry",
				payment_entries[0],
				update_modified=False,
			)


def _is_linked_payment_entry(entry, payment_entry_name):
	return frappe.db.exists(
		"Payment Entry",
		{
			"name": payment_entry_name,
			"company": entry.company,
			"reference_no": entry.name,
			"payment_type": "Internal Transfer",
		},
	)
