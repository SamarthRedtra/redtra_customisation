"""Default Purchase Order tax-template handling."""

import frappe


DEFAULT_COMPANY = "Pampa Industries International Corp"
DEFAULT_TAX_TEMPLATE = "UAE VAT 5% - PIC"
DEFAULT_TAX_TEMPLATE_FIELD = "custom_default_purchase_order_tax_template"


def apply_default_purchase_order_tax_template(purchase_order, method=None):
	"""Apply the configured template to a new PO with no existing tax setup."""
	if not should_apply_default_tax_template(purchase_order):
		return

	tax_template = get_default_tax_template(purchase_order.company)
	if tax_template:
		purchase_order.taxes_and_charges = tax_template


def initialize_default_purchase_order_tax_template():
	"""Initialize Pampa's default PO VAT template without touching transactions."""
	if not frappe.get_meta("Company").has_field(DEFAULT_TAX_TEMPLATE_FIELD):
		return
	if not frappe.db.exists("Company", DEFAULT_COMPANY):
		return
	if not frappe.db.exists(
		"Purchase Taxes and Charges Template",
		{"name": DEFAULT_TAX_TEMPLATE, "company": DEFAULT_COMPANY, "disabled": 0},
	):
		return

	company = frappe.get_doc("Company", DEFAULT_COMPANY)
	if not company.get(DEFAULT_TAX_TEMPLATE_FIELD):
		company.set(DEFAULT_TAX_TEMPLATE_FIELD, DEFAULT_TAX_TEMPLATE)
		company.save(ignore_permissions=True)


def should_apply_default_tax_template(purchase_order):
	return bool(
		purchase_order.is_new()
		and purchase_order.company
		and not purchase_order.get("is_return")
		and not purchase_order.get("taxes_and_charges")
		and not purchase_order.get("taxes")
	)


def get_default_tax_template(company):
	tax_template = frappe.db.get_value("Company", company, DEFAULT_TAX_TEMPLATE_FIELD)
	if not tax_template:
		return None
	return frappe.db.get_value(
		"Purchase Taxes and Charges Template",
		{"name": tax_template, "company": company, "disabled": 0},
		"name",
	)
