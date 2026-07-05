# Copyright (c) 2026, redtra_customisation contributors

import frappe


def is_pi_point_adjustment_gl_split_enabled() -> bool:
	return bool(
		frappe.db.get_single_value(
			"Redtra Custom Setting", "enable_purchase_invoice_point_adjustment_gl_split"
		)
	)


def get_pi_point_adjustment_account() -> str | None:
	if not is_pi_point_adjustment_gl_split_enabled():
		return None

	return frappe.db.get_single_value(
		"Redtra Custom Setting", "purchase_invoice_point_adjustment_account"
	)


@frappe.whitelist()
def is_pi_point_adjustment_gl_split_enabled_api() -> int:
	return int(is_pi_point_adjustment_gl_split_enabled())
