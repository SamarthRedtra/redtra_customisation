"""Maintain the Pampa portrait Purchase Order print format."""

from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.purchase_order_custom_fields import PURCHASE_ORDER_CUSTOM_FIELDS


PRINT_FORMAT_NAME = "PO Default 1"
TEMPLATE_PATH = ("templates", "print_formats", "pampa_purchase_order.html")


def get_pampa_purchase_order_html():
	"""Return the approved portrait Purchase Order Jinja template."""
	path = Path(frappe.get_app_path("redtra_customisation", *TEMPLATE_PATH))
	return path.read_text(encoding="utf-8")


def ensure_pampa_purchase_order_print_format():
	"""Create or restore the managed portrait print format without touching POs."""
	create_custom_fields(PURCHASE_ORDER_CUSTOM_FIELDS, ignore_validate=True)

	values = {
		"doc_type": "Purchase Order",
		"print_format_for": "DocType",
		"module": "Buying",
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
		"html": get_pampa_purchase_order_html(),
	}

	if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
		print_format = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
		changed = False
		for fieldname, value in values.items():
			if print_format.get(fieldname) != value:
				print_format.set(fieldname, value)
				changed = True
		if changed:
			print_format.save(ignore_permissions=True)
	else:
		print_format = frappe.get_doc({"doctype": "Print Format", "name": PRINT_FORMAT_NAME, **values})
		print_format.insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Print Format")
