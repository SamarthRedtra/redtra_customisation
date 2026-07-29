# Copyright (c) 2026, redtra_customisation contributors

"""Reusable Company scope for transaction doctypes.

Frappe does not automatically apply a Company User Permission to every custom
or standard transaction list. These helpers make the scope consistent for the
transaction doctypes configured in hooks.py.
"""

import frappe


def get_company_permission_query_conditions(doctype: str, user: str | None = None) -> str | None:
	companies = get_allowed_companies(user)
	if companies is None:
		return None

	escaped = ", ".join(frappe.db.escape(company) for company in companies)
	return f"`tab{doctype}`.company in ({escaped})"


def has_company_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	companies = get_allowed_companies(user)
	if companies is None:
		return None

	company = doc.get("company") if doc else None
	# Normal DocType permissions still govern a new document before Company is set.
	if not company:
		return None
	return company in companies


def get_allowed_companies(user: str | None = None) -> set[str] | None:
	"""Return explicit Company permissions; None means no Company restriction."""
	user = user or frappe.session.user
	if user == "Administrator":
		return None

	permissions = frappe.permissions.get_user_permissions(user)
	company_permissions = permissions.get("Company") or []
	companies = {row.get("doc") for row in company_permissions if row.get("doc")}
	return companies or None


def get_purchase_receipt_permission_query_conditions(user: str | None = None) -> str | None:
	return get_company_permission_query_conditions("Purchase Receipt", user)


def get_purchase_invoice_permission_query_conditions(user: str | None = None) -> str | None:
	return get_company_permission_query_conditions("Purchase Invoice", user)
