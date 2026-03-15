# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

from hrms.hr.doctype.shift_type.shift_type import ShiftType as ShiftTypeBase

from redtra_customisation.rpayroll.overtime_helpers import create_food_allowance_additional_salary_if_eligible


class ShiftType(ShiftTypeBase):
	@frappe.whitelist()
	def regenerate_food_allowance(self, from_date: str, to_date: str) -> dict:
		Attendance = frappe.qb.DocType("Attendance")
		attendance_list = (
			frappe.qb.from_(Attendance)
			.select(Attendance.name)
			.where(
				(Attendance.docstatus == 1)
				& (Attendance.shift == self.name)
				& (Attendance.status.isin(["Present", "Work From Home"]))
				& (Attendance.attendance_date >= getdate(from_date))
				& (Attendance.attendance_date <= getdate(to_date))
			)
		).run(pluck=True)
		created = skipped = 0
		for att_name in attendance_list:
			doc = frappe.get_doc("Attendance", att_name)
			result = create_food_allowance_additional_salary_if_eligible(doc)
			if result is not None:
				_, is_new = result
				if is_new:
					created += 1
				else:
					skipped += 1
		return {"created": created, "skipped": skipped, "processed": len(attendance_list)}
