"""
Install hooks for PDC Management module
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.cbe.custom_fields import CBE_LINK_CUSTOM_FIELDS
from redtra_customisation.pdc.custom_fields import PDC_CUSTOM_FIELDS
from redtra_customisation.purchase_invoice.custom_fields import (
	PURCHASE_INVOICE_POINT_ADJUSTMENT_CUSTOM_FIELDS,
)
from redtra_customisation.setup import get_sales_partner_commission_custom_fields, get_work_order_custom_fields


def create_property_setters():
	"""Create property setters for default values"""
	# Set use_multi_level_bom default to 0 (unchecked) in Work Order
	if not frappe.db.exists("Property Setter", {
		"doc_type": "Work Order",
		"field_name": "use_multi_level_bom",
		"property": "default",
	}):
		frappe.get_doc({
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": "Work Order",
			"field_name": "use_multi_level_bom",
			"property": "default",
			"value": "0",
			"property_type": "Text",
			"is_system_generated": 0,
		}).insert(ignore_permissions=True)
		frappe.db.commit()


def after_install():
	"""Create custom fields after app installation"""
	create_custom_fields(PDC_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(CBE_LINK_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(PURCHASE_INVOICE_POINT_ADJUSTMENT_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(get_sales_partner_commission_custom_fields(), ignore_validate=True)
	create_custom_fields(get_work_order_custom_fields(), ignore_validate=True)
	create_property_setters()
	frappe.msgprint("PDC Management custom fields have been created")


def after_migrate():
	"""Create custom fields after migration"""
	create_custom_fields(PDC_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(CBE_LINK_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(PURCHASE_INVOICE_POINT_ADJUSTMENT_CUSTOM_FIELDS, ignore_validate=True)
	create_custom_fields(get_sales_partner_commission_custom_fields(), ignore_validate=True)
	create_custom_fields(get_work_order_custom_fields(), ignore_validate=True)
	create_property_setters()
