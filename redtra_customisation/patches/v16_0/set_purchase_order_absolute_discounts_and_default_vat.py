"""Configure absolute PO discounts and correct the approved draft example."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt

from redtra_customisation.purchase_invoice.default_accounts import get_default_discount_account
from redtra_customisation.purchase_item_discount import DISCOUNT_MARKER
from redtra_customisation.purchase_order_custom_fields import PURCHASE_ORDER_CUSTOM_FIELDS
from redtra_customisation.purchase_order_tax import (
	DEFAULT_COMPANY,
	DEFAULT_TAX_TEMPLATE,
	initialize_default_purchase_order_tax_template,
)


PURCHASE_ORDER = "PUR-ORD-2026-00223"
ITEM_CODE = "GS50100"
EXPECTED_TOTAL = 140.0
EXPECTED_DISCOUNT = 30.0
EXPECTED_TAXABLE = 110.0
EXPECTED_VAT = 5.5
EXPECTED_GRAND_TOTAL = 115.5


def execute():
	create_custom_fields(PURCHASE_ORDER_CUSTOM_FIELDS, ignore_validate=True)
	initialize_default_purchase_order_tax_template()

	if not frappe.db.exists("Purchase Order", PURCHASE_ORDER):
		return

	purchase_order = frappe.get_doc("Purchase Order", PURCHASE_ORDER)
	if _is_correct(purchase_order):
		return

	if not _matches_expected_draft(purchase_order):
		frappe.logger("redtra_customisation").warning(
			"Skipped %s correction because the draft no longer matches the approved AED 140 snapshot.",
			PURCHASE_ORDER,
		)
		return
	discount_account = get_default_discount_account(purchase_order.company)
	if not discount_account:
		frappe.throw("A configured Purchase Invoice Discount Account is required for the PO correction.")

	item = purchase_order.items[0]
	item.custom_purchase_discount_amount = EXPECTED_DISCOUNT
	item.custom_purchase_discount_account = discount_account
	item.discount_amount = 0
	item.discount_percentage = 0
	purchase_order.taxes_and_charges = DEFAULT_TAX_TEMPLATE
	purchase_order.set("taxes", [])
	purchase_order.save(ignore_permissions=True)

	purchase_order.reload()
	if not _is_correct(purchase_order):
		frappe.throw(
			f"{PURCHASE_ORDER} did not recalculate to AED 140.00 less AED 30.00, "
			"plus AED 5.50 VAT. The migration was rolled back."
		)


def _matches_expected_draft(purchase_order):
	if purchase_order.docstatus != 0:
		return False
	if purchase_order.company != DEFAULT_COMPANY or purchase_order.currency != "AED":
		return False
	if not _same(purchase_order.total, EXPECTED_TOTAL) or not _same(
		purchase_order.net_total, EXPECTED_TOTAL
	):
		return False
	if len(purchase_order.items) != 1:
		return False

	item = purchase_order.items[0]
	legacy_discount = flt(item.custom_purchase_discount_amount)
	if (
		item.item_code != ITEM_CODE
		or not _same(item.qty, 2)
		or not _same(item.rate, 70)
		or not _same(item.amount, EXPECTED_TOTAL)
		or not any(_same(legacy_discount, value) for value in (30, 45))
	):
		return False
	discount_rows = [row for row in purchase_order.taxes if cint(row.get(DISCOUNT_MARKER))]
	if (
		purchase_order.taxes_and_charges
		or any(not cint(row.get(DISCOUNT_MARKER)) for row in purchase_order.taxes)
		or len(discount_rows) != 1
		or not _same(discount_rows[0].tax_amount, legacy_discount * flt(item.qty))
	):
		return False
	return True


def _is_correct(purchase_order):
	if purchase_order.docstatus != 0 or len(purchase_order.items) != 1:
		return False
	item = purchase_order.items[0]
	discount_rows = [row for row in purchase_order.taxes if cint(row.get(DISCOUNT_MARKER))]
	vat_rows = [row for row in purchase_order.taxes if not cint(row.get(DISCOUNT_MARKER))]
	return bool(
		purchase_order.taxes_and_charges == DEFAULT_TAX_TEMPLATE
		and item.item_code == ITEM_CODE
		and _same(item.custom_purchase_discount_amount, EXPECTED_DISCOUNT)
		and _same(purchase_order.total, EXPECTED_TOTAL)
		and _same(purchase_order.custom_purchase_discount_total, EXPECTED_DISCOUNT)
		and _same(EXPECTED_TOTAL - purchase_order.custom_purchase_discount_total, EXPECTED_TAXABLE)
		and _same(purchase_order.grand_total, EXPECTED_GRAND_TOTAL)
		and len(discount_rows) == 1
		and _same(discount_rows[0].tax_amount, EXPECTED_DISCOUNT)
		and len(vat_rows) == 1
		and _same(vat_rows[0].rate, 5)
		and _same(vat_rows[0].tax_amount, EXPECTED_VAT)
		and vat_rows[0].charge_type == "On Previous Row Total"
		and cint(vat_rows[0].row_id) == discount_rows[0].idx
	)


def _same(value, expected):
	return abs(flt(value) - flt(expected)) < 0.0001
