"""Ensure the paid-invoice commission flag exists before its hooks run."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.setup import get_sales_partner_commission_custom_fields


def execute():
	create_custom_fields(get_sales_partner_commission_custom_fields(), ignore_validate=True)
