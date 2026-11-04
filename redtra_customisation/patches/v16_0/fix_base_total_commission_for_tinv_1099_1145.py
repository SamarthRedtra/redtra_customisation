"""Recompute commission from base_total for TINV/1099 and TINV/1145 AUG invoices.

These submitted invoices still store amount_eligible_for_commission = Net Total
(after retention/advance). Draft calculation already uses base_total; submitted
docs skip recalculation, so rewrite header + Sales Team from invoice Total.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

EXPLICIT_INVOICES = (
	"TINV/1099/2026-AUG/1",
	"TINV/1099/2026-AUG/1-1",
	"TINV/1145/2026-AUG/1",
	"TINV/1145/2026-AUG/1-1",
)


def fix_invoice_commission_from_base_total(invoice_name: str, rate: float, base: float) -> dict:
	"""Rewrite SI commission header and Sales Team incentives from base_total."""
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

	team_updates = []
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
		team_updates.append(
			{
				"name": row.name,
				"allocated_amount": allocated_amount,
				"incentives": incentives,
			}
		)

	return {
		"name": invoice_name,
		"amount_eligible_for_commission": base,
		"total_commission": total_commission,
		"sales_team": team_updates,
	}


def collect_invoices_to_fix() -> list[dict]:
	"""Explicit TINV names plus any submitted SI still stuck on Net Total."""
	rows = frappe.db.sql(
		"""
		SELECT name, base_total, base_net_total, commission_rate, amount_eligible_for_commission
		FROM `tabSales Invoice`
		WHERE docstatus = 1
			AND IFNULL(commission_rate, 0) > 0
			AND ABS(IFNULL(amount_eligible_for_commission, 0) - IFNULL(base_net_total, 0)) < 0.02
			AND IFNULL(base_total, 0) > IFNULL(base_net_total, 0) + 1
		""",
		as_dict=True,
	)
	seen = {row.name for row in rows}

	for name in EXPLICIT_INVOICES:
		if name in seen:
			continue
		invoice = frappe.db.get_value(
			"Sales Invoice",
			name,
			[
				"name",
				"docstatus",
				"base_total",
				"base_net_total",
				"commission_rate",
				"amount_eligible_for_commission",
			],
			as_dict=True,
		)
		if invoice and invoice.docstatus == 1 and flt(invoice.commission_rate) > 0:
			rows.append(invoice)

	return rows


def execute():
	meta = frappe.get_meta("Sales Invoice")
	if not meta.has_field("total_commission") or not meta.has_field("commission_rate"):
		return

	for invoice in collect_invoices_to_fix():
		rate = flt(invoice.commission_rate)
		base = flt(invoice.base_total)
		if rate <= 0 or base <= 0:
			continue
		fix_invoice_commission_from_base_total(invoice.name, rate, base)

	frappe.db.commit()
