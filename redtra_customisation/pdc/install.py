"""
Install hooks for PDC Management module
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.pdc.custom_fields import PDC_CUSTOM_FIELDS


def after_install():
	"""Create custom fields after app installation"""
	create_custom_fields(PDC_CUSTOM_FIELDS, ignore_validate=True)
	frappe.msgprint("PDC Management custom fields have been created")


def after_migrate():
	"""Create custom fields after migration"""
	create_custom_fields(PDC_CUSTOM_FIELDS, ignore_validate=True)
