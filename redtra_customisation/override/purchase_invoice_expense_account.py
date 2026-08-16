# Copyright (c) 2026, redtra_customisation contributors

import frappe


@frappe.whitelist()
def is_any_account_allowed_on_pi() -> int:
	if not frappe.get_meta("Redtra Custom Setting").has_field("allow_any_account_on_purchase_invoice"):
		return 0
	return int(
		frappe.db.get_single_value(
			"Redtra Custom Setting", "allow_any_account_on_purchase_invoice"
		)
		or 0
	)

