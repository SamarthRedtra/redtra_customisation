"""Keep the Stock Entry voucher layouts aligned without changing their data logic."""

import re

import frappe


PRINT_FORMAT_NAMES = ("Excesses in Stock", "Consumption Voucher", "Stock Transfer")
STYLE_MARKER = "/* redtra-stock-entry-layout */"
LAYOUT_STYLE = """
/* redtra-stock-entry-layout */
@page { size: A4; margin: 8mm; }
.print-format {
	width: 100%;
	max-width: 100%;
	margin: 0;
	padding: 0 4mm !important;
}
.main-box {
	width: 100%;
	max-width: 100%;
	padding: 6px 8px !important;
	overflow: hidden;
}
table.items { width: 100%; table-layout: fixed; border-collapse: collapse; }
table.items th { padding: 6px 2px !important; overflow-wrap: anywhere; }
table.items td { padding: 5px 3px !important; overflow-wrap: anywhere; word-break: break-word; }
"""


def ensure_stock_entry_print_formats():
	"""Apply only layout overrides to the three existing Stock Entry formats."""
	for name in PRINT_FORMAT_NAMES:
		if not frappe.db.exists("Print Format", name):
			continue
		print_format = frappe.get_doc("Print Format", name)
		updated_html = apply_layout(print_format.html or "")
		if updated_html != print_format.html:
			print_format.html = updated_html
			print_format.save(ignore_permissions=True)

	frappe.clear_cache(doctype="Print Format")


def apply_layout(html):
	"""Replace our old override, then append one CSS block after document CSS."""
	pattern = rf"\s*<style>\s*{re.escape(STYLE_MARKER)}.*?</style>"
	clean_html = re.sub(pattern, "", html, flags=re.DOTALL)
	clean_html = re.sub(r"\s*<style>\s*</style>", "", clean_html)
	return f"{clean_html}\n<style>{LAYOUT_STYLE}</style>"
