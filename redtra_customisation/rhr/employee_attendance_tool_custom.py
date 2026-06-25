# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import datetime
import json
import frappe
from frappe.utils import getdate, add_days, date_diff


@frappe.whitelist()
def mark_employee_attendance(
	employee_list: list | str,
	status: str,
	date: str | datetime.date,
	leave_type: str | None = None,
	company: str | None = None,
	late_entry: int | None = None,
	early_exit: int | None = None,
	shift: str | None = None,
	project: str | None = None,
	mark_half_day: bool | None = False,
	half_day_status: str | None = None,
	half_day_employee_list: list | str | None = None,
	custom_from_date: str | None = None,
	custom_to_date: str | None = None,
) -> None:
	dates = []
	if custom_from_date and custom_to_date:
		start = getdate(custom_from_date)
		end = getdate(custom_to_date)
		diff = date_diff(end, start)
		if diff >= 0:
			for i in range(diff + 1):
				dates.append(add_days(start, i))
	else:
		dates.append(getdate(date))

	if isinstance(employee_list, str):
		employee_list = json.loads(employee_list)

	for d in dates:
		# Mark full day attendance
		for employee in employee_list:
			# Skip if attendance already exists for this date and employee to avoid duplicate error
			if frappe.db.exists("Attendance", {"employee": employee, "attendance_date": d, "docstatus": ["<", 2]}):
				continue

			attendance = frappe.get_doc(
				dict(
					doctype="Attendance",
					employee=employee,
					attendance_date=d,
					status=status,
					leave_type=leave_type if status == "On Leave" else None,
					late_entry=late_entry,
					early_exit=early_exit,
					shift=shift,
					project=project,
				)
			)
			attendance.insert()
			attendance.submit()

		# Mark half day attendance
		if mark_half_day and half_day_employee_list:
			if isinstance(half_day_employee_list, str):
				half_day_employee_list = json.loads(half_day_employee_list)
			
			Attendance = frappe.qb.DocType("Attendance")
			for employee in half_day_employee_list:
				if frappe.db.exists("Attendance", {"employee": employee, "attendance_date": d, "docstatus": ["<", 2]}):
					frappe.qb.update(Attendance).where(
						(Attendance.employee == employee) & (Attendance.attendance_date == d)
					).set(Attendance.half_day_status, half_day_status).set(Attendance.shift, shift).set(
						Attendance.late_entry, late_entry
					).set(Attendance.early_exit, early_exit).set(Attendance.project, project).set(Attendance.modify_half_day_status, 0).run()
