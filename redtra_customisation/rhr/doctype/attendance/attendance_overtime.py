# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from redtra_customisation.rpayroll.overtime_helpers import (
	create_food_allowance_additional_salary_if_eligible,
	create_overtime_request_from_attendance,
	get_standard_hours_for_attendance,
)


def _has_overtime_fields(doc):
	return doc.meta.get_field("overtime_hours") and doc.meta.get_field("overtime_request")


def before_save_attendance(doc, method=None):
	if not _has_overtime_fields(doc):
		return
	working_hours = flt(doc.get("working_hours"), 2)
	if working_hours <= 0:
		doc.overtime_hours = 0
		return
	standard_hours = get_standard_hours_for_attendance(doc)
	doc.overtime_hours = max(0, working_hours - standard_hours)


def on_submit_attendance(doc, method=None):
	if not _has_overtime_fields(doc):
		return
	if flt(doc.get("overtime_hours"), 2) <= 0:
		working_hours = flt(doc.get("working_hours"), 2)
		if working_hours > 0:
			standard_hours = get_standard_hours_for_attendance(doc)
			doc.overtime_hours = max(0, working_hours - standard_hours)
	otr_name = create_overtime_request_from_attendance(doc)
	if otr_name:
		frappe.db.set_value("Attendance", doc.name, {"overtime_hours": doc.overtime_hours, "overtime_request": otr_name})
		frappe.db.commit()
	if doc.status in ("Present", "Work From Home"):
		create_food_allowance_additional_salary_if_eligible(doc)


def on_cancel_attendance(doc, method=None):
	from redtra_customisation.rpayroll.overtime_helpers import cancel_food_allowance_additional_salary_for_attendance

	cancel_food_allowance_additional_salary_for_attendance(doc.name)
