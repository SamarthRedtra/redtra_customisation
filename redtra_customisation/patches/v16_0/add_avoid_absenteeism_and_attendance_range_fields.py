import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from redtra_customisation.setup import get_overtime_custom_fields


def execute():
	# Create/update all custom fields in get_overtime_custom_fields
	create_custom_fields(get_overtime_custom_fields(), ignore_validate=True)
	
	# Clear metadata cache so fresh custom fields are immediately loaded
	for doctype in ("Attendance", "Payroll Settings", "Salary Slip", "Employee Attendance Tool"):
		frappe.clear_cache(doctype=doctype)
