"""Unit checks for Purchase Order absolute line-discount semantics."""

from pathlib import Path

import frappe

from redtra_customisation.purchase_item_discount import get_item_discount_amount
from redtra_customisation.purchase_order_tax import (
	DEFAULT_COMPANY,
	DEFAULT_TAX_TEMPLATE,
	DEFAULT_TAX_TEMPLATE_FIELD,
)


def test_purchase_order_discount_is_absolute_for_any_quantity():
	for quantity in (1, 2, 10):
		document = frappe._dict(doctype="Purchase Order")
		item = frappe._dict(custom_purchase_discount_amount=30, qty=quantity)
		assert get_item_discount_amount(document, item) == 30


def test_purchase_order_discount_code_never_rewrites_rate():
	module_path = Path(__file__).parents[1] / "purchase_item_discount.py"
	assert ".rate =" not in module_path.read_text(encoding="utf-8")


def test_purchase_invoice_discount_remains_per_unit():
	document = frappe._dict(doctype="Purchase Invoice")
	item = frappe._dict(custom_purchase_discount_amount=30, qty=2)
	assert get_item_discount_amount(document, item) == 60


def test_pampa_purchase_order_vat_defaults_are_stable():
	assert DEFAULT_COMPANY == "Pampa Industries International Corp"
	assert DEFAULT_TAX_TEMPLATE == "UAE VAT 5% - PIC"
	assert DEFAULT_TAX_TEMPLATE_FIELD == "custom_default_purchase_order_tax_template"
