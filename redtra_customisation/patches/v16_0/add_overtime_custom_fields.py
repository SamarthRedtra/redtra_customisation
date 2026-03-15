# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.setup import get_overtime_custom_fields


def execute():
	create_custom_fields(get_overtime_custom_fields(), ignore_validate=True)
