import frappe
from frappe.tests import UnitTestCase
from redtra_customisation.rpayroll.doctype.payroll_entry.payroll_entry import CustomPayrollEntry

class TestPayrollEntryJvPartyBypass(UnitTestCase):
	def test_payroll_entry_jv_party_bypass_hook(self):
		# Setup: Ensure we have a company and accounts
		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			company = frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Company",
				"default_currency": "AED"
			}).insert().name

		# Find a receivable/payable account
		account = frappe.db.get_value("Account", {"account_type": "Receivable", "company": company}, "name")
		if not account:
			account = frappe.get_doc({
				"doctype": "Account",
				"account_name": "Dummy Staff Receivable",
				"parent_account": frappe.db.get_value("Account", {"is_group": 1, "company": company}, "name"),
				"account_type": "Receivable",
				"company": company
			}).insert().name

		cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")
		bank_account = (
			frappe.db.get_value("Account", {"account_type": "Bank", "company": company}, "name") or 
			frappe.db.get_value("Account", {"company": company, "account_type": "Cash"}, "name")
		)

		# 1. Test without flag: should raise ValidationError
		je1 = frappe.new_doc("Journal Entry")
		je1.company = company
		je1.voucher_type = "Journal Entry"
		je1.posting_date = "2026-06-26"
		je1.append("accounts", {
			"account": account,
			"debit_in_account_currency": 1000.0,
			"cost_center": cost_center
		})
		je1.append("accounts", {
			"account": bank_account,
			"credit_in_account_currency": 1000.0,
			"cost_center": cost_center
		})

		frappe.flags.party_not_required_for_receivable_payable = False
		self.assertRaises(frappe.exceptions.ValidationError, je1.save)

		# 2. Test with flag: should save successfully
		je2 = frappe.new_doc("Journal Entry")
		je2.company = company
		je2.voucher_type = "Journal Entry"
		je2.posting_date = "2026-06-26"
		je2.append("accounts", {
			"account": account,
			"debit_in_account_currency": 1000.0,
			"cost_center": cost_center
		})
		je2.append("accounts", {
			"account": bank_account,
			"credit_in_account_currency": 1000.0,
			"cost_center": cost_center
		})

		frappe.flags.party_not_required_for_receivable_payable = True
		try:
			je2.save(ignore_permissions=True)
			self.assertEqual(je2.party_not_required, 1)
		finally:
			frappe.flags.party_not_required_for_receivable_payable = False
			frappe.db.rollback()

	def test_payroll_entry_assigns_party_to_receivable_accounts(self):
		# Create a dummy payroll entry, add mock salary component total and assert party is populated.
		company = frappe.db.get_value("Company", {}, "name")
		pe = frappe.get_doc({
			"doctype": "Payroll Entry",
			"company": company,
			"start_date": "2026-05-26",
			"end_date": "2026-06-25",
			"payroll_frequency": "Monthly",
			"exchange_rate": 1.0,
		})
		
		# Extend/wrap pe as CustomPayrollEntry
		custom_pe = CustomPayrollEntry(pe.as_dict())
		custom_pe.exchange_rate = 1.0
		custom_pe._party_receivable_payable_entries = []
		
		# Create a dummy employee
		employee = frappe.db.get_value("Employee", {}, "name")
		if not employee:
			employee = frappe.get_doc({
				"doctype": "Employee",
				"first_name": "Test Employee",
				"company": company,
				"date_of_joining": "2020-01-01",
				"gender": "Male"
			}).insert().name
			
		account = frappe.db.get_value("Account", {"account_type": "Receivable", "company": company}, "name")
		cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")
		
		# Manually add to _party_receivable_payable_entries to test set_accounting_entries_for_advance_deductions
		custom_pe._party_receivable_payable_entries.append({
			"employee": employee,
			"account": account,
			"amount": 1100.0,
			"cost_center": cost_center,
			"component_type": "deductions"
		})
		
		accounts = []
		currencies = ["AED"]
		payable_amount = 5000.0
		
		# Run set_accounting_entries_for_advance_deductions
		payable_amount = custom_pe.set_accounting_entries_for_advance_deductions(
			accounts=accounts,
			currencies=currencies,
			company_currency="AED",
			accounting_dimensions=[],
			precision=2,
			payable_amount=payable_amount
		)
		
		# Assertions
		self.assertEqual(len(accounts), 1)
		row = accounts[0]
		self.assertEqual(row["account"], account)
		self.assertEqual(row["party_type"], "Employee")
		self.assertEqual(row["party"], employee)
		self.assertEqual(row["credit_in_account_currency"], 1100.0)
		self.assertEqual(payable_amount, 5000.0 - 1100.0)
