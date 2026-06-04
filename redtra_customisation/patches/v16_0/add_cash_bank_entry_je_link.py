import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.cbe.custom_fields import CBE_LINK_CUSTOM_FIELDS


def execute():
	create_custom_fields(CBE_LINK_CUSTOM_FIELDS, ignore_validate=True)
