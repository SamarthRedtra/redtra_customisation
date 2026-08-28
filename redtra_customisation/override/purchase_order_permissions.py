# Copyright (c) 2026, redtra_customisation contributors

import frappe

PURCHASE_TYPES = ("Domestic", "International", "Admin")


def get_permission_query_conditions(user: str | None = None) -> str | None:
	"""Apply the restrictions that must also apply to list and API queries."""
	user = user or frappe.session.user
	if user == "Administrator":
		return None

	conditions = []
	if is_restricted_non_stock_user(user):
		conditions.append("(`tabPurchase Order`.is_nonstock = 1)")
	if is_purchase_type_mapped_user(user):
		conditions.append(f"(`tabPurchase Order`.owner = {frappe.db.escape(user)})")

	return " AND ".join(conditions) or None


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	if _existing_po_is_not_owned_by_mapped_user(doc, user):
		return False

	if is_restricted_non_stock_user(user) and not _po_is_nonstock(doc):
		# New PO creation still goes through role permissions; validate enforces is_nonstock.
		if ptype == "create" or _doc_is_new(doc):
			return True
		return False

	if is_purchase_type_mapped_user(user):
		return True

	# The standard role permission check continues after this hook returns True.
	return True


def set_default_is_nonstock(doc, method=None):
	"""Ensure listed users always work on non-stock POs."""
	if not doc.is_new() or doc.get("is_nonstock"):
		return
	if is_restricted_non_stock_user(frappe.session.user):
		doc.is_nonstock = 1


def set_purchase_type_defaults(doc, method=None):
	"""Set a configured default and prevent mapped users from choosing another owner."""
	if not doc.is_new():
		return

	user = frappe.session.user
	if not is_purchase_type_mapped_user(user):
		return

	doc.owner = user
	configuration = get_purchase_type_configuration(user)
	if not doc.get("custom_purchase_type") and configuration.default_type:
		doc.custom_purchase_type = configuration.default_type


def validate_non_stock_user_po(doc, method=None):
	user = frappe.session.user
	if is_restricted_non_stock_user(user) and not frappe.utils.cint(doc.get("is_nonstock")):
		frappe.throw(
			frappe._("You can only create or update non-stock Purchase Orders."),
			title=frappe._("Non Stock Purchase Order Required"),
		)

	validate_purchase_type(doc, user)
	validate_mapped_purchase_order_owner(doc, user)


@frappe.whitelist()
def is_current_user_restricted() -> int:
	return int(is_restricted_non_stock_user(frappe.session.user))


@frappe.whitelist()
def get_current_user_purchase_type_configuration() -> dict:
	"""Return only the calling user's own Purchase Type configuration."""
	configuration = get_purchase_type_configuration(frappe.session.user)
	return {
		"allowed_types": list(configuration.allowed_types),
		"default_type": configuration.default_type,
		"is_mapped": bool(configuration.allowed_types),
	}


def is_restricted_non_stock_user(user: str) -> bool:
	return user in _get_restrict_non_stock_users()


def is_purchase_type_mapped_user(user: str) -> bool:
	return bool(get_purchase_type_configuration(user).allowed_types)


def get_purchase_type_configuration(user: str) -> frappe._dict:
	return _get_purchase_type_configuration(user)


def validate_purchase_type(doc, user: str):
	if not frappe.get_meta("Purchase Order").has_field("custom_purchase_type"):
		return

	purchase_type = doc.get("custom_purchase_type")
	if not purchase_type:
		frappe.throw(
			frappe._("Purchase Type is mandatory."),
			title=frappe._("Purchase Type Required"),
		)
	if purchase_type not in PURCHASE_TYPES:
		frappe.throw(
			frappe._("Purchase Type must be Domestic, International, or Admin."),
			title=frappe._("Invalid Purchase Type"),
		)

	if user == "Administrator":
		return

	allowed_types = get_purchase_type_configuration(user).allowed_types
	if allowed_types and purchase_type not in allowed_types:
		frappe.throw(
			frappe._("You can only select these Purchase Types: {0}.").format(", ".join(allowed_types)),
			title=frappe._("Purchase Type Not Allowed"),
		)


def validate_mapped_purchase_order_owner(doc, user: str):
	if user == "Administrator" or not is_purchase_type_mapped_user(user):
		return

	if doc.get("owner") != user:
		frappe.throw(
			frappe._("You can only create or update Purchase Orders you own."),
			exc=frappe.PermissionError,
		)


def _doc_is_new(doc) -> bool:
	if doc.get("__islocal"):
		return True
	is_new = getattr(doc, "is_new", None)
	if callable(is_new):
		return is_new()
	return not doc.get("name")


def _existing_po_is_not_owned_by_mapped_user(doc, user: str) -> bool:
	if not is_purchase_type_mapped_user(user) or _doc_is_new(doc):
		return False
	return _po_owner(doc) != user


def _po_is_nonstock(doc) -> bool:
	is_nonstock = doc.get("is_nonstock")
	if is_nonstock is None and doc.get("name"):
		is_nonstock = frappe.db.get_value("Purchase Order", doc.name, "is_nonstock")
	return frappe.utils.cint(is_nonstock)


def _po_owner(doc) -> str | None:
	owner = doc.get("owner")
	if owner is None and doc.get("name"):
		owner = frappe.db.get_value("Purchase Order", doc.name, "owner")
	return owner


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


@frappe.request_cache
def _get_purchase_type_configuration(user: str) -> frappe._dict:
	if not frappe.db.table_exists("Purchase Type User Mapping"):
		return frappe._dict(allowed_types=(), default_type=None)

	rows = frappe.get_all(
		"Purchase Type User Mapping",
		filters={"parent": "Redtra Custom Setting", "parenttype": "Redtra Custom Setting", "user": user},
		fields=["purchase_type", "is_default"],
		order_by="idx asc",
	)
	allowed_types = tuple(row.purchase_type for row in rows if row.purchase_type in PURCHASE_TYPES)
	default_type = next((row.purchase_type for row in rows if frappe.utils.cint(row.is_default)), None)
	return frappe._dict(allowed_types=allowed_types, default_type=default_type)
