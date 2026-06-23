import frappe
from frappe.utils import cint


def execute():
	if not frappe.db.exists("DocType", "Redtra Custom Setting"):
		return

	meta = frappe.get_meta("Redtra Custom Setting")
	if not meta.has_field("enable_provisional_purchase_order"):
		return

	settings = frappe.get_single("Redtra Custom Setting")
	changed = False

	if not cint(settings.get("enable_provisional_purchase_order")):
		settings.enable_provisional_purchase_order = 1
		changed = True

	if not cint(settings.get("auto_sync_po_qty_on_receipt")):
		settings.auto_sync_po_qty_on_receipt = 1
		changed = True

	if changed:
		settings.save(ignore_permissions=True)
