# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def force_delete_overtime_request(name: str, delete_attendance: bool = True) -> dict:
	if not name or not frappe.db.exists("Overtime Request", name):
		frappe.throw(_("Overtime Request not found"))
	attendance_name = frappe.db.get_value("Overtime Request", name, "attendance")
	frappe.db.set_value("Overtime Request", name, "attendance", None)
	if attendance_name and frappe.db.exists("Attendance", attendance_name):
		frappe.db.set_value("Attendance", attendance_name, "overtime_request", None)
	frappe.db.commit()
	if delete_attendance and attendance_name and frappe.db.exists("Attendance", attendance_name):
		attendance = frappe.get_doc("Attendance", attendance_name)
		attendance.flags.ignore_permissions = True
		if attendance.docstatus == 1:
			attendance.cancel()
		frappe.delete_doc("Attendance", attendance_name, force=1)
	frappe.delete_doc("Overtime Request", name, force=1)
	frappe.db.commit()
	return {"deleted": name, "attendance_deleted": bool(delete_attendance and attendance_name)}


class OvertimeRequest(Document):
	pass
