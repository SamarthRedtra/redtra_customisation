# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice


class TestPurchaseInvoiceRounding(FrappeTestCase):
	def test_manual_rounding_adjustment_posts_separate_gl(self):
		if not frappe.db.exists("Company", "_Test Company"):
			self.skipTest("_Test Company not available")

		round_off_account = frappe.db.get_value(
			"Account",
			{"company": "_Test Company", "account_name": "Round Off", "is_group": 0},
			"name",
		)
		if not round_off_account:
			frappe.db.set_value("Company", "_Test Company", "round_off_account", "Round Off - _TC")

		pi = make_purchase_invoice(qty=1, rate=10.50, do_not_submit=True)
		pi.disable_rounded_total = 0
		pi.rounding_adjustment = 0.39
		pi.save()

		self.assertEqual(flt(pi.items[0].net_amount), 10.50)
		self.assertEqual(flt(pi.rounding_adjustment), 0.39)
		self.assertEqual(flt(pi.rounded_total), 10.89)

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
		rounding_gle = frappe.db.get_value(
			"GL Entry",
			{
				"voucher_type": "Purchase Invoice",
				"voucher_no": pi.name,
				"account": ["in", [round_off_account, "Round Off - _TC"]],
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
		self.assertEqual(flt(rounding_gle), 0.39)
		self.assertEqual(flt(creditor_gle), 10.89)

	def test_rounding_preserved_when_disable_rounded_total_was_checked(self):
		if not frappe.db.exists("Company", "_Test Company"):
			self.skipTest("_Test Company not available")

		pi = make_purchase_invoice(qty=1, rate=10, do_not_submit=True)
		pi.disable_rounded_total = 1
		pi.rounding_adjustment = 0.20
		pi.save()

		self.assertEqual(flt(pi.rounding_adjustment), 0.20)
		self.assertEqual(flt(pi.rounded_total), 10.20)
