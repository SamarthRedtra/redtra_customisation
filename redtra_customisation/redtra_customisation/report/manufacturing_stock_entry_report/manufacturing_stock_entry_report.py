# Copyright (c) 2026, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	report_summary = get_report_summary(data)
	return columns, data, None, chart, report_summary


def get_columns():
	return [
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 160,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Work Order"),
			"fieldname": "work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 160,
		},
		{
			"label": _("BOM No"),
			"fieldname": "bom_no",
			"fieldtype": "Link",
			"options": "BOM",
			"width": 160,
		},
		{
			"label": _("FG Completed Qty"),
			"fieldname": "fg_completed_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Type"),
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Qty"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("UOM"),
			"fieldname": "uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80,
		},
		{
			"label": _("Source Warehouse"),
			"fieldname": "s_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180,
		},
		{
			"label": _("Target Warehouse"),
			"fieldname": "t_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180,
		},
		{
			"label": _("Basic Rate"),
			"fieldname": "basic_rate",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Basic Amount"),
			"fieldname": "basic_amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Item BOM No"),
			"fieldname": "item_bom_no",
			"fieldtype": "Link",
			"options": "BOM",
			"width": 150,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 150,
		},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql(
		"""
		SELECT
			se.name AS stock_entry,
			se.posting_date,
			se.work_order,
			se.bom_no,
			se.fg_completed_qty,
			sed.item_code,
			sed.item_name,
			sed.is_finished_item,
			sed.is_scrap_item,
			CASE
				WHEN sed.is_finished_item = 1 THEN 'Produced Item'
				WHEN sed.is_scrap_item = 1 THEN 'Scrap Item'
				ELSE 'Material Consumed'
			END AS item_type,
			sed.qty,
			sed.uom,
			sed.s_warehouse,
			sed.t_warehouse,
			sed.basic_rate,
			sed.basic_amount,
			sed.bom_no AS item_bom_no,
			se.company
		FROM
			`tabStock Entry` se
		INNER JOIN
			`tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE
			se.docstatus = 1
			AND se.purpose = 'Manufacture'
			{conditions}
		ORDER BY
			se.posting_date DESC, se.name DESC, sed.idx ASC
		""".format(conditions=conditions),
		filters,
		as_dict=True,
	)

	return data


def get_conditions(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND se.company = %(company)s"

	if filters.get("from_date"):
		conditions += " AND se.posting_date >= %(from_date)s"

	if filters.get("to_date"):
		conditions += " AND se.posting_date <= %(to_date)s"

	if filters.get("bom_no"):
		conditions += " AND se.bom_no = %(bom_no)s"

	if filters.get("work_order"):
		conditions += " AND se.work_order = %(work_order)s"

	if filters.get("item_type"):
		if filters.item_type == "Produced Item":
			conditions += " AND sed.is_finished_item = 1"
		elif filters.item_type == "Scrap Item":
			conditions += " AND sed.is_scrap_item = 1"
		elif filters.item_type == "Material Consumed":
			conditions += " AND sed.is_finished_item = 0 AND sed.is_scrap_item = 0"

	return conditions


def get_chart(data):
	"""Bar chart: Consumed vs Produced amounts grouped by BOM."""
	if not data:
		return None

	bom_consumed = defaultdict(float)
	bom_produced = defaultdict(float)

	for row in data:
		bom = row.get("bom_no") or "No BOM"
		if row.get("is_finished_item"):
			bom_produced[bom] += row.get("basic_amount") or 0
		elif not row.get("is_scrap_item"):
			bom_consumed[bom] += row.get("basic_amount") or 0

	all_boms = sorted(set(list(bom_consumed.keys()) + list(bom_produced.keys())))

	if not all_boms:
		return None

	return {
		"data": {
			"labels": all_boms,
			"datasets": [
				{
					"name": _("Material Consumed"),
					"values": [bom_consumed.get(b, 0) for b in all_boms],
				},
				{
					"name": _("Produced Item"),
					"values": [bom_produced.get(b, 0) for b in all_boms],
				},
			],
		},
		"type": "bar",
		"colors": ["#e24c4c", "#38a169"],
		"barOptions": {"stacked": False},
	}


def get_report_summary(data):
	"""Number cards for key metrics."""
	if not data:
		return None

	stock_entries = set()
	total_consumed_qty = 0
	total_produced_qty = 0
	total_consumed_amount = 0
	total_produced_amount = 0

	for row in data:
		stock_entries.add(row.get("stock_entry"))
		if row.get("is_finished_item"):
			total_produced_qty += row.get("qty") or 0
			total_produced_amount += row.get("basic_amount") or 0
		elif not row.get("is_scrap_item"):
			total_consumed_qty += row.get("qty") or 0
			total_consumed_amount += row.get("basic_amount") or 0

	return [
		{
			"value": len(stock_entries),
			"indicator": "blue",
			"label": _("Total Entries"),
			"datatype": "Int",
		},
		{
			"value": total_consumed_qty,
			"indicator": "red",
			"label": _("Consumed Qty"),
			"datatype": "Float",
		},
		{
			"value": total_consumed_amount,
			"indicator": "red",
			"label": _("Consumed Amount"),
			"datatype": "Currency",
		},
		{
			"value": total_produced_qty,
			"indicator": "green",
			"label": _("Produced Qty"),
			"datatype": "Float",
		},
		{
			"value": total_produced_amount,
			"indicator": "green",
			"label": _("Produced Amount"),
			"datatype": "Currency",
		},
	]
