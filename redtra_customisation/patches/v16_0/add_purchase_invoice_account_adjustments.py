"""Install standard account-based Purchase Invoice adjustments."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.purchase_invoice.adjustment import initialize_default_adjustment_account
from redtra_customisation.purchase_invoice.custom_fields import PURCHASE_INVOICE_ADJUSTMENT_CUSTOM_FIELDS


def execute():
	create_custom_fields(PURCHASE_INVOICE_ADJUSTMENT_CUSTOM_FIELDS, ignore_validate=True)
	initialize_default_adjustment_account()
