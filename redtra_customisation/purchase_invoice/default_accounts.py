"""Central defaults for Purchase Invoice discount and adjustment accounts."""

import frappe


DISCOUNT_ACCOUNT_FIELD = "default_purchase_invoice_discount_account"
ADJUSTMENT_ACCOUNT_FIELD = "default_purchase_invoice_adjustment_account"
DEFAULT_DISCOUNT_ACCOUNT = "3050000 - Discount Received For Cash - PIC"
DEFAULT_ADJUSTMENT_ACCOUNT = "Adjustment Account - Adjustment Account - PIC"


def get_default_discount_account(company):
	return get_default_account(DISCOUNT_ACCOUNT_FIELD, company)


def get_default_adjustment_account(company):
	return get_default_account(ADJUSTMENT_ACCOUNT_FIELD, company)


def get_default_account(fieldname, company):
	if not frappe.get_meta("Redtra Custom Setting").has_field(fieldname):
		return None
	account = frappe.db.get_single_value("Redtra Custom Setting", fieldname)
	return get_active_company_account(account, company)


def initialize_default_purchase_invoice_accounts():
	settings = frappe.get_single("Redtra Custom Setting")
	defaults = {
		DISCOUNT_ACCOUNT_FIELD: DEFAULT_DISCOUNT_ACCOUNT,
		ADJUSTMENT_ACCOUNT_FIELD: DEFAULT_ADJUSTMENT_ACCOUNT,
	}
	changed = False

	for fieldname, account in defaults.items():
		if not settings.meta.has_field(fieldname) or settings.get(fieldname):
			continue
		if frappe.db.exists("Account", account):
			settings.set(fieldname, account)
			changed = True

	if changed:
		settings.save(ignore_permissions=True)


def validate_default_purchase_invoice_accounts(settings):
	for fieldname in (DISCOUNT_ACCOUNT_FIELD, ADJUSTMENT_ACCOUNT_FIELD):
		account = settings.get(fieldname)
		if not account:
			continue
		account_details = frappe.db.get_value(
			"Account", account, ["is_group", "disabled"], as_dict=True
		)
		if not account_details or account_details.is_group or account_details.disabled:
			frappe.throw("Default Purchase Invoice accounts must be active, non-group accounts.")


def get_active_company_account(account, company):
	if not account or not company:
		return None
	return frappe.db.get_value(
		"Account",
		{"name": account, "company": company, "is_group": 0, "disabled": 0},
		"name",
	)
