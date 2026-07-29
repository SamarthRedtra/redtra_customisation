"""Correct historical paid-invoice commission headers after the base-total rule change."""

import frappe
from frappe.utils import flt


# These invoices were previously calculated from a residual / Net Total amount.
# Missing invoices are skipped so the patch is safe across sites.
INVOICES = ("ACC-SINV-2026-00214", "ACC-SINV-2026-00229")


def execute():
	meta = frappe.get_meta("Sales Invoice")
	if not meta.has_field("total_commission") or not meta.has_field("commission_rate"):
		return

	for invoice_name in INVOICES:
		invoice = frappe.db.get_value(
			"Sales Invoice",
			invoice_name,
			["name", "docstatus", "base_total", "commission_rate"],
			as_dict=True,
		)
		if not invoice or invoice.docstatus != 1:
			continue

		rate = flt(invoice.commission_rate)
		if not rate:
			continue
		amount = flt(invoice.base_total) * rate / 100.0
		values = {
			"amount_eligible_for_commission": flt(invoice.base_total),
			"total_commission": amount,
		}
		if meta.has_field("custom_commission_recorded"):
			values["custom_commission_recorded"] = 1
		frappe.db.set_value("Sales Invoice", invoice_name, values, update_modified=False)

	frappe.db.commit()

