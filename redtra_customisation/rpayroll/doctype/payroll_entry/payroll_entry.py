import frappe
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry


class CustomPayrollEntry(PayrollEntry):
	def get_advance_deduction(self, component_type: str, item: dict) -> str | None:
		"""Skip deductions for employee advances already fully settled."""
		employee_advance = super().get_advance_deduction(component_type, item)
		if not employee_advance:
			return None

		pending_amount = flt(
			frappe.db.get_value("Employee Advance", employee_advance, "pending_amount") or 0
		)
		if pending_amount <= 0:
			return None

		return employee_advance

	def add_advance_deduction_entry(
		self,
		item: dict,
		amount: float,
		cost_center: str,
		employee_advance: str,
	) -> None:
		"""
		Use Employee Advance account when the salary component points to a receivable/payable account.
		This prevents self-adjustment issues while posting payroll accrual entries.
		"""
		account = self.get_salary_component_account(item.salary_component)
		account_type = frappe.get_cached_value("Account", account, "account_type")

		if account_type in ("Receivable", "Payable"):
			account = frappe.db.get_value("Employee Advance", employee_advance, "advance_account") or account

		self._advance_deduction_entries.append(
			{
				"employee": item.employee,
				"account": account,
				"amount": amount,
				"cost_center": cost_center,
				"reference_type": "Employee Advance",
				"reference_name": employee_advance,
			}
		)

	def make_accrual_jv_entry(self, submitted_salary_slips):
		self._party_receivable_payable_entries = []
		super().make_accrual_jv_entry(submitted_salary_slips)

	def get_salary_component_total(
		self,
		component_type=None,
		employee_wise_accounting_enabled=False,
	):
		if not hasattr(self, "_party_receivable_payable_entries"):
			self._party_receivable_payable_entries = []

		salary_components = self.get_salary_components(component_type)
		if salary_components:
			component_dict = {}

			for item in salary_components:
				employee_cost_centers = self.get_payroll_cost_centers_for_employee(
					item.employee, item.salary_structure
				)
				employee_advance = self.get_advance_deduction(component_type, item)

				for cost_center, percentage in employee_cost_centers.items():
					amount_against_cost_center = flt(item.amount) * percentage / 100

					account = self.get_salary_component_account(item.salary_component)
					account_type = frappe.get_cached_value("Account", account, "account_type")

					if employee_advance:
						self.add_advance_deduction_entry(
							item, amount_against_cost_center, cost_center, employee_advance
						)
					elif account_type in ("Receivable", "Payable"):
						self._party_receivable_payable_entries.append({
							"employee": item.employee,
							"account": account,
							"amount": amount_against_cost_center,
							"cost_center": cost_center,
							"component_type": component_type
						})
					else:
						key = (item.salary_component, cost_center)
						component_dict[key] = component_dict.get(key, 0) + amount_against_cost_center

					if employee_wise_accounting_enabled:
						self.set_employee_based_payroll_payable_entries(
							component_type, item.employee, amount_against_cost_center
						)

			account_details = self.get_account(component_dict=component_dict)

			return account_details

	def set_accounting_entries_for_advance_deductions(
		self,
		accounts: list,
		currencies: list,
		company_currency: str,
		accounting_dimensions: list,
		precision: int,
		payable_amount: float,
	):
		if not hasattr(self, "_advance_deduction_entries"):
			self._advance_deduction_entries = []

		payable_amount = super().set_accounting_entries_for_advance_deductions(
			accounts, currencies, company_currency, accounting_dimensions, precision, payable_amount
		)

		for entry in getattr(self, "_party_receivable_payable_entries", []):
			payable_amount = self.get_accounting_entries_and_payable_amount(
				entry.get("account"),
				entry.get("cost_center"),
				entry.get("amount"),
				currencies,
				company_currency,
				payable_amount,
				accounting_dimensions,
				precision,
				entry_type="credit" if entry.get("component_type") == "deductions" else "debit",
				accounts=accounts,
				party=entry.get("employee"),
			)

		return payable_amount

