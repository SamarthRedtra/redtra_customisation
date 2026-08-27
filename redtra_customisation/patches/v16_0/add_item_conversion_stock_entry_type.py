"""Add the controlled item-conversion label to standard Stock Entry."""

import frappe


ITEM_CONVERSION_TYPE = "Item Conversion / Dismantling"
ITEM_CONVERSION_PURPOSE = "Material Transfer"


def execute():
	"""Create or correct the conversion type with its standard ledger purpose."""
	if frappe.db.exists("Stock Entry Type", ITEM_CONVERSION_TYPE):
		purpose = frappe.db.get_value("Stock Entry Type", ITEM_CONVERSION_TYPE, "purpose")
		if purpose != ITEM_CONVERSION_PURPOSE:
			frappe.db.set_value(
				"Stock Entry Type",
				ITEM_CONVERSION_TYPE,
				"purpose",
				ITEM_CONVERSION_PURPOSE,
				update_modified=False,
			)
		return

	frappe.get_doc(
		{
			"doctype": "Stock Entry Type",
			"name": ITEM_CONVERSION_TYPE,
			"purpose": ITEM_CONVERSION_PURPOSE,
			"is_standard": 0,
		}
	).insert(ignore_permissions=True)
