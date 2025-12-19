# Copyright (c) 2025, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None) -> tuple:
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Payment Entry"),
			"fieldname": "payment_entry",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 150
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Party Type"),
			"fieldname": "party_type",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Party"),
			"fieldname": "party",
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 150
		},
		{
			"label": _("Cheque Number"),
			"fieldname": "cheque_number",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Cheque Date"),
			"fieldname": "cheque_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Bank Account"),
			"fieldname": "bank_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 150
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120
		}
	]


def get_data(filters: dict | None = None) -> list[dict]:
	"""Get PDC register data"""
	# Build filters
	filter_dict = {
		"docstatus": 1,
		"pdc_cheque_number": ["!=", ""]
	}
	
	if filters.get("company"):
		filter_dict["company"] = filters.company
	if filters.get("party_type"):
		filter_dict["party_type"] = filters.party_type
	if filters.get("party"):
		filter_dict["party"] = filters.party
	if filters.get("status"):
		filter_dict["pdc_cheque_status"] = filters.status
	
	# Handle date range
	if filters.get("from_date") and filters.get("to_date"):
		filter_dict["pdc_cheque_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		filter_dict["pdc_cheque_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		filter_dict["pdc_cheque_date"] = ["<=", filters.to_date]
	
	# Get payment entries
	data = frappe.get_all(
		"Payment Entry",
		filters=filter_dict,
		fields=[
			"name as payment_entry",
			"posting_date",
			"party_type",
			"party",
			"pdc_cheque_number as cheque_number",
			"pdc_cheque_date as cheque_date",
			"pdc_bank_account as bank_account",
			"pdc_cheque_status as status",
			"paid_amount",
			"received_amount",
			"company",
			"payment_type"
		],
		order_by="pdc_cheque_date desc, posting_date desc"
	)
	
	# Calculate amount based on payment type
	for row in data:
		if row.payment_type == "Receive":
			row.amount = row.received_amount
		else:
			row.amount = row.paid_amount
	
	return data


