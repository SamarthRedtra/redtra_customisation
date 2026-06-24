# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice


class TestPurchaseInvoicePointAdjustment(FrappeTestCase):
	def test_point_adjustment_updates_totals_and_gl(self):
		if not frappe.db.exists("Company", "_Test Company"):
			self.skipTest("_Test Company not available")

		pi = make_purchase_invoice(qty=1, rate=4.98, do_not_submit=True)
		item_row = pi.items[0]

		pi.append(
			"point_adjustments",
			{
				"item_row": item_row.idx,
				"purchase_invoice_item": item_row.name,
				"item_code": item_row.item_code,
				"adjustment_amount": 0.48,
				"remarks": "Point adjustment",
			},
		)
		pi.save()

		self.assertEqual(flt(pi.custom_total_point_adjustment), 0.48)
		self.assertEqual(flt(pi.items[0].custom_point_adjustment_total), 0.48)
		self.assertEqual(flt(pi.items[0].net_amount), 5.46)

		pi.submit()
		expense_gle = frappe.db.get_value(
			"GL Entry",
			{
				"voucher_type": "Purchase Invoice",
				"voucher_no": pi.name,
				"account": pi.items[0].expense_account,
				"is_cancelled": 0,
			},
			"debit",
		)
		self.assertEqual(flt(expense_gle), flt(pi.items[0].base_net_amount))

	def test_multiple_point_adjustments_on_same_line(self):
		if not frappe.db.exists("Company", "_Test Company"):
			self.skipTest("_Test Company not available")

		pi = make_purchase_invoice(qty=1, rate=10, do_not_submit=True)
		item_row = pi.items[0]

		for amount in (0.25, -0.10, 0.05):
			pi.append(
				"point_adjustments",
				{
					"item_row": item_row.idx,
					"purchase_invoice_item": item_row.name,
					"item_code": item_row.item_code,
					"adjustment_amount": amount,
				},
			)

		pi.save()
		self.assertEqual(flt(pi.custom_total_point_adjustment), 0.20)
		self.assertEqual(flt(pi.items[0].net_amount), 10.20)
