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
