# Copyright (c) 2026, redtra_customisation contributors

from frappe.utils import flt

from erpnext.accounts.general_ledger import get_round_off_account_and_cost_center


def has_manual_rounding(doc) -> bool:
	if flt(doc.get("rounding_adjustment")):
		return True

	grand_total = flt(doc.grand_total)
	rounded_total = flt(doc.get("rounded_total"))
	return rounded_total and abs(rounded_total - grand_total) > 0.0001


def preserve_manual_rounding(doc):
	"""Re-apply user-entered rounding after ERPNext totals reset it."""
	if not has_manual_rounding(doc):
		return

	manual_rounding = flt(doc.rounding_adjustment)
	manual_rounded = flt(doc.rounded_total)
	conversion_rate = flt(doc.conversion_rate) or 1.0

	if manual_rounding:
		doc.rounding_adjustment = manual_rounding
		doc.rounded_total = flt(doc.grand_total) + manual_rounding
	elif manual_rounded:
		doc.rounded_total = manual_rounded
		doc.rounding_adjustment = flt(manual_rounded - flt(doc.grand_total))

	doc.base_rounding_adjustment = flt(
		doc.rounding_adjustment * conversion_rate,
		doc.precision("base_rounding_adjustment"),
	)
	doc.base_rounded_total = flt(doc.base_grand_total) + flt(doc.base_rounding_adjustment)

	if doc.meta.get_field("outstanding_amount") and doc.docstatus == 0:
		doc.outstanding_amount = flt(doc.rounded_total) - flt(doc.paid_amount)


def apply_round_off_account_override(doc, gl_entries: list) -> list:
	"""Use PI-level round off account override when set."""
	override_account = doc.get("custom_round_off_account")
	if not override_account or not flt(doc.base_rounding_adjustment):
		return gl_entries

	default_account, _, _ = get_round_off_account_and_cost_center(
		doc.company,
		doc.doctype,
		doc.name,
		doc.get("use_company_roundoff_cost_center"),
	)

	for entry in gl_entries:
		debit = flt(entry.get("debit"))
		if debit and abs(debit - flt(doc.base_rounding_adjustment)) < 0.0001:
			if entry.get("account") == default_account or entry.get("account") == override_account:
				entry["account"] = override_account

	return gl_entries
