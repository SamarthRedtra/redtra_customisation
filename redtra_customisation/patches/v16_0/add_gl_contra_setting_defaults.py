import frappe
from frappe.utils import cint


def execute():
	if not frappe.db.exists("DocType", "Redtra Custom Setting"):
		return

	meta = frappe.get_meta("Redtra Custom Setting")
	if not meta.has_field("include_against_account_entries_in_gl"):
		return

	settings = frappe.get_single("Redtra Custom Setting")
	changed = False

	if not cint(settings.get("include_against_account_entries_in_gl")):
		settings.include_against_account_entries_in_gl = 1
		changed = True

	if not cint(settings.get("group_by_against_voucher_in_gl")):
		settings.group_by_against_voucher_in_gl = 1
		changed = True

	if changed:
		settings.save(ignore_permissions=True)
