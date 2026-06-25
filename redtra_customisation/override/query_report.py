# Copyright (c) 2026, Redtra Customisation and contributors

import frappe


@frappe.whitelist()
def get_data_for_custom_field(doctype: str, field: str, names=None):
	"""
	Custom override for get_data_for_custom_field to sanitize 'names' argument
	to prevent Pydantic typing validation exceptions when the list contains None.
	"""
	if names:
		if isinstance(names, str):
			try:
				names_list = frappe.parse_json(names)
				if isinstance(names_list, list):
					names = [str(x) for x in names_list if x is not None]
			except Exception:
				pass
		elif isinstance(names, list):
			names = [str(x) for x in names if x is not None]

	from frappe.desk.query_report import get_data_for_custom_field as original_get_data_for_custom_field
	return original_get_data_for_custom_field(doctype=doctype, field=field, names=names)
