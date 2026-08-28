"""Maintain the source-controlled Petty Cash Entry print format."""

from pathlib import Path

import frappe


PRINT_FORMAT_NAME = "Petty Cash Voucher"


def ensure_petty_cash_print_format():
	"""Create or restore the Petty Cash Entry voucher format."""
	values = {
		"doc_type": "Petty Cash Entry",
		"print_format_for": "DocType",
		"module": "Accounts",
		"standard": "No",
		"custom_format": 1,
		"print_format_type": "Jinja",
		"pdf_generator": "wkhtmltopdf",
		"page_number": "Bottom Right",
		"margin_top": 6.0,
		"margin_bottom": 6.0,
		"margin_left": 6.0,
		"margin_right": 6.0,
		"font_size": 9,
		"disabled": 0,
		"raw_printing": 0,
		"html": get_template(),
	}
	upsert_print_format(PRINT_FORMAT_NAME, values)
	frappe.clear_cache(doctype="Print Format")


def get_template():
	path = Path(
		frappe.get_app_path("redtra_customisation", "templates", "print_formats", "petty_cash_voucher.html")
	)
	return path.read_text(encoding="utf-8")


def upsert_print_format(name, values):
	if frappe.db.exists("Print Format", name):
		print_format = frappe.get_doc("Print Format", name)
		for fieldname, value in values.items():
			if print_format.get(fieldname) != value:
				print_format.set(fieldname, value)
		print_format.save(ignore_permissions=True)
		return

	frappe.get_doc({"doctype": "Print Format", "name": name, **values}).insert(ignore_permissions=True)
