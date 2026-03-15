# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import flt

from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from redtra_customisation.rpayroll.overtime_helpers import (
	compute_food_allowance_counts,
	get_overtime_requests_for_period,
	submit_draft_food_allowance_for_employee_period,
)


class SalarySlipOvertime(SalarySlip):
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
