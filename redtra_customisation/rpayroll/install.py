# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe

_PATCHED = False


def patch_employee_checkin_for_overtime_once():
	"""Run once per process to patch employee_checkin for overtime."""
	global _PATCHED
	if _PATCHED:
		return
	_PATCHED = True
	patch_employee_checkin_for_overtime()


def patch_employee_checkin_for_overtime():
	"""Monkey-patch employee_checkin.create_or_update_attendance to call process_overtime
	when half-day attendance is updated via db.set_value (e.g. half-day to full day).
	"""
	from hrms.hr.doctype.employee_checkin import employee_checkin

	_original_create_or_update = employee_checkin.create_or_update_attendance

	def _patched_create_or_update(
		employee,
		attendance_date,
		attendance_status,
		working_hours=None,
		shift=None,
		late_entry=False,
		early_exit=False,
		in_time=None,
		out_time=None,
		overtime_type=None,
		project=None,
	):
		result = _original_create_or_update(
			employee=employee,
			attendance_date=attendance_date,
			attendance_status=attendance_status,
			working_hours=working_hours,
			shift=shift,
			late_entry=late_entry,
			early_exit=early_exit,
			in_time=in_time,
			out_time=out_time,
			overtime_type=overtime_type,
			project=project,
		)
		# When half-day was updated via db.set_value, process overtime for our flow
		if result and hasattr(result, "name"):
			try:
				from redtra_customisation.rpayroll.overtime_helpers import (
					process_overtime_for_attendance_by_name,
				)

				process_overtime_for_attendance_by_name(result.name)
			except Exception:
				pass
		return result

	employee_checkin.create_or_update_attendance = _patched_create_or_update
