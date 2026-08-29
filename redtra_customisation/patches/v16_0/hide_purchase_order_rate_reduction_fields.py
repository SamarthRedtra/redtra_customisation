"""Expose only the account-backed absolute PO line discount."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.purchase_order_custom_fields import (
	PURCHASE_ORDER_CUSTOM_FIELDS,
	ensure_purchase_order_discount_field_label,
	ensure_standard_purchase_order_rate_discounts_hidden,
)


def execute():
	create_custom_fields(PURCHASE_ORDER_CUSTOM_FIELDS, ignore_validate=True)
	ensure_purchase_order_discount_field_label()
	ensure_standard_purchase_order_rate_discounts_hidden()
