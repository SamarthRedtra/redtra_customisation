"""Keep standard Landed Cost Voucher link totals consistent across vouchers."""

import frappe
from frappe.utils import flt


def reconcile_landed_cost_links(doc, method=None):
	"""Refresh standard receipt and vendor-invoice amounts after an LCV transition.

	ERPNext already validates the company, submitted receipt document, and the
	``Update Stock`` requirement for Purchase Invoice receipt documents. This
	hook deliberately adds no custom link fields or alternate validation.
	"""
	_refresh_receipt_landed_cost_amounts(doc)
	_refresh_vendor_invoice_claimed_amounts(doc)


def _refresh_receipt_landed_cost_amounts(lcv):
	"""Persist each linked receipt item's standard LCV amount."""
	receipt_documents = {
		(row.receipt_document_type, row.receipt_document)
		for row in lcv.get("purchase_receipts")
		if row.receipt_document_type and row.receipt_document
	}

	for receipt_document_type, receipt_document in receipt_documents:
		receipt = frappe.get_doc(receipt_document_type, receipt_document)
		receipt.set_landed_cost_voucher_amount()

		for item in receipt.get("items"):
			item.db_update()


def _refresh_vendor_invoice_claimed_amounts(lcv):
	"""Recalculate claims from every submitted LCV, including sibling vouchers."""
	vendor_invoices = {
		row.vendor_invoice for row in lcv.get("vendor_invoices") if row.vendor_invoice
	}

	for vendor_invoice in vendor_invoices:
		claimed_amount = _get_submitted_claimed_amount(vendor_invoice)
		precision = frappe.get_precision("Purchase Invoice", "claimed_landed_cost_amount")
		claimed_amount = flt(claimed_amount, precision)

		if flt(
			frappe.db.get_value("Purchase Invoice", vendor_invoice, "claimed_landed_cost_amount"),
			precision,
		) != claimed_amount:
			frappe.db.set_value(
				"Purchase Invoice",
				vendor_invoice,
				"claimed_landed_cost_amount",
				claimed_amount,
				update_modified=False,
			)


def _get_submitted_claimed_amount(vendor_invoice):
	"""Return the total of vendor-charge rows that belong to submitted LCVs."""
	amounts = frappe.get_all(
		"Landed Cost Vendor Invoice",
		filters={
			"parenttype": "Landed Cost Voucher",
			"vendor_invoice": vendor_invoice,
			"docstatus": 1,
		},
		pluck="amount",
	)
	return sum(flt(amount) for amount in amounts)
