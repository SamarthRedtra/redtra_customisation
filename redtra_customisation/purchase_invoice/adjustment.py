"""Standard Purchase Invoice tax-row adjustments."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from redtra_customisation.purchase_item_discount import reindex_tax_rows
from redtra_customisation.purchase_invoice.default_accounts import (
	get_default_adjustment_account as get_setting_default_adjustment_account,
)


ADJUSTMENT_MARKER = "custom_is_purchase_invoice_adjustment"
ITEM_ADJUSTMENT_MARKER = "custom_is_purchase_invoice_item_adjustment"
ITEM_ADJUSTMENT_AMOUNT = "custom_item_adjustment_amount"
ITEM_ADJUSTMENT_ACCOUNT = "custom_item_adjustment_account"
ITEM_DISCOUNT_MARKER = "custom_is_purchase_item_discount"
ADJUSTED_TAX_BASE_MARKER = "custom_uses_adjusted_tax_base"
ORIGINAL_CHARGE_TYPE = "custom_original_charge_type"
ORIGINAL_ROW_ID = "custom_original_row_id"
DEFAULT_COMPANY = "Pampa Industries International Corp"
DEFAULT_ACCOUNT = "Adjustment Account - Adjustment Account - PIC"


def validate_purchase_invoice_adjustments(invoice):
	"""Validate marked standard tax rows and update the visible adjustment total."""
	adjustment_rows = get_adjustment_rows(invoice)
	if not adjustment_rows:
		set_adjustment_total(invoice, 0)
		return

	validate_adjustments_precede_tax_rows(invoice)
	for row in adjustment_rows:
		validate_adjustment_row(invoice, row)
	set_adjustment_total(invoice, get_adjustment_total(adjustment_rows))


def normalize_purchase_invoice_adjustments(invoice):
	"""Treat a negative entered amount as a standard Deduct adjustment."""
	for row in get_adjustment_rows(invoice):
		if flt(row.tax_amount) < 0:
			row.tax_amount = abs(flt(row.tax_amount))
			row.add_deduct_tax = "Deduct"


def sync_item_adjustments(invoice):
	"""Turn signed item adjustments into standard account-aware tax rows."""
	if not _has_item_adjustment_fields():
		return

	invoice.set(
		"taxes",
		[row for row in invoice.get("taxes") if not cint(row.get(ITEM_ADJUSTMENT_MARKER))],
	)

	for (account, cost_center), amount in get_item_adjustment_totals_by_cost_center(invoice).items():
		if not flt(amount):
			continue
		invoice.append(
			"taxes",
			{
				"charge_type": "Actual",
				"category": "Total",
				"add_deduct_tax": "Add" if amount > 0 else "Deduct",
				"account_head": account,
				"cost_center": cost_center,
				"description": _("Item Adjustments"),
				"tax_amount": abs(flt(amount)),
				"included_in_print_rate": 0,
				"included_in_paid_amount": 0,
				ADJUSTMENT_MARKER: 1,
				ITEM_ADJUSTMENT_MARKER: 1,
			},
		)
	reindex_tax_rows(invoice)


def configure_adjusted_tax_base(invoice):
	"""Make percentage taxes calculate after account-backed adjustments and discounts."""
	taxable_base_rows = get_taxable_base_rows(invoice)
	if not taxable_base_rows:
		restore_original_tax_base(invoice)
		reindex_tax_rows(invoice)
		return

	move_taxable_base_rows_first(invoice, taxable_base_rows)
	reindex_tax_rows(invoice)
	last_base_row = get_taxable_base_rows(invoice)[-1]

	for row in invoice.get("taxes"):
		if is_taxable_base_row(row):
			continue
		if row.charge_type == "On Net Total":
			remember_original_tax_base(row)
			row.charge_type = "On Previous Row Total"
			row.row_id = last_base_row.idx
			row.set(ADJUSTED_TAX_BASE_MARKER, 1)
		elif cint(row.get(ADJUSTED_TAX_BASE_MARKER)):
			row.row_id = last_base_row.idx


def restore_original_tax_base(invoice):
	"""Restore standard tax settings once no taxable base adjustment remains."""
	for row in invoice.get("taxes"):
		if not cint(row.get(ADJUSTED_TAX_BASE_MARKER)):
			continue
		row.charge_type = row.get(ORIGINAL_CHARGE_TYPE) or "On Net Total"
		row.row_id = row.get(ORIGINAL_ROW_ID) or None
		row.set(ADJUSTED_TAX_BASE_MARKER, 0)
		row.set(ORIGINAL_CHARGE_TYPE, None)
		row.set(ORIGINAL_ROW_ID, None)


def initialize_default_adjustment_account():
	"""Set the requested Pampa default once, without creating an Account."""
	if not frappe.get_meta("Company").has_field("custom_purchase_invoice_adjustment_account"):
		return
	if not frappe.db.exists("Company", DEFAULT_COMPANY):
		return
	if not frappe.db.exists("Account", {"name": DEFAULT_ACCOUNT, "company": DEFAULT_COMPANY}):
		return

	company = frappe.get_doc("Company", DEFAULT_COMPANY)
	if company.custom_purchase_invoice_adjustment_account:
		return
	company.custom_purchase_invoice_adjustment_account = DEFAULT_ACCOUNT
	company.save(ignore_permissions=True)


def get_adjustment_rows(invoice):
	if not frappe.get_meta("Purchase Taxes and Charges").has_field(ADJUSTMENT_MARKER):
		return []
	return [row for row in invoice.get("taxes") if cint(row.get(ADJUSTMENT_MARKER))]


def get_taxable_base_rows(invoice):
	return [row for row in invoice.get("taxes") if is_taxable_base_row(row)]


def is_taxable_base_row(row):
	return cint(row.get(ADJUSTMENT_MARKER)) or cint(row.get(ITEM_DISCOUNT_MARKER))


def get_item_adjustment_totals(invoice):
	"""Return signed item adjustments grouped by their posting account."""
	totals = {}
	for (account, _cost_center), amount in get_item_adjustment_totals_by_cost_center(invoice).items():
		totals[account] = flt(totals.get(account)) + amount
	return totals


def get_item_adjustment_totals_by_cost_center(invoice):
	"""Return signed item adjustments grouped by posting account and Cost Center."""
	default_account = get_default_adjustment_account(invoice.company)
	totals = {}
	for item in invoice.get("items"):
		amount = flt(item.get(ITEM_ADJUSTMENT_AMOUNT))
		if not amount:
			continue
		account = item.get(ITEM_ADJUSTMENT_ACCOUNT) or default_account
		item.set(ITEM_ADJUSTMENT_ACCOUNT, account)
		cost_center = item.cost_center or get_default_cost_center(invoice)
		key = (account, cost_center)
		totals[key] = flt(totals.get(key)) + amount
	return totals


def validate_adjustments_precede_tax_rows(invoice):
	seen_tax_row = False
	for row in invoice.get("taxes"):
		if is_taxable_base_row(row):
			if seen_tax_row:
				frappe.throw(_("Purchase Invoice adjustments and item discounts must precede tax rows."))
		else:
			seen_tax_row = True


def remember_original_tax_base(row):
	if cint(row.get(ADJUSTED_TAX_BASE_MARKER)):
		return
	row.set(ORIGINAL_CHARGE_TYPE, row.charge_type)
	row.set(ORIGINAL_ROW_ID, row.row_id)


def move_taxable_base_rows_first(invoice, taxable_base_rows):
	taxable_row_names = {row.name for row in taxable_base_rows if row.name}
	taxable_row_ids = {id(row) for row in taxable_base_rows}
	other_rows = [
		row
		for row in invoice.get("taxes")
		if row.name not in taxable_row_names and id(row) not in taxable_row_ids
	]
	invoice.set("taxes", taxable_base_rows + other_rows)


def validate_adjustment_row(invoice, row):
	if row.charge_type != "Actual" or row.category != "Total":
		frappe.throw(_("Row {0}: Adjustment must use Actual type and Total category.").format(row.idx))
	if row.add_deduct_tax not in ("Add", "Deduct"):
		frappe.throw(_("Row {0}: Adjustment must be Add or Deduct.").format(row.idx))
	if cint(row.included_in_print_rate) or cint(row.included_in_paid_amount):
		frappe.throw(_("Row {0}: Adjustment cannot be included in tax or paid amount.").format(row.idx))
	if flt(row.tax_amount) <= 0:
		frappe.throw(_("Row {0}: Adjustment Amount must be greater than zero.").format(row.idx))
	validate_adjustment_account(invoice, row)
	row.cost_center = row.cost_center or get_default_cost_center(invoice)
	if not row.cost_center:
		frappe.throw(_("Row {0}: Cost Center is required for the Adjustment Account.").format(row.idx))


def validate_adjustment_account(invoice, row):
	if not row.account_head:
		frappe.throw(_("Row {0}: Adjustment Account is required.").format(row.idx))

	account = frappe.db.get_value(
		"Account", row.account_head, ["company", "is_group", "disabled"], as_dict=True
	)
	if not account or account.company != invoice.company or cint(account.is_group) or cint(account.disabled):
		frappe.throw(_("Row {0}: Adjustment Account must be active, non-group, and in this Company.").format(row.idx))


def get_adjustment_total(rows):
	return sum(
		flt(row.tax_amount)
		* (-1 if row.add_deduct_tax == "Deduct" else 1)
		for row in rows
	)


def set_adjustment_total(invoice, amount):
	if invoice.meta.has_field("custom_adjustment_total"):
		invoice.custom_adjustment_total = flt(amount, invoice.precision("custom_adjustment_total"))


def get_default_adjustment_account(company):
	if account := get_setting_default_adjustment_account(company):
		return account
	if not company or not frappe.get_meta("Company").has_field("custom_purchase_invoice_adjustment_account"):
		return None
	return frappe.db.get_value("Company", company, "custom_purchase_invoice_adjustment_account")


def get_default_cost_center(invoice):
	return next((item.cost_center for item in invoice.get("items") if item.cost_center), None) or invoice.get(
		"cost_center"
	) or frappe.db.get_value("Company", invoice.company, "cost_center")


def _has_item_adjustment_fields():
	return (
		frappe.get_meta("Purchase Invoice Item").has_field(ITEM_ADJUSTMENT_AMOUNT)
		and frappe.get_meta("Purchase Taxes and Charges").has_field(ITEM_ADJUSTMENT_MARKER)
	)
