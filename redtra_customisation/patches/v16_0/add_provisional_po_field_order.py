import json

import frappe


def execute():
	"""Ensure provisional PO fields appear on the Purchase Order form layout."""
	field_order_name = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Purchase Order", "property": "field_order", "doctype_or_field": "DocType"},
		"name",
	)
	if not field_order_name:
		return

	raw_value = frappe.db.get_value("Property Setter", field_order_name, "value")
	if not raw_value:
		return

	try:
		fields = json.loads(raw_value)
	except json.JSONDecodeError:
		return

	if not isinstance(fields, list):
		return

	insert_after = "is_subcontracted"
	if insert_after not in fields:
		return

	insert_at = fields.index(insert_after) + 1
	changed = False

	for fieldname in ("is_nonstock", "custom_is_provisional_po"):
		if fieldname in fields:
			continue
		if not frappe.db.exists("Custom Field", {"dt": "Purchase Order", "fieldname": fieldname}):
			continue
		fields.insert(insert_at, fieldname)
		insert_at += 1
		changed = True

	if changed:
		frappe.db.set_value("Property Setter", field_order_name, "value", json.dumps(fields))
		frappe.clear_cache(doctype="Purchase Order")
