# Copyright (c) 2026, redtra_customisation contributors

import frappe


def get_permission_query_conditions(user: str | None = None) -> str | None:
	"""Listed users can only see non-stock Purchase Orders."""
	user = user or frappe.session.user
	if user == "Administrator" or not is_restricted_non_stock_user(user):
		return None

	return "(`tabPurchase Order`.is_nonstock = 1)"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	user = user or frappe.session.user
	if user == "Administrator" or not is_restricted_non_stock_user(user):
		return None

	if not frappe.utils.cint(doc.get("is_nonstock")):
		return False

	return None


def set_default_is_nonstock(doc, method=None):
	"""Ensure listed users always work on non-stock POs."""
	if not doc.is_new() or doc.get("is_nonstock"):
		return
	if is_restricted_non_stock_user(frappe.session.user):
		doc.is_nonstock = 1


def validate_non_stock_user_po(doc, method=None):
	if not is_restricted_non_stock_user(frappe.session.user):
		return
	if not frappe.utils.cint(doc.get("is_nonstock")):
		frappe.throw(
			frappe._("You can only create or update non-stock Purchase Orders."),
			title=frappe._("Non Stock Purchase Order Required"),
		)


@frappe.whitelist()
def is_current_user_restricted() -> int:
	return int(is_restricted_non_stock_user(frappe.session.user))


def is_restricted_non_stock_user(user: str) -> bool:
	return user in _get_restrict_non_stock_users()


@frappe.request_cache
def _get_restrict_non_stock_users() -> set[str]:
	if not frappe.db.table_exists("Restrict Non Stockable Item User"):
		return set()

	rows = frappe.get_all(
		"Restrict Non Stockable Item User",
		filters={"parent": "Redtra Custom Setting", "parenttype": "Redtra Custom Setting"},
		pluck="user",
	)
	return {row for row in rows if row}
