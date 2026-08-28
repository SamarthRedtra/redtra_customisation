"""Smoke checks for the managed Pampa buying print templates."""

from redtra_customisation.purchase_print_formats import get_template


def test_supplier_invoice_template_has_required_data_sources():
	"""Keep the Supplier Invoice connected to ERPNext buying fields."""
	template = get_template("pampa_supplier_invoice.html")

	for expected_value in (
		"doc.bill_no",
		"item.purchase_receipt",
		"tax_amount",
		"total_amount",
		"{:.6f}",
		"get_letter_head_html",
		"@page { size: A4 portrait",
	):
		assert expected_value in template


def test_received_note_template_has_required_data_sources():
	"""Keep the G/Received Note linked to the standard receipt fields."""
	template = get_template("pampa_received_note.html")

	for expected_value in (
		"custom_supplier_ref",
		"supplier_delivery_note",
		"item.purchase_order",
		"item.warehouse",
		"@page { size: A4 portrait",
	):
		assert expected_value in template
