# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import cint, date_diff, flt, getdate

from hrms.payroll.doctype.salary_slip.salary_slip import (
	SalarySlip,
	get_period_factor,
	set_loan_repayment,
)
from redtra_customisation.rpayroll.overtime_helpers import (
	compute_food_allowance_counts,
	get_overtime_requests_for_period,
	submit_draft_food_allowance_for_employee_period,
)
from frappe.utils import cint

class SalarySlipOvertime(SalarySlip):
	def get_working_days_details(self, lwp=None, for_preview=0):
		super().get_working_days_details(lwp=lwp, for_preview=for_preview)
		if not for_preview:
			self._set_monthly_payment_days_denominator()

	def _set_monthly_payment_days_denominator(self):
		"""Keep payment_days from attendance but prorate against the normal monthly cycle.

		Partial joiner/relieving slips can be shorter than the usual payroll period
		(e.g. 26th-25th). Using the shortened period as total_working_days inflates
		per-day pay. Use the employee's standard cycle length instead.
		"""
		if not self.start_date or not self.end_date or not self.salary_structure:
			return

		frequency = frappe.db.get_value("Salary Structure", self.salary_structure, "payroll_frequency")
		if frequency != "Monthly":
			return

		period_days = date_diff(self.end_date, self.start_date) + 1
		if not period_days:
			return

		filters = {
			"employee": self.employee,
			"docstatus": ("!=", 2),
			"end_date": ("<", self.start_date),
		}
		if self.name:
			filters["name"] = ("!=", self.name)

		standard_cycle_days = frappe.db.get_value(
			"Salary Slip",
			filters,
			"total_working_days",
			order_by="end_date desc",
		)
		if not standard_cycle_days or flt(standard_cycle_days) <= period_days:
			return

		is_partial_joiner = self.joining_date and getdate(self.joining_date) > getdate(self.start_date)
		if self.relieving_date or is_partial_joiner:
			self.total_working_days = standard_cycle_days

	@frappe.whitelist()
	def get_emp_and_working_day_details(self):
		if self.employee and self.start_date and self.end_date:
			submit_draft_food_allowance_for_employee_period(self.employee, self.start_date, self.end_date)
		super().get_emp_and_working_day_details()
		self.set_overtime_details()

	def on_trash(self):
		super().on_trash()
		_update_payroll_entry_if_no_slips_left(self)

	def validate(self):
		super().validate()
		if self.employee and self.start_date and self.end_date:
			self.set_overtime_details()

	def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
		super().calculate_net_pay(skip_tax_breakup_computation=skip_tax_breakup_computation)
		if getattr(self, "custom_avoid_absenteeism", 0):
			# Filter out standard Absenteeism Penalty and any other Absenteeism Deduction
			self.set("deductions", [d for d in (self.deductions or []) if d.salary_component not in ("Absenteeism Penalty", "Absenteeism Deduction")])
			
			# Recalculate totals
			self.set_precision_for_component_amounts()
			self.set_net_pay()
			if not skip_tax_breakup_computation:
				self.compute_income_tax_breakup()

	def set_overtime_details(self):
		has_overtime_requests = bool(self.meta.get_field("overtime_requests"))
		has_total_overtime_hours = bool(self.meta.get_field("total_overtime_hours"))
		has_holidays_overtime_hours = bool(self.meta.get_field("holidays_overtime_hours"))
		has_food_allowance_counts = bool(self.meta.get_field("food_allowance_counts"))

		if not any([
			has_overtime_requests,
			has_total_overtime_hours,
			has_holidays_overtime_hours,
			has_food_allowance_counts,
		]):
			return

		if has_overtime_requests:
			self.set("overtime_requests", [])
		if has_total_overtime_hours:
			self.total_overtime_hours = 0
		if has_holidays_overtime_hours:
			self.holidays_overtime_hours = 0
		if has_food_allowance_counts:
			self.food_allowance_counts = 0

		start_date = getattr(self, "actual_start_date", None) or self.start_date
		end_date = getattr(self, "actual_end_date", None) or self.end_date
		overtime_list = get_overtime_requests_for_period(self.employee, start_date, end_date, only_earned=False)
		if not overtime_list:
			return
		for ot in overtime_list:
			if has_overtime_requests:
				self.append("overtime_requests", {
					"overtime_request": ot.name,
					"overtime_hours": ot.overtime_hours,
					"is_holiday": ot.is_holiday,
				})
			if has_total_overtime_hours:
				self.total_overtime_hours = flt(self.total_overtime_hours) + flt(ot.overtime_hours)
			if ot.is_holiday and has_holidays_overtime_hours:
				self.holidays_overtime_hours = flt(self.holidays_overtime_hours) + flt(ot.overtime_hours)
		payroll_settings = frappe.get_cached_value(
			"Payroll Settings", None,
			("enable_food_allowance", "food_allowance_normal_days_threshold", "food_allowance_holiday_weekend_threshold"),
			as_dict=1,
		)
		if payroll_settings and payroll_settings.enable_food_allowance and has_food_allowance_counts:
			self.food_allowance_counts = compute_food_allowance_counts(
				self.employee, start_date, end_date, overtime_list,
				normal_threshold=flt(payroll_settings.food_allowance_normal_days_threshold) or 12,
				holiday_threshold=flt(payroll_settings.food_allowance_holiday_weekend_threshold) or 0,
			)


def _update_payroll_entry_if_no_slips_left(doc):
	if not doc.get("payroll_entry"):
		return
	SalarySlip = frappe.qb.DocType("Salary Slip")
	remaining = frappe.qb.from_(SalarySlip).select(Count(SalarySlip.name)).where(
		(SalarySlip.payroll_entry == doc.payroll_entry)
		& (SalarySlip.docstatus != 2)
		& (SalarySlip.name != doc.name)
	).run()[0][0]
	if remaining == 0:
		frappe.db.set_value("Payroll Entry", doc.payroll_entry, {"salary_slips_created": 0, "status": "Draft", "docstatus": 0})
