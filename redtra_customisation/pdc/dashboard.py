"""
Dashboard data for Customer and Supplier PDC tracking
"""

import frappe
from frappe import _


def get_pdc_summary(party_type, party):
	"""
	Get PDC summary for a customer or supplier
	Returns: dict with received/issued amounts and counts
	"""
	if not party_type or not party:
		return {}
	
	if party_type == "Customer":
		return get_customer_pdc_summary(party)
	elif party_type == "Supplier":
		return get_supplier_pdc_summary(party)
	else:
		return {}


def get_customer_pdc_summary(customer):
	"""Get PDC received summary for customer"""
	# Get all relevant payment entries
	entries = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"party_type": "Customer",
			"party": customer,
			"payment_type": "Receive",
			"pdc_cheque_number": ["!=", ""],
			"pdc_cheque_status": ["in", ["Issued", "Under Collection"]]
		},
		fields=["pdc_cheque_status", "received_amount"]
	)
	
	# Group by status
	data = {}
	for entry in entries:
		status = entry.pdc_cheque_status
		if status not in data:
			data[status] = {"count": 0, "amount": 0}
		data[status]["count"] += 1
		data[status]["amount"] += entry.received_amount or 0
	
	total_count = len(entries)
	total_amount = sum(entry.received_amount or 0 for entry in entries)
	
	return {
		"total_count": total_count,
		"total_amount": total_amount,
		"status_breakdown": data,
		"type": "received"
	}


def get_supplier_pdc_summary(supplier):
	"""Get PDC issued summary for supplier"""
	# Get all relevant payment entries
	entries = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"party_type": "Supplier",
			"party": supplier,
			"payment_type": "Pay",
			"pdc_cheque_number": ["!=", ""],
			"pdc_cheque_status": ["in", ["Issued", "Under Collection"]]
		},
		fields=["pdc_cheque_status", "paid_amount"]
	)
	
	# Group by status
	data = {}
	for entry in entries:
		status = entry.pdc_cheque_status
		if status not in data:
			data[status] = {"count": 0, "amount": 0}
		data[status]["count"] += 1
		data[status]["amount"] += entry.paid_amount or 0
	
	total_count = len(entries)
	total_amount = sum(entry.paid_amount or 0 for entry in entries)
	
	return {
		"total_count": total_count,
		"total_amount": total_amount,
		"status_breakdown": data,
		"type": "issued"
	}


@frappe.whitelist()
def get_party_pdc_dashboard(party_type, party):
	"""API endpoint for dashboard data"""
	return get_pdc_summary(party_type, party)
