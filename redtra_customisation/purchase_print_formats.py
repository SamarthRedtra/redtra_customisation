"""Maintain the Pampa Purchase Invoice and Purchase Receipt print formats."""

from base64 import b64encode
from mimetypes import guess_type
from pathlib import Path
import re

import frappe


PRINT_FORMATS = (
	("Purchase Invoice (Custom)", "Purchase Invoice", "pampa_supplier_invoice.html"),
	("G/Received Note (Custom)", "Purchase Receipt", "pampa_received_note.html"),
)


def ensure_pampa_purchase_print_formats():
	"""Create or restore the managed buying print formats without changing documents."""
	for name, doc_type, template_name in PRINT_FORMATS:
		ensure_print_format(name, doc_type, template_name)

	frappe.clear_cache(doctype="Print Format")


def ensure_print_format(name, doc_type, template_name):
	"""Store one managed Jinja template in its existing Print Format record."""
	values = {
		"doc_type": doc_type,
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
		"html": get_template(template_name),
	}

	if frappe.db.exists("Print Format", name):
		print_format = frappe.get_doc("Print Format", name)
		changed = False
		for fieldname, value in values.items():
			if print_format.get(fieldname) != value:
				print_format.set(fieldname, value)
				changed = True
		if changed:
			print_format.save(ignore_permissions=True)
		return

	frappe.get_doc({"doctype": "Print Format", "name": name, **values}).insert(ignore_permissions=True)


def get_template(template_name):
	"""Read one source-controlled Jinja template."""
	path = Path(frappe.get_app_path("redtra_customisation", "templates", "print_formats", template_name))
	return path.read_text(encoding="utf-8")


def get_letter_head_html(company_name, letter_head):
	"""Inline public letterhead images so wkhtmltopdf does not need DNS access."""
	content = letter_head or get_default_letter_head_content(company_name)
	return re.sub(r'src="(?P<url>/files/[^"]+)"', inline_public_file, content or "")


def get_default_letter_head_content(company_name):
	"""Return the company's configured Letter Head HTML when one is available."""
	letter_head_name = frappe.db.get_value("Company", company_name, "default_letter_head")
	return frappe.db.get_value("Letter Head", letter_head_name, "content") if letter_head_name else ""


def inline_public_file(match):
	"""Replace a public image URL with a self-contained data URL when it exists."""
	file_url = match.group("url")
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		return 'src=""'

	file = frappe.get_doc("File", file_name)
	mime_type = guess_type(file.file_name or file_url)[0]
	if not mime_type or not mime_type.startswith("image/"):
		return 'src=""'

	try:
		encoded_content = b64encode(file.get_content()).decode("utf-8")
	except OSError:
		return 'src=""'

	return f'src="data:{mime_type};base64,{encoded_content}"'
