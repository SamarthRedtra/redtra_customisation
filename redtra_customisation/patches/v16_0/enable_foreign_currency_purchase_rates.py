import frappe


RATE_FIELDS = (
	"price_list_rate",
	"base_price_list_rate",
	"rate_with_margin",
	"base_rate_with_margin",
	"rate",
	"base_rate",
	"net_rate",
	"base_net_rate",
	"stock_uom_rate",
)

PURCHASE_ITEM_DOCTYPES = ("Purchase Order Item", "Purchase Invoice Item")


def execute():
	"""Enable foreign-currency purchasing and retain six-decimal unit rates."""
	apply_settings()


def apply_settings():
	"""Apply the purchase metadata after fixtures have been synced."""
	_set_property("Purchase Order", "currency_and_price_list", "hidden", 0, "Check")

	for doctype in PURCHASE_ITEM_DOCTYPES:
		for fieldname in RATE_FIELDS:
			_set_property(doctype, fieldname, "precision", 6, "Currency")

	frappe.clear_cache(doctype="Purchase Order")
	frappe.clear_cache(doctype="Purchase Invoice")


def _set_property(doctype, fieldname, property_name, value, property_type):
	filters = {
		"doc_type": doctype,
		"field_name": fieldname,
		"property": property_name,
		"doctype_or_field": "DocField",
	}
	property_setter = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)

	if property_setter:
		if property_setter.value != str(value):
			frappe.db.set_value("Property Setter", property_setter.name, "value", value)
		return

	frappe.make_property_setter(
		{
			"doctype": doctype,
			"fieldname": fieldname,
			"property": property_name,
			"value": value,
			"property_type": property_type,
		},
		validate_fields_for_doctype=False,
		is_system_generated=False,
	)
