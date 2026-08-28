"""Create the initial Purchase Type mappings and backfill eligible draft POs."""

from collections import defaultdict

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.purchase_order_custom_fields import PURCHASE_ORDER_CUSTOM_FIELDS

INITIAL_MAPPINGS = (
	("murugan@pampauae.com", "Domestic", 0),
	("murugan@pampauae.com", "International", 0),
	("bandana@pampauae.com", "Admin", 1),
)


def execute():
	"""Apply the initial configuration without overwriting later Settings changes."""
	if not frappe.db.exists("DocType", "Redtra Custom Setting"):
		return

	create_custom_fields(PURCHASE_ORDER_CUSTOM_FIELDS, ignore_validate=True)
	frappe.clear_cache(doctype="Purchase Order")

	if not frappe.db.table_exists("Purchase Type User Mapping"):
		return

	settings = frappe.get_single("Redtra Custom Setting")
	known_mappings = {
		(row.user, row.purchase_type)
		for row in settings.get("purchase_type_user_mappings") or []
	}
	changed = False
	for user, purchase_type, is_default in INITIAL_MAPPINGS:
		if (user, purchase_type) in known_mappings:
			continue
		settings.append(
			"purchase_type_user_mappings",
			{"user": user, "purchase_type": purchase_type, "is_default": is_default},
		)
		changed = True

	if changed:
		settings.save(ignore_permissions=True)

	backfill_draft_purchase_orders()
	frappe.clear_cache(doctype="Redtra Custom Setting")
	frappe.clear_cache(doctype="Purchase Order")


def backfill_draft_purchase_orders():
	"""Type only drafts whose owner has exactly one configured Purchase Type."""
	configured_types = defaultdict(set)
	for row in frappe.get_all(
		"Purchase Type User Mapping",
		filters={"parent": "Redtra Custom Setting", "parenttype": "Redtra Custom Setting"},
		fields=["user", "purchase_type"],
	):
		if row.user and row.purchase_type:
			configured_types[row.user].add(row.purchase_type)

	if not configured_types:
		return

	for purchase_order in frappe.get_all(
		"Purchase Order",
		filters={"docstatus": 0},
		fields=["name", "owner", "custom_purchase_type"],
	):
		allowed_types = configured_types.get(purchase_order.owner, set())
		if purchase_order.custom_purchase_type or len(allowed_types) != 1:
			continue

		frappe.db.set_value(
			"Purchase Order",
			purchase_order.name,
			"custom_purchase_type",
			next(iter(allowed_types)),
			update_modified=False,
		)
