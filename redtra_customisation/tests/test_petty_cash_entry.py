import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate


class TestPettyCashEntry(IntegrationTestCase):
	company = "_Test Company"
	cash_account = "_Test Cash - _TC"
	expense_account = "Administrative Expenses - _TC"

	def setUp(self):
		self.party = frappe.db.get_value("Employee", {"status": "Active"}, "name")
		if not all(
			frappe.db.exists(doctype, name)
			for doctype, name in (
				("Company", self.company),
				("Account", self.cash_account),
				("Account", self.expense_account),
				("Mode of Payment", "Cash"),
				("Employee", self.party),
			)
		):
			self.skipTest("ERPNext accounting test records are unavailable on this site")

	def make_entry(self, expense_account=None):
		return frappe.get_doc(
			{
				"doctype": "Petty Cash Entry",
				"company": self.company,
				"posting_date": nowdate(),
				"cash_account": self.cash_account,
				"mode_of_payment": "Cash",
				"party_type": "Employee",
				"party": self.party,
				"expense_lines": [
					{
						"expense_account": expense_account or self.expense_account,
						"amount": 125,
						"remarks": "Petty cash integration test",
					}
				],
			}
		)

	def test_submit_and_cancel_linked_payment_entry(self):
		entry = self.make_entry()
		entry.insert()
		entry.submit()

		self.assertRegex(entry.name, r"^P\d{2}\d{5}$")
		self.assertEqual(entry.status, "Submitted")
		self.assertEqual(entry.total_amount, 125)
		self.assertTrue(entry.party_name)
		self.assertTrue(entry.expense_lines[0].payment_entry)

		payment_entry = frappe.get_doc("Payment Entry", entry.expense_lines[0].payment_entry)
		self.assertEqual(payment_entry.docstatus, 1)
		self.assertEqual(payment_entry.payment_type, "Internal Transfer")
		self.assertEqual(payment_entry.paid_from, self.cash_account)
		self.assertEqual(payment_entry.paid_to, self.expense_account)
		self.assertIn(f"Paid to: {entry.party_name}", payment_entry.custom_remarks)
		self.assertEqual(entry.reload().payment_entry, payment_entry.name)
		self.assertEqual(payment_entry.custom_petty_cash_entry, entry.name)

		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Payment Entry", "voucher_no": payment_entry.name},
			pluck="custom_petty_cash_entry",
		)
		self.assertTrue(gl_entries)
		self.assertEqual(set(gl_entries), {entry.name})

		entry.cancel()
		self.assertEqual(payment_entry.reload().docstatus, 2)
		self.assertEqual(entry.reload().docstatus, 2)
		self.assertEqual(
			set(
				frappe.get_all(
					"GL Entry",
					filters={"voucher_type": "Payment Entry", "voucher_no": payment_entry.name},
					pluck="custom_petty_cash_entry",
				)
			),
			{entry.name},
		)

	def test_rejects_cash_account_as_expense_account(self):
		entry = self.make_entry(expense_account=self.cash_account)
		with self.assertRaises(frappe.ValidationError):
			entry.insert()

	def test_rejects_missing_party(self):
		entry = self.make_entry()
		entry.party = None
		with self.assertRaises(frappe.ValidationError):
			entry.insert()

	def test_print_format_and_stock_layouts_exist(self):
		self.assertTrue(frappe.db.exists("Print Format", {"name": "Petty Cash Voucher", "doc_type": "Petty Cash Entry"}))
		for name in ("Excesses in Stock", "Consumption Voucher", "Stock Transfer"):
			html = frappe.db.get_value("Print Format", name, "html")
			self.assertIn("redtra-stock-entry-layout", html)
