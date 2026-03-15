"""
Install hooks for PDC Management module
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.pdc.custom_fields import PDC_CUSTOM_FIELDS
from redtra_customisation.setup import get_sales_partner_commission_custom_fields


def after_install():
	"""Create custom fields after app installation"""
	create_custom_fields(PDC_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(get_sales_partner_commission_custom_fields(), ignore_validate=True)
	frappe.msgprint("PDC Management custom fields have been created")


def after_migrate():
	"""Create custom fields after migration"""
	create_custom_fields(PDC_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(get_sales_partner_commission_custom_fields(), ignore_validate=True)
