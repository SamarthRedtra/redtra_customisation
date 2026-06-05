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
	if user == "Administrator":
		return None

	if not is_restricted_non_stock_user(user):
		# Non-listed users are not subject to non-stock PO restrictions.
		# Allow read/select so PR/GRN can reference linked POs without a PO read role.
		if ptype in ("read", "select"):
			return True
		return None

	# Listed users may only work with non-stock POs.
	if _po_is_nonstock(doc):
		return None

	# New PO creation still goes through role permissions; validate enforces is_nonstock.
	if ptype == "create" or _doc_is_new(doc):
		return None

	if ptype in ("read", "select"):
		return False

	return False


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


def _doc_is_new(doc) -> bool:
	if doc.get("__islocal"):
		return True
	is_new = getattr(doc, "is_new", None)
	if callable(is_new):
		return is_new()
	return not doc.get("name")


def _po_is_nonstock(doc) -> bool:
	is_nonstock = doc.get("is_nonstock")
	if is_nonstock is None and doc.get("name"):
		is_nonstock = frappe.db.get_value("Purchase Order", doc.name, "is_nonstock")
	return frappe.utils.cint(is_nonstock)


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
