"""Custom fields owned by the Purchase Order access customisation."""

import frappe

PURCHASE_ORDER_CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": "custom_default_purchase_order_tax_template",
			"fieldtype": "Link",
			"label": "Default Purchase Order Tax Template",
			"options": "Purchase Taxes and Charges Template",
			"insert_after": "custom_default_purchase_invoice_tax_template",
		},
	],
	"Purchase Order": [
		{
			"fieldname": "custom_purchase_type",
			"fieldtype": "Select",
			"label": "Purchase Type",
			"options": "Domestic\nInternational\nAdmin",
			"insert_after": "supplier_name",
			"reqd": 1,
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "custom_store",
			"fieldtype": "Data",
			"label": "Store",
			"insert_after": "custom_purchase_type",
		},
		{
			"fieldname": "custom_cost_code",
			"fieldtype": "Data",
			"label": "Cost Code",
			"insert_after": "custom_store",
		},
		{
			"fieldname": "custom_boe_no",
			"fieldtype": "Data",
			"label": "BOE No.",
			"insert_after": "custom_cost_code",
		},
		{
			"fieldname": "custom_purchase_discount_total",
			"fieldtype": "Currency",
			"label": "Item Discount Total",
			"insert_after": "discount_amount",
			"read_only": 1,
		},
	],
	"Purchase Order Item": [
		{
			"fieldname": "custom_purchase_discount_amount",
			"fieldtype": "Currency",
			"label": "Discount Amount",
			"description": "Absolute discount for this complete row. It does not change the item Rate.",
			"insert_after": "amount",
			"in_list_view": 1,
		},
		{
			"fieldname": "custom_purchase_discount_account",
			"fieldtype": "Link",
			"label": "Discount Account",
			"options": "Account",
			"insert_after": "custom_purchase_discount_amount",
			"in_list_view": 1,
		},
	],
	"Purchase Taxes and Charges": [
		{
			"fieldname": "custom_is_purchase_item_discount",
			"fieldtype": "Check",
			"label": "Purchase Item Discount",
			"default": "0",
			"hidden": 1,
			"read_only": 1,
		},
	],
}


def ensure_purchase_order_discount_field_label():
	"""Keep the account-backed line discount labelled clearly after migration."""
	custom_field_name = "Purchase Order Item-custom_purchase_discount_amount"
	if not frappe.db.exists("Custom Field", custom_field_name):
		return

	custom_field = frappe.get_doc("Custom Field", custom_field_name)
	expected_values = {
		"label": "Discount Amount",
		"description": "Absolute discount for this complete row. It does not change the item Rate.",
		"hidden": 0,
		"in_list_view": 1,
	}
	if any(custom_field.get(fieldname) != value for fieldname, value in expected_values.items()):
		custom_field.update(expected_values)
		custom_field.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Purchase Order Item")


def ensure_standard_purchase_order_rate_discounts_hidden():
	"""Hide ERPNext's rate-reduction inputs so the absolute field is unambiguous."""
	for fieldname in ("discount_amount", "discount_percentage"):
		for property_name in ("hidden", "in_list_view"):
			value = "1" if property_name == "hidden" else "0"
			name = f"Purchase Order Item-{fieldname}-redtra-{property_name}"
			values = {
				"doctype_or_field": "DocField",
				"doc_type": "Purchase Order Item",
				"field_name": fieldname,
				"property": property_name,
				"property_type": "Check",
				"value": value,
				"is_system_generated": 1,
			}
			if frappe.db.exists("Property Setter", name):
				property_setter = frappe.get_doc("Property Setter", name)
				if any(property_setter.get(key) != value for key, value in values.items()):
					property_setter.update(values)
					property_setter.save(ignore_permissions=True)
			else:
				frappe.get_doc({"doctype": "Property Setter", "name": name, **values}).insert(
					ignore_permissions=True
				)

	frappe.clear_cache(doctype="Purchase Order Item")
