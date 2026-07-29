# Copyright (c) 2026, redtra_customisation contributors

"""Company-scoped access for Post Dated Cheques.

The PDC doctype has a mandatory Company field, but user permissions on
Company are not applied automatically to its List View. Enforce the scope at
the query layer so the List View, link searches, exports, and API list calls
all return the same records.
"""

import frappe

from redtra_customisation.override.company_permissions import get_allowed_companies


def get_permission_query_conditions(user: str | None = None) -> str | None:
	"""Return the Company condition for users with explicit Company access."""
	companies = get_allowed_companies(user)
	if companies is None:
		return None

	escaped = ", ".join(frappe.db.escape(company) for company in companies)
	return f"`tabPost Dated Cheques`.company in ({escaped})"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	"""Do not allow direct access to a PDC outside the user's Company scope."""
	companies = get_allowed_companies(user)
	if companies is None:
		return None

	company = doc.get("company") if doc else None
	# Let normal DocType permissions handle a new document until its Company is chosen.
	if not company:
		return None
	return company in companies


@frappe.whitelist()
def get_current_user_companies() -> list[str]:
	"""Expose the current user's PDC Company scope for the List View label."""
	companies = get_allowed_companies()
	return sorted(companies) if companies is not None else []
