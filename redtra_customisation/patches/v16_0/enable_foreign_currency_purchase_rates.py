import frappe


TRANSACTION_DOCTYPES = (
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
)

TRANSACTION_ITEM_DOCTYPES = (
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Quotation Item",
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
)

RATE_AND_AMOUNT_FIELDS = (
	"price_list_rate",
	"base_price_list_rate",
	"rate_with_margin",
	"base_rate_with_margin",
	"rate",
	"base_rate",
	"net_rate",
	"base_net_rate",
	"stock_uom_rate",
	"amount",
	"base_amount",
	"net_amount",
	"base_net_amount",
	"stock_uom_amount",
)


def execute():
	"""Enable multi-currency transaction controls and six-decimal amounts."""
	apply_settings()


def apply_settings():
	"""Apply transaction metadata after fixtures and custom fields have synced."""
	for doctype in TRANSACTION_DOCTYPES:
		_set_property_if_field_exists(doctype, "currency_and_price_list", "hidden", 0, "Check")

	for doctype in TRANSACTION_ITEM_DOCTYPES:
		for fieldname in RATE_AND_AMOUNT_FIELDS:
			_set_property_if_field_exists(doctype, fieldname, "precision", 6, "Currency")

	for doctype in (*TRANSACTION_DOCTYPES, *TRANSACTION_ITEM_DOCTYPES):
		frappe.clear_cache(doctype=doctype)


def _set_property_if_field_exists(doctype, fieldname, property_name, value, property_type):
	"""Set a Property Setter only when the installed DocType contains the field."""
	if not frappe.get_meta(doctype).has_field(fieldname):
		return

	_set_property(doctype, fieldname, property_name, value, property_type)


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
