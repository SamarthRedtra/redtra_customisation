"""Maintain the single approved Purchase Order naming series."""

import frappe


PURCHASE_ORDER_NAMING_SERIES = "PUR-ORD-.YYYY.-"
_PROPERTY_SETTERS = (
	("options", "Text", PURCHASE_ORDER_NAMING_SERIES),
	("default", "Text", PURCHASE_ORDER_NAMING_SERIES),
)


def ensure_purchase_order_naming_series():
	"""Restrict new Purchase Orders to the approved series after every migration."""
	for property_name, property_type, value in _PROPERTY_SETTERS:
		property_setter_name = f"Purchase Order-naming_series-{property_name}-redtra"
		if frappe.db.exists("Property Setter", property_setter_name):
			property_setter = frappe.get_doc("Property Setter", property_setter_name)
			if property_setter.value != value:
				property_setter.value = value
				property_setter.save(ignore_permissions=True)
			continue

		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"name": property_setter_name,
				"doctype_or_field": "DocField",
				"doc_type": "Purchase Order",
				"field_name": "naming_series",
				"property": property_name,
				"property_type": property_type,
				"value": value,
				"is_system_generated": 1,
			}
		).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Purchase Order")


def set_purchase_order_naming_series(doc, method=None):
	"""Select the only supported series for every newly-created Purchase Order."""
	# This handler runs only on ``before_insert``; assigning unconditionally also
	# protects inserts made through imports and the REST API.
	doc.naming_series = PURCHASE_ORDER_NAMING_SERIES


def validate_purchase_order_naming_series(doc, method=None):
	"""Reject changes away from the approved series without blocking historic POs."""
	is_new = doc.is_new()
	existing_series = None if is_new else frappe.db.get_value("Purchase Order", doc.name, "naming_series")
	if (is_new or existing_series == PURCHASE_ORDER_NAMING_SERIES) and doc.naming_series != PURCHASE_ORDER_NAMING_SERIES:
		frappe.throw(
			frappe._("Purchase Orders must use the naming series {0}.").format(
				frappe.bold(PURCHASE_ORDER_NAMING_SERIES)
			),
			title=frappe._("Invalid Purchase Order Series"),
		)
