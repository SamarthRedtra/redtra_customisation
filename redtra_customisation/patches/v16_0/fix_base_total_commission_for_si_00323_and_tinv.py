"""Recompute commission from invoice Total (base_total) for more affected SIs.

Same Net Total bug as ACC-SINV-2026-00260-1 after project-wise defer skipped
Redtra's base_total override on validate.
"""

import frappe
from frappe.utils import flt


INVOICES = (
	"ACC-SINV-2026-00323",
	# Old combined name (pre project-no) and renamed form after rename_combined_tinv_to_include_project_no
	"TINV/February26-May26-June26/1",
	"TINV/1016/February26-May26-June26/1",
	"ACC-SINV-2026-00260-1",
)


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
		if rate <= 0:
			continue

		base = flt(invoice.base_total)
		total_commission = flt(base * rate / 100.0, 2)
		frappe.db.set_value(
			"Sales Invoice",
			invoice_name,
			{
				"amount_eligible_for_commission": base,
				"total_commission": total_commission,
			},
			update_modified=False,
		)

		for row in frappe.get_all(
			"Sales Team",
			filters={"parent": invoice_name, "parenttype": "Sales Invoice"},
			fields=["name", "allocated_percentage", "commission_rate"],
		):
			allocated_pct = flt(row.allocated_percentage) or 100.0
			row_rate = flt(row.commission_rate) or rate
			allocated_amount = flt(base * allocated_pct / 100.0, 2)
			incentives = flt(allocated_amount * row_rate / 100.0, 2)
			frappe.db.set_value(
				"Sales Team",
				row.name,
				{"allocated_amount": allocated_amount, "incentives": incentives},
				update_modified=False,
			)

	frappe.db.commit()
