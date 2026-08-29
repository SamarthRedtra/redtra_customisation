"""Account-aware item discounts for buying documents."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from redtra_customisation.purchase_invoice.default_accounts import get_default_discount_account


DISCOUNT_AMOUNT = "custom_purchase_discount_amount"
DISCOUNT_ACCOUNT = "custom_purchase_discount_account"
DISCOUNT_MARKER = "custom_is_purchase_item_discount"
DISCOUNT_TOTAL = "custom_purchase_discount_total"
ADJUSTED_TAX_BASE_MARKER = "custom_uses_adjusted_tax_base"
ORIGINAL_CHARGE_TYPE = "custom_original_charge_type"
ORIGINAL_ROW_ID = "custom_original_row_id"


def sync_purchase_order_item_discounts(purchase_order, method=None):
	"""Create standard Deduct charge rows without changing item rates."""
	validate_standard_rate_discounts_are_unused(purchase_order)
	ensure_selected_purchase_order_tax_template(purchase_order)
	sync_item_discounts(purchase_order)
	configure_purchase_order_discount_tax_base(purchase_order)


def sync_item_discounts(document):
	"""Translate each item's discount into a standard account-aware deduction."""
	if not _has_discount_fields(document):
		return

	document.set(
		"taxes",
		[row for row in document.get("taxes") if not cint(row.get(DISCOUNT_MARKER))],
	)

	for (account, cost_center), amount in get_item_discount_totals(document).items():
		document.append(
			"taxes",
			{
				"charge_type": "Actual",
				"category": "Total",
				"add_deduct_tax": "Deduct",
				"account_head": account,
				"cost_center": cost_center,
				"description": _("Item Discounts"),
				"tax_amount": amount,
				"included_in_print_rate": 0,
				"included_in_paid_amount": 0,
				DISCOUNT_MARKER: 1,
			},
		)

	reindex_tax_rows(document)
	set_discount_total(document)


def validate_standard_rate_discounts_are_unused(purchase_order):
	"""Prevent ERPNext's standard fields from rewriting the user-entered rate."""
	for item in purchase_order.get("items"):
		if flt(item.discount_amount) or flt(item.discount_percentage):
			frappe.throw(
				_(
					"Row {0}: Clear Price Reduction / Unit and enter the value in Discount Amount. "
					"The item Rate will remain unchanged."
				).format(item.idx)
			)


def ensure_selected_purchase_order_tax_template(purchase_order):
	"""Restore a selected PO tax template only when no standard tax row exists."""
	if not purchase_order.get("taxes_and_charges"):
		return

	standard_tax_rows = [
		row for row in purchase_order.get("taxes") if not cint(row.get(DISCOUNT_MARKER))
	]
	if standard_tax_rows:
		return

	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	for tax in get_taxes_and_charges(
		"Purchase Taxes and Charges Template", purchase_order.taxes_and_charges
	) or []:
		purchase_order.append("taxes", tax)


def configure_purchase_order_discount_tax_base(purchase_order):
	"""Place item discounts before percentage taxes and tax the discounted total."""
	discount_rows = [
		row for row in purchase_order.get("taxes") if cint(row.get(DISCOUNT_MARKER))
	]
	if not discount_rows:
		restore_purchase_order_tax_base(purchase_order)
		reindex_tax_rows(purchase_order)
		return

	other_rows = [row for row in purchase_order.get("taxes") if not cint(row.get(DISCOUNT_MARKER))]
	purchase_order.set("taxes", discount_rows + other_rows)
	reindex_tax_rows(purchase_order)
	last_discount_row = discount_rows[-1]

	for row in other_rows:
		if row.charge_type == "On Net Total":
			row.set(ORIGINAL_CHARGE_TYPE, "On Net Total")
			row.set(ORIGINAL_ROW_ID, row.row_id)
			row.charge_type = "On Previous Row Total"
			row.row_id = last_discount_row.idx
			row.set(ADJUSTED_TAX_BASE_MARKER, 1)
		elif cint(row.get(ADJUSTED_TAX_BASE_MARKER)):
			row.row_id = last_discount_row.idx


def restore_purchase_order_tax_base(purchase_order):
	"""Restore the tax-template charge type after all item discounts are removed."""
	for row in purchase_order.get("taxes"):
		if not cint(row.get(ADJUSTED_TAX_BASE_MARKER)):
			continue
		row.charge_type = row.get(ORIGINAL_CHARGE_TYPE) or "On Net Total"
		row.row_id = row.get(ORIGINAL_ROW_ID) or None
		row.set(ADJUSTED_TAX_BASE_MARKER, 0)
		row.set(ORIGINAL_CHARGE_TYPE, None)
		row.set(ORIGINAL_ROW_ID, None)


def validate_item_discounts(document):
	"""Keep generated discount rows deductible and account-backed."""
	if not _has_discount_fields(document):
		return

	for row in [row for row in document.get("taxes") if cint(row.get(DISCOUNT_MARKER))]:
		if row.charge_type != "Actual" or row.category != "Total" or row.add_deduct_tax != "Deduct":
			frappe.throw(_("Item Discount rows must use Actual type, Total category, and Deduct."))
		if flt(row.tax_amount) <= 0:
			frappe.throw(_("Item Discount Amount must be greater than zero."))
		validate_discount_account(document, row.account_head)
		validate_cost_center(document, row)

	set_discount_total(document)


def get_item_discount_totals(document):
	"""Return discounts per account, including partial-document quantities."""
	totals = {}
	for item in document.get("items"):
		discount = flt(item.get(DISCOUNT_AMOUNT))
		if not discount:
			continue
		if discount < 0:
			frappe.throw(_("Row {0}: Discount Amount cannot be negative.").format(item.idx))
		discount_amount = get_item_discount_amount(document, item)
		row_amount = max(flt(item.amount), flt(item.rate) * flt(item.qty))
		if document.doctype == "Purchase Order" and discount_amount > row_amount:
			frappe.throw(
				_("Row {0}: Discount Amount cannot exceed the row amount of {1}.").format(
					item.idx, frappe.format_value(row_amount, {"fieldtype": "Currency"})
				)
			)
		account = item.get(DISCOUNT_ACCOUNT) or get_default_discount_account(document.company)
		if not account:
			frappe.throw(_("Row {0}: Select a Discount Account before saving.").format(item.idx))
		item.set(DISCOUNT_ACCOUNT, account)
		cost_center = item.cost_center or get_default_cost_center(document)
		if not cost_center:
			frappe.throw(_("Row {0}: A Cost Center is required for the Discount Account.").format(item.idx))
		key = (account, cost_center)
		totals[key] = flt(totals.get(key)) + discount_amount
	return {key: amount for key, amount in totals.items() if flt(amount)}


def get_item_discount_amount(document, item):
	"""Return the monetary discount contributed by one buying-document row."""
	discount = flt(item.get(DISCOUNT_AMOUNT))
	if document.doctype == "Purchase Order":
		return discount
	return discount * flt(item.qty)


def validate_discount_account(document, account_name):
	account = frappe.db.get_value(
		"Account",
		account_name,
		["company", "is_group", "disabled", "report_type"],
		as_dict=True,
	)
	if (
		not account
		or account.company != document.company
		or cint(account.is_group)
		or cint(account.disabled)
		or account.report_type != "Profit and Loss"
	):
		frappe.throw(_("Discount Account must be an active, non-group Profit and Loss account in this Company."))


def validate_cost_center(document, row):
	row.cost_center = row.cost_center or get_default_cost_center(document)
	cost_center = frappe.db.get_value(
		"Cost Center", row.cost_center, ["company", "is_group", "disabled"], as_dict=True
	)
	if (
		not cost_center
		or cost_center.company != document.company
		or cint(cost_center.is_group)
		or cint(cost_center.disabled)
	):
		frappe.throw(_("Item Discount Cost Center must be active, non-group, and in this Company."))


def get_default_cost_center(document):
	return next((item.cost_center for item in document.get("items") if item.cost_center), None) or document.get(
		"cost_center"
	) or frappe.db.get_value("Company", document.company, "cost_center")


def reindex_tax_rows(document):
	"""Actual charges are keyed by row index during ERPNext tax calculation."""
	for index, row in enumerate(document.get("taxes"), start=1):
		row.idx = index


def set_discount_total(document):
	if document.meta.has_field(DISCOUNT_TOTAL):
		document.set(DISCOUNT_TOTAL, sum(get_item_discount_totals(document).values()))


def _has_discount_fields(document):
	item_doctype = f"{document.doctype} Item"
	return (
		frappe.get_meta(item_doctype).has_field(DISCOUNT_AMOUNT)
		and frappe.get_meta("Purchase Taxes and Charges").has_field(DISCOUNT_MARKER)
	)
