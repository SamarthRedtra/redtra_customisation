import frappe
from frappe.tests import UnitTestCase

from redtra_customisation.purchase_invoice.adjustment import (
	get_adjustment_total,
	get_item_adjustment_totals,
	normalize_purchase_invoice_adjustments,
)
from redtra_customisation.purchase_item_discount import reindex_tax_rows


class TestPurchaseInvoiceAdjustment(UnitTestCase):
	def test_signed_adjustment_total(self):
		rows = [
			frappe._dict(add_deduct_tax="Add", tax_amount=5),
			frappe._dict(add_deduct_tax="Deduct", tax_amount=2),
		]
		self.assertEqual(get_adjustment_total(rows), 3)

	def test_negative_amount_becomes_deduct_adjustment(self):
		invoice = frappe._dict(
			taxes=[
				frappe._dict(
					custom_is_purchase_invoice_adjustment=1,
					tax_amount=-5,
					add_deduct_tax="Add",
				)
			]
		)

		normalize_purchase_invoice_adjustments(invoice)

		self.assertEqual(invoice.taxes[0].tax_amount, 5)
		self.assertEqual(invoice.taxes[0].add_deduct_tax, "Deduct")

	def test_item_adjustments_are_summed_by_account(self):
		invoice = frappe._dict(
			company="Pampa Industries International Corp",
			items=[
				frappe._dict(custom_item_adjustment_amount=5, custom_item_adjustment_account="Account A"),
				frappe._dict(custom_item_adjustment_amount=-2, custom_item_adjustment_account="Account A"),
				frappe._dict(custom_item_adjustment_amount=3, custom_item_adjustment_account="Account B"),
			],
		)

		self.assertEqual(get_item_adjustment_totals(invoice), {"Account A": 3, "Account B": 3})

	def test_tax_rows_are_reindexed_after_generated_rows_are_rebuilt(self):
		invoice = frappe._dict(
			taxes=[
				frappe._dict(idx=1, description="VAT"),
				frappe._dict(idx=3, description="Item Discount"),
				frappe._dict(idx=3, description="Item Adjustment"),
			]
		)

		reindex_tax_rows(invoice)

		self.assertEqual([row.idx for row in invoice.taxes], [1, 2, 3])
