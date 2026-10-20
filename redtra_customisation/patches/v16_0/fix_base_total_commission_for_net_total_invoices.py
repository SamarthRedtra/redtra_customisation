"""Recompute commission from base_total for submitted SIs stuck on Net Total.

ERPNext ``calculate_commission`` sums ``item.base_net_amount`` (after retention /
advance). Project Commission reads Sales Team incentives from that reduced base.
ACC-SINV-2026-00260-2 and similar invoices were amended/submitted with Net Total
eligible amounts; this patch rewrites header + Sales Team from ``base_total``.

Also links Sales Person ``MUHAMMAD WAQAR`` to employee SK0092 so Project Commission
Pay is enabled (same person as ``MUHAMMAD WAQAR TARIQ MUHAMMAD TARIQ``).
"""

import frappe
from frappe.utils import flt


def _fix_invoice(invoice_name: str, rate: float, base: float):
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


def _link_waqar_sales_person():
	if not frappe.db.exists("Sales Person", "MUHAMMAD WAQAR"):
		return
	if not frappe.db.exists("Employee", "SK0092"):
		return
	if frappe.db.get_value("Sales Person", "MUHAMMAD WAQAR", "employee"):
		return
	frappe.db.set_value(
		"Sales Person",
		"MUHAMMAD WAQAR",
		"employee",
		"SK0092",
		update_modified=False,
	)


def execute():
	meta = frappe.get_meta("Sales Invoice")
	if not meta.has_field("total_commission") or not meta.has_field("commission_rate"):
		return

	_link_waqar_sales_person()

	rows = frappe.db.sql(
		"""
		SELECT name, base_total, base_net_total, commission_rate
		FROM `tabSales Invoice`
		WHERE docstatus = 1
			AND IFNULL(commission_rate, 0) > 0
			AND ABS(IFNULL(amount_eligible_for_commission, 0) - IFNULL(base_net_total, 0)) < 0.02
			AND ABS(IFNULL(base_total, 0) - IFNULL(base_net_total, 0)) > 1
		""",
		as_dict=True,
	)

	# Always include the amended 00260 live invoice even if already partially fixed.
	explicit = ("ACC-SINV-2026-00260-2",)
	seen = {r.name for r in rows}
	for name in explicit:
		if name in seen:
			continue
		invoice = frappe.db.get_value(
			"Sales Invoice",
			name,
			["name", "docstatus", "base_total", "base_net_total", "commission_rate"],
			as_dict=True,
		)
		if invoice and invoice.docstatus == 1:
			rows.append(invoice)

	for invoice in rows:
		rate = flt(invoice.commission_rate)
		base = flt(invoice.base_total)
		if rate <= 0 or base <= 0:
			continue
		_fix_invoice(invoice.name, rate, base)

	frappe.db.commit()
