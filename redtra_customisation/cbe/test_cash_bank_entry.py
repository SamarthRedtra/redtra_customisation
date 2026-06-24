# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowdate


class TestCashBankEntry(IntegrationTestCase):
	def _ensure_test_company(self):
		if not frappe.db.exists("Company", "_Test Company"):
			self.skipTest("ERPNext _Test Company not available on this site")

	def _make_cbe(self, **kwargs):
		doc = frappe.new_doc("Cash Bank Entry")
		doc.company = kwargs.get("company", "_Test Company")
		doc.posting_date = kwargs.get("posting_date", nowdate())
		doc.entry_type = kwargs.get("entry_type", "Payment")
		doc.account_type = kwargs.get("account_type", "Bank")
		doc.paid_account = kwargs.get("paid_account", "_Test Bank - _TC")
		doc.settlement_mode = kwargs.get("settlement_mode", "Journal Entry")
		doc.naming_series = "CBE-.YYYY.-"
		doc.journal_naming_series = kwargs.get("journal_naming_series", "ACC-JV-.YYYY.-")
		doc.paid_account_exchange_rate = 1

		for row in kwargs.get("accounts", []):
			doc.append(
				"accounts",
				{
					"account": row["account"],
					"amount": row.get("amount", 100),
					"exchange_rate": row.get("exchange_rate", 1),
					"party_type": row.get("party_type"),
					"party": row.get("party"),
					"reference_doctype": row.get("reference_doctype"),
					"reference_name": row.get("reference_name"),
					"allocated_amount": row.get("allocated_amount"),
					"tax_rate": row.get("tax_rate"),
					"tax_account": row.get("tax_account"),
				},
			)

		account_rows = {idx + 1: row for idx, row in enumerate(doc.accounts)}
		for inv_ref in kwargs.get("invoice_references", []):
			line_no = inv_ref.get("account_row_idx", 1)
			account_row = account_rows.get(line_no)
			if not account_row:
				continue
			doc.append(
				"invoice_references",
				{
					"account_row": account_row.name,
					"account_row_idx": line_no,
					"reference_doctype": inv_ref["reference_doctype"],
					"reference_name": inv_ref["reference_name"],
					"total_amount": inv_ref.get("total_amount"),
					"outstanding_amount": inv_ref.get("outstanding_amount"),
					"allocated_amount": inv_ref.get("allocated_amount"),
				},
			)
		return doc

	def test_doctype_exists(self):
		self.assertTrue(frappe.db.exists("DocType", "Cash Bank Entry"))
		self.assertTrue(frappe.db.exists("DocType", "Cash Bank Entry Account"))

	def test_payment_creates_journal_entry(self):
		self._ensure_test_company()

		cbe = self._make_cbe(
			accounts=[
				{"account": "Administrative Expenses - _TC", "amount": 500},
				{"account": "Office Rent - _TC", "amount": 300},
			]
		)
		cbe.insert()
		cbe.submit()

		self.assertEqual(cbe.status, "Submitted")
		self.assertTrue(cbe.journal_entry)
		self.assertFalse(cbe.payment_entry)

		je = frappe.get_doc("Journal Entry", cbe.journal_entry)
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(je.voucher_type, "Bank Entry")
		self.assertEqual(je.naming_series, cbe.journal_naming_series)
		if hasattr(je, "custom_cash_bank_entry"):
			self.assertFalse(je.custom_cash_bank_entry)

		total_debit = sum(flt(r.debit) for r in je.accounts)
		total_credit = sum(flt(r.credit) for r in je.accounts)
		self.assertAlmostEqual(total_debit, total_credit, places=2)
		self.assertAlmostEqual(flt(cbe.amount), 800, places=2)

	def test_receipt_creates_cash_journal_entry(self):
		self._ensure_test_company()

		cbe = self._make_cbe(
			entry_type="Receipt",
			account_type="Cash",
			paid_account="_Test Cash - _TC",
			accounts=[{"account": "Sales - _TC", "amount": 250}],
		)
		cbe.insert()
		cbe.submit()

		je = frappe.get_doc("Journal Entry", cbe.journal_entry)
		self.assertEqual(je.voucher_type, "Cash Entry")
		bank_line = [r for r in je.accounts if r.account == "_Test Cash - _TC"][0]
		self.assertGreater(flt(bank_line.debit), 0)

	def test_cancel_cancels_journal_entry(self):
		self._ensure_test_company()

		cbe = self._make_cbe(
			accounts=[{"account": "Administrative Expenses - _TC", "amount": 100}]
		)
		cbe.insert()
		cbe.submit()
		je_name = cbe.journal_entry

		cbe.cancel()
		self.assertEqual(cbe.status, "Cancelled")
		self.assertEqual(frappe.db.get_value("Journal Entry", je_name, "docstatus"), 2)

	def test_line_tax_expands_to_je_tax_line(self):
		self._ensure_test_company()

		tax_account = "VAT - _TC"
		if not frappe.db.exists("Account", tax_account):
			self.skipTest("VAT - _TC account not available")

		cbe = self._make_cbe(
			accounts=[
				{
					"account": "Administrative Expenses - _TC",
					"amount": 118,
					"tax_rate": 18,
					"tax_account": tax_account,
				}
			]
		)
		cbe.insert()
		cbe.submit()

		je = frappe.get_doc("Journal Entry", cbe.journal_entry)
		tax_lines = [r for r in je.accounts if r.account == tax_account]
		self.assertTrue(tax_lines)
		self.assertAlmostEqual(flt(tax_lines[0].debit), 18, places=2)

	def test_invoice_reference_on_receipt(self):
		self._ensure_test_company()

		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

		si = create_sales_invoice(
			customer="_Test Customer",
			rate=400,
			qty=1,
			do_not_submit=True,
		)
		si.insert()
		si.submit()

		outstanding_before = flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))

		cbe = self._make_cbe(
			entry_type="Receipt",
			account_type="Cash",
			paid_account="_Test Cash - _TC",
			accounts=[
				{
					"account": "Debtors - _TC",
					"amount": 400,
					"party_type": "Customer",
					"party": "_Test Customer",
					"reference_doctype": "Sales Invoice",
					"reference_name": si.name,
					"allocated_amount": 400,
				}
			],
		)
		cbe.insert()
		cbe.submit()

		outstanding_after = flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))
		self.assertAlmostEqual(outstanding_before - outstanding_after, 400, places=2)

		je = frappe.get_doc("Journal Entry", cbe.journal_entry)
		ref_line = [
			r
			for r in je.accounts
			if r.reference_type == "Sales Invoice" and r.reference_name == si.name
		]
		self.assertTrue(ref_line)

	def test_pe_settlement_mode_single_party(self):
		self._ensure_test_company()

		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

		si = create_sales_invoice(
			customer="_Test Customer",
			rate=200,
			qty=1,
			do_not_submit=True,
		)
		si.insert()
		si.submit()

		cbe = self._make_cbe(
			entry_type="Receipt",
			account_type="Bank",
			paid_account="_Test Bank - _TC",
			settlement_mode="Payment Entry",
			accounts=[
				{
					"account": "Debtors - _TC",
					"amount": 200,
					"party_type": "Customer",
					"party": "_Test Customer",
					"reference_doctype": "Sales Invoice",
					"reference_name": si.name,
					"allocated_amount": 200,
				}
			],
		)
		cbe.mode_of_payment = "_Test Mode of Payment"
		cbe.insert()
		cbe.submit()

		self.assertTrue(cbe.payment_entry)
		self.assertFalse(cbe.journal_entry)
		pe = frappe.get_doc("Payment Entry", cbe.payment_entry)
		self.assertEqual(pe.docstatus, 1)
		if hasattr(pe, "custom_cash_bank_entry"):
			self.assertFalse(pe.custom_cash_bank_entry)

	def test_pe_mode_blocked_for_mixed_lines(self):
		self._ensure_test_company()

		cbe = self._make_cbe(
			settlement_mode="Payment Entry",
			accounts=[
				{
					"account": "Debtors - _TC",
					"amount": 100,
					"party_type": "Customer",
					"party": "_Test Customer",
				},
				{"account": "Sales - _TC", "amount": 50},
			],
		)
		cbe.mode_of_payment = "_Test Mode of Payment"
		cbe.insert()
		with self.assertRaises(frappe.ValidationError):
			cbe.submit()

	def test_multi_invoice_pe_from_single_account_row(self):
		self._ensure_test_company()

		from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice

		si1 = create_sales_invoice(customer="_Test Customer", rate=100, qty=1, do_not_submit=True)
		si1.insert()
		si1.submit()
		si2 = create_sales_invoice(customer="_Test Customer", rate=150, qty=1, do_not_submit=True)
		si2.insert()
		si2.submit()

		cbe = self._make_cbe(
			entry_type="Receipt",
			account_type="Bank",
			paid_account="_Test Bank - _TC",
			settlement_mode="Payment Entry",
			accounts=[
				{
					"account": "Debtors - _TC",
					"amount": 250,
					"party_type": "Customer",
					"party": "_Test Customer",
				}
			],
			invoice_references=[
				{
					"account_row_idx": 1,
					"reference_doctype": "Sales Invoice",
					"reference_name": si1.name,
					"total_amount": si1.grand_total,
					"outstanding_amount": si1.outstanding_amount,
					"allocated_amount": 100,
				},
				{
					"account_row_idx": 1,
					"reference_doctype": "Sales Invoice",
					"reference_name": si2.name,
					"total_amount": si2.grand_total,
					"outstanding_amount": si2.outstanding_amount,
					"allocated_amount": 150,
				},
			],
		)
		cbe.mode_of_payment = "_Test Mode of Payment"
		cbe.insert()
		cbe.submit()

		pe = frappe.get_doc("Payment Entry", cbe.payment_entry)
		self.assertEqual(pe.docstatus, 1)
		self.assertEqual(len(pe.references), 2)
		ref_names = {ref.reference_name for ref in pe.references}
		self.assertEqual(ref_names, {si1.name, si2.name})

	def test_multi_invoice_pdc_from_single_account_row(self):
		self._ensure_test_company()

		from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice

		pi1 = make_purchase_invoice(qty=1, rate=80, do_not_submit=True)
		pi1.insert()
		pi1.submit()
		pi2 = make_purchase_invoice(qty=1, rate=120, do_not_submit=True)
		pi2.insert()
		pi2.submit()

		cbe = self._make_cbe(
			entry_type="Payment",
			account_type="Bank",
			paid_account="_Test Bank - _TC",
			settlement_mode="Post Dated Cheque",
			accounts=[
				{
					"account": "Creditors - _TC",
					"amount": 200,
					"party_type": "Supplier",
					"party": pi1.supplier,
				}
			],
			invoice_references=[
				{
					"account_row_idx": 1,
					"reference_doctype": "Purchase Invoice",
					"reference_name": pi1.name,
					"total_amount": pi1.grand_total,
					"outstanding_amount": pi1.outstanding_amount,
					"allocated_amount": 80,
				},
				{
					"account_row_idx": 1,
					"reference_doctype": "Purchase Invoice",
					"reference_name": pi2.name,
					"total_amount": pi2.grand_total,
					"outstanding_amount": pi2.outstanding_amount,
					"allocated_amount": 120,
				},
			],
		)
		cbe.mode_of_payment = "_Test Mode of Payment"
		cbe.reference = "CHQ-001"
		cbe.reference_date = nowdate()
		cbe.insert()
		cbe.submit()

		pdc = frappe.get_doc("Post Dated Cheques", cbe.post_dated_cheque)
		self.assertEqual(pdc.docstatus, 1)
		self.assertEqual(len(pdc.invoice_references), 2)
		ref_names = {ref.reference_name for ref in pdc.invoice_references}
		self.assertEqual(ref_names, {pi1.name, pi2.name})
