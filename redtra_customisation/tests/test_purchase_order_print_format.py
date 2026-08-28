"""Smoke checks for the managed Pampa Purchase Order print template."""

from redtra_customisation.purchase_order_print_format import get_pampa_purchase_order_html


def test_pampa_purchase_order_template_contains_required_data_sources():
	"""Keep the template linked to the fields required by the approved layout."""
	template = get_pampa_purchase_order_html()

	for expected_value in (
		"custom_supplier_reference",
		"custom_our_reference",
		"custom_store",
		"custom_cost_code",
		"custom_boe_no",
		"supplier.tax_id",
		"frappe.utils.strip_html",
		"tax_amount",
		"total_amount",
		"@page { size: A4 portrait",
		"{:.6f}",
	):
		assert expected_value in template
