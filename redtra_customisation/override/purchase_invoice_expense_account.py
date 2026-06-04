# Copyright (c) 2026, redtra_customisation contributors

import frappe


@frappe.whitelist()
def is_any_account_allowed_on_pi() -> int:
	return int(
		frappe.db.get_single_value(
			"Redtra Custom Setting", "allow_any_account_on_purchase_invoice"
		)
		or 0
	)
