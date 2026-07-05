# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice


class TestPurchaseInvoicePointAdjustment(FrappeTestCase):
	def setUp(self):
		self._original_gl_split = frappe.db.get_single_value(
			"Redtra Custom Setting", "enable_purchase_invoice_point_adjustment_gl_split"
		)
		self._original_adj_account = frappe.db.get_single_value(
			"Redtra Custom Setting", "purchase_invoice_point_adjustment_account"
		)

	def tearDown(self):
		frappe.db.set_single_value(
			"Redtra Custom Setting",
			{
				"enable_purchase_invoice_point_adjustment_gl_split": self._original_gl_split or 0,
				"purchase_invoice_point_adjustment_account": self._original_adj_account,
			},
		)

	def _get_adjustment_account(self, company="_Test Company"):
		account = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": "Round Off", "is_group": 0},
			"name",
		)
		if not account:
			account = frappe.db.get_value(
				"Account",
				{"company": company, "root_type": "Expense", "is_group": 0},
				"name",
			)
		return account

	def _enable_gl_split(self, account):
		frappe.db.set_single_value(
			"Redtra Custom Setting",
			{
				"enable_purchase_invoice_point_adjustment_gl_split": 1,
				"purchase_invoice_point_adjustment_account": account,
			},
		)

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

	def test_point_adjustment_gl_split_posts_separate_adjustment_account(self):
		if not frappe.db.exists("Company", "_Test Company"):
			self.skipTest("_Test Company not available")

		adjustment_account = self._get_adjustment_account()
		if not adjustment_account:
			self.skipTest("No adjustment account available in _Test Company")

		self._enable_gl_split(adjustment_account)

		pi = make_purchase_invoice(qty=1, rate=10.50, do_not_submit=True)
		item_row = pi.items[0]

		pi.append(
			"point_adjustments",
			{
				"item_row": item_row.idx,
				"purchase_invoice_item": item_row.name,
				"item_code": item_row.item_code,
				"adjustment_amount": 0.39,
				"remarks": "Point adjustment split",
			},
		)
		pi.save()

		self.assertEqual(flt(pi.items[0].net_amount), 10.50)
		self.assertEqual(flt(pi.items[0].custom_adjusted_net_amount), 10.89)
		self.assertEqual(flt(pi.grand_total), 10.89)

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
		adjustment_gle = frappe.db.get_value(
			"GL Entry",
			{
				"voucher_type": "Purchase Invoice",
				"voucher_no": pi.name,
				"account": adjustment_account,
				"is_cancelled": 0,
			},
			"debit",
		)
		creditor_gle = frappe.db.get_value(
			"GL Entry",
			{
				"voucher_type": "Purchase Invoice",
				"voucher_no": pi.name,
				"account": pi.credit_to,
				"is_cancelled": 0,
			},
			"credit",
		)

		self.assertEqual(flt(expense_gle), 10.50)
		self.assertEqual(flt(adjustment_gle), 0.39)
		self.assertEqual(flt(creditor_gle), 10.89)

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
