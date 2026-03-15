import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.setup import get_overtime_custom_fields


def execute():
	# Keep this as a new patch so migrated sites apply the Salary Slip overtime fields again.
	create_custom_fields(get_overtime_custom_fields(), ignore_validate=True)

	# Clear cached meta so the freshly added fields are available immediately after migrate.
	for doctype in ("Attendance", "Payroll Settings", "Salary Slip"):
		frappe.clear_cache(doctype=doctype)
