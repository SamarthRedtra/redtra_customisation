"""Smoke checks for the managed Pampa Purchase Order print template."""

from redtra_customisation.purchase_order_print_format import (
	DEFAULT_PRINT_FORMAT_PROPERTY_SETTER,
	PRINT_FORMAT_NAME,
	get_pampa_purchase_order_html,
)


def test_pampa_purchase_order_template_contains_required_data_sources():
	"""Keep the template linked to the fields required by the approved layout."""
	template = get_pampa_purchase_order_html()

	for expected_value in (
		"physical_address_lines",
		"company_contact_lines",
		'link_doctype": "Company"',
		"doc.shipping_address or company_address_name",
		"custom_supplier_reference",
		"custom_our_reference",
		"custom_store",
		"custom_cost_code",
		"custom_boe_no",
		"get_letter_head_html",
		"supplier.tax_id",
		"frappe.utils.strip_html",
		"tax_amount",
		"@page { size: A4 portrait",
		"[8 - (doc.items | length)",
		"{:.3f}",
	):
		assert expected_value in template

	assert "address.phone" not in template
	assert "address.fax" not in template
	assert "address.email_id" not in template
	assert "custom_purchase_discount_amount or 0) * (item.qty" not in template


def test_pampa_purchase_order_default_is_stable():
	assert PRINT_FORMAT_NAME == "PO Default 1"
	assert DEFAULT_PRINT_FORMAT_PROPERTY_SETTER == "Purchase Order-main-default_print_format"
