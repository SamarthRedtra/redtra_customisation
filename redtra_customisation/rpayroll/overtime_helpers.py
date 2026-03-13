# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.utils import add_days, flt, getdate, get_time, time_diff_in_hours

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from hrms.utils.holiday_list import get_holiday_dates_between


def is_auto_overtime_request_enabled() -> bool:
	return bool(frappe.db.get_single_value("Payroll Settings", "auto_create_overtime_request"))


def get_standard_hours_for_attendance(attendance_doc) -> float:
	if attendance_doc.get("shift"):
		shift = frappe.get_cached_doc("Shift Type", attendance_doc.shift)
		start = get_time(shift.start_time)
		end = get_time(shift.end_time)
		shift_start = datetime.combine(getdate(), start)
		if start < end:
			shift_end = datetime.combine(getdate(), end)
		else:
			shift_end = datetime.combine(add_days(getdate(), 1), end)
		return flt(time_diff_in_hours(shift_end, shift_start), 2)
	standard_hours = frappe.db.get_single_value("HR Settings", "standard_working_hours") or 8
	return flt(standard_hours, 2)


def process_overtime_for_attendance_by_name(attendance_name: str) -> str | None:
	if not is_auto_overtime_request_enabled():
		return None
	try:
		doc = frappe.get_doc("Attendance", attendance_name)
		if not doc.meta.get_field("overtime_hours"):
			return None
		working_hours = flt(doc.get("working_hours"), 2)
		if working_hours <= 0:
			return None
		standard_hours = get_standard_hours_for_attendance(doc)
		doc.overtime_hours = max(0, working_hours - standard_hours)
		otr_name = create_overtime_request_from_attendance(doc)
		if otr_name:
			frappe.db.set_value(
				"Attendance", attendance_name,
				{"overtime_hours": doc.overtime_hours, "overtime_request": otr_name}
			)
		if doc.docstatus == 1 and doc.status in ("Present", "Work From Home"):
			create_food_allowance_additional_salary_if_eligible(doc)
		return otr_name
	except Exception:
		return None


def create_overtime_request_from_attendance(attendance_doc) -> str | None:
	if not is_auto_overtime_request_enabled():
		return None
	overtime_hours = flt(attendance_doc.get("overtime_hours"), 2)
	if overtime_hours <= 0:
		return None
	if attendance_doc.status not in ("Present", "Work From Home"):
		return None
	if attendance_doc.get("overtime_request"):
		return attendance_doc.overtime_request

	holiday_list = get_holiday_list_for_employee(attendance_doc.employee, raise_exception=False)
	is_holiday = 0
	if holiday_list:
		holiday_dates = get_holiday_dates_between(
			holiday_list, attendance_doc.attendance_date, attendance_doc.attendance_date
		)
		if getdate(attendance_doc.attendance_date) in holiday_dates:
			is_holiday = 1

	from_time = get_time(attendance_doc.in_time) if attendance_doc.get("in_time") else None
	till_time = get_time(attendance_doc.out_time) if attendance_doc.get("out_time") else None

	otr = frappe.get_doc({
		"doctype": "Overtime Request",
		"employee": attendance_doc.employee,
		"attendance_date": attendance_doc.attendance_date,
		"from_time": from_time,
		"till_time": till_time,
		"overtime_hours": overtime_hours,
		"company": attendance_doc.company,
		"overtime_status": "Draft",
		"is_holiday": is_holiday,
		"attendance": attendance_doc.name,
	})
	otr.insert(ignore_permissions=True)
	return otr.name


def get_overtime_requests_for_period(employee, start_date, end_date, only_earned=True):
	OvertimeRequest = frappe.qb.DocType("Overtime Request")
	query = (
		frappe.qb.from_(OvertimeRequest)
		.select(
			OvertimeRequest.name,
			OvertimeRequest.overtime_hours,
			OvertimeRequest.is_holiday,
			OvertimeRequest.attendance_date,
		)
		.where(
			(OvertimeRequest.employee == employee)
			& (OvertimeRequest.attendance_date >= start_date)
			& (OvertimeRequest.attendance_date <= end_date)
			& (OvertimeRequest.overtime_status == "Approved")
		)
	)
	if only_earned:
		query = query.where(OvertimeRequest.is_earned == 1)
	return query.run(as_dict=True)


def create_food_allowance_additional_salary_if_eligible(attendance_doc) -> tuple[str, bool] | None:
	# Skip when HRMS flow handles this attendance (overtime_type set from Shift Type allow_overtime)
	if attendance_doc.get("overtime_type"):
		return None

	payroll_settings = frappe.get_cached_value(
		"Payroll Settings", None,
		("enable_food_allowance", "food_allowance_salary_component", "food_allowance_amount",
		 "food_allowance_normal_days_threshold", "food_allowance_holiday_weekend_threshold"),
		as_dict=1,
	)
	if not (payroll_settings and payroll_settings.enable_food_allowance):
		return None
	if not payroll_settings.food_allowance_salary_component:
		return None
	amount = flt(payroll_settings.food_allowance_amount, 2)
	if amount <= 0:
		return None

	working_hours = flt(attendance_doc.get("working_hours"), 2)
	if working_hours <= 0:
		return None
	standard_hours = get_standard_hours_for_attendance(attendance_doc)
	total_hours = standard_hours + flt(attendance_doc.get("overtime_hours"), 2)

	att_date = getdate(attendance_doc.attendance_date)
	holiday_list = get_holiday_list_for_employee(attendance_doc.employee, raise_exception=False)
	is_holiday = False
	if holiday_list:
		holiday_dates = get_holiday_dates_between(holiday_list, att_date, att_date)
		is_holiday = att_date in holiday_dates

	normal_threshold = flt(payroll_settings.food_allowance_normal_days_threshold) or 12
	holiday_threshold = flt(payroll_settings.food_allowance_holiday_weekend_threshold) or 0

	qualifies = holiday_threshold == 0 or total_hours > holiday_threshold if is_holiday else total_hours > normal_threshold
	if not qualifies:
		return None

	existing = frappe.db.exists("Additional Salary", {
		"employee": attendance_doc.employee,
		"salary_component": payroll_settings.food_allowance_salary_component,
		"payroll_date": att_date,
		"docstatus": ["!=", 2],
	})
	if existing:
		return (existing, False)

	company = attendance_doc.company
	currency = frappe.get_cached_value("Company", company, "default_currency") or "INR"
	additional_salary = frappe.get_doc({
		"doctype": "Additional Salary",
		"employee": attendance_doc.employee,
		"company": company,
		"salary_component": payroll_settings.food_allowance_salary_component,
		"payroll_date": att_date,
		"amount": amount,
		"currency": currency,
		"ref_doctype": "Attendance",
		"ref_docname": attendance_doc.name,
	})
	additional_salary.insert(ignore_permissions=True)
	return (additional_salary.name, True)


def submit_draft_food_allowance_for_employee_period(employee, start_date, end_date):
	payroll_settings = frappe.get_cached_value(
		"Payroll Settings", None,
		("enable_food_allowance", "food_allowance_salary_component"),
		as_dict=1,
	)
	if not (payroll_settings and payroll_settings.enable_food_allowance and payroll_settings.food_allowance_salary_component):
		return

	AdditionalSalary = frappe.qb.DocType("Additional Salary")
	drafts = (
		frappe.qb.from_(AdditionalSalary)
		.select(AdditionalSalary.name)
		.where(
			(AdditionalSalary.employee == employee)
			& (AdditionalSalary.salary_component == payroll_settings.food_allowance_salary_component)
			& (AdditionalSalary.docstatus == 0)
			& (AdditionalSalary.payroll_date >= getdate(start_date))
			& (AdditionalSalary.payroll_date <= getdate(end_date))
		)
	).run(pluck=True)

	for name in drafts:
		frappe.get_doc("Additional Salary", name).submit()


def cancel_food_allowance_additional_salary_for_attendance(attendance_name):
	additional_salaries = frappe.get_all(
		"Additional Salary",
		filters={"ref_doctype": "Attendance", "ref_docname": attendance_name, "docstatus": ["!=", 2]},
		pluck="name",
	)
	for name in additional_salaries:
		doc = frappe.get_doc("Additional Salary", name)
		if doc.docstatus == 1:
			doc.cancel()
		else:
			doc.delete()


def compute_food_allowance_counts(employee, start_date, end_date, overtime_requests, normal_threshold=12, holiday_threshold=0):
	if not overtime_requests:
		return 0
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	holiday_dates = set(get_holiday_dates_between(holiday_list, start_date, end_date)) if holiday_list else set()
	standard_hours = flt(frappe.db.get_single_value("HR Settings", "standard_working_hours") or 8, 2)
	count = 0
	processed_dates = set()
	for ot in overtime_requests:
		dt = getdate(ot.attendance_date)
		if dt in processed_dates:
			continue
		processed_dates.add(dt)
		total_hours = standard_hours + flt(ot.overtime_hours, 2)
		is_holiday_or_weekend = dt in holiday_dates
		if is_holiday_or_weekend:
			if holiday_threshold == 0 or total_hours > holiday_threshold:
				count += 1
		else:
			if total_hours > normal_threshold:
				count += 1
	return count
