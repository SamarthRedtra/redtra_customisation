# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe import _
from frappe.utils import cint, flt

import erpnext


def sync_point_adjustment_rows(doc):
	item_by_idx = {cint(row.idx): row for row in doc.get("items") or []}
	item_by_name = {row.name: row for row in doc.get("items") or []}

	for adj in doc.get("point_adjustments") or []:
		item = None
		if adj.purchase_invoice_item:
			item = item_by_name.get(adj.purchase_invoice_item)
		if not item and adj.item_row:
			item = item_by_idx.get(cint(adj.item_row))

		if not item:
			frappe.throw(
				_("Point Adjustment row {0}: select a valid item line.").format(adj.idx)
			)

		adj.purchase_invoice_item = item.name
		adj.item_row = item.idx
		adj.item_code = item.item_code
		adj.item_name = item.item_name
		adj.reference_amount = flt(item.net_amount)


def apply_point_adjustments(doc):
	adjustments = doc.get("point_adjustments") or []
	adjustment_by_item = {}

	for adj in adjustments:
		if not adj.purchase_invoice_item:
			continue
		adjustment_by_item.setdefault(adj.purchase_invoice_item, 0.0)
		adjustment_by_item[adj.purchase_invoice_item] += flt(adj.adjustment_amount)

	total_adjustment = 0.0
	base_total_adjustment = 0.0
	conversion_rate = flt(doc.conversion_rate) or 1.0

	for item in doc.get("items") or []:
		item_adjustment = flt(adjustment_by_item.get(item.name, 0))
		item.custom_point_adjustment_total = item_adjustment

		if item_adjustment:
			base_adjustment = flt(
				item_adjustment * conversion_rate, item.precision("base_net_amount")
			)
			item.net_amount = flt(item.net_amount) + item_adjustment
			item.base_net_amount = flt(item.base_net_amount) + base_adjustment
			total_adjustment += item_adjustment
			base_total_adjustment += base_adjustment

		item.custom_adjusted_net_amount = flt(item.net_amount)

	doc.custom_total_point_adjustment = total_adjustment

	if not total_adjustment:
		return

	doc.net_total = flt(doc.net_total) + total_adjustment
	doc.base_net_total = flt(doc.base_net_total) + base_total_adjustment
	doc.grand_total = flt(doc.grand_total) + total_adjustment
	doc.base_grand_total = flt(doc.base_grand_total) + base_total_adjustment

	if doc.meta.get_field("outstanding_amount") and doc.docstatus == 0:
		paid_amount = flt(doc.paid_amount)
		doc.outstanding_amount = flt(doc.grand_total) - paid_amount

	if doc.get("disable_rounded_total"):
		return

	if not doc.meta.get_field("rounded_total") or doc.is_rounded_total_disabled():
		return

	from frappe.utils.data import round_based_on_smallest_currency_fraction

	doc.rounded_total = round_based_on_smallest_currency_fraction(
		doc.grand_total, doc.currency, doc.precision("rounded_total")
	)
	doc.rounding_adjustment = flt(
		doc.rounded_total - doc.grand_total, doc.precision("rounding_adjustment")
	)
	if doc.meta.get_field("base_rounded_total"):
		doc.base_rounded_total = round_based_on_smallest_currency_fraction(
			doc.base_grand_total, erpnext.get_company_currency(doc.company), doc.precision("base_rounded_total")
		)
		doc.base_rounding_adjustment = flt(
			doc.base_rounded_total - doc.base_grand_total, doc.precision("base_rounding_adjustment")
		)
