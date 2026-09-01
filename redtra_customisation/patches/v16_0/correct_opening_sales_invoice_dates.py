"""Correct the imported opening Sales Invoice dates from the closing-balance workbook."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from redtra_customisation.patches.v16_0.opening_sales_invoice_date_map import INVOICE_DATE_MAP
from redtra_customisation.patches.v16_0.sales_invoice_date_utils import dates_match


COMPANY = "Deltachem Middle East LLC"
SOURCE_POSTING_DATE = "2026-08-16"
SOURCE_DUE_DATE = "2026-07-31"
EXPECTED_INVOICE_COUNT = 133


def execute():
	"""Apply the guarded, idempotent opening-balance date correction."""
	if not frappe.db.exists("Company", COMPANY):
		return
	if not _has_mapped_invoices():
		return

	if len(INVOICE_DATE_MAP) != EXPECTED_INVOICE_COUNT:
		frappe.throw(
			_("Opening Sales Invoice date map must contain {0} entries.").format(EXPECTED_INVOICE_COUNT)
		)

	records = _preflight()
	_apply_date_correction(records)
	_verify_correction()


def _has_mapped_invoices():
	"""Return whether this site has any invoice from the Delta data correction."""
	return bool(
		frappe.get_all(
			"Sales Invoice",
			filters={"name": ("in", list(INVOICE_DATE_MAP))},
			limit_page_length=1,
			pluck="name",
		)
	)


def _preflight():
	"""Validate every document and ledger pattern before changing any date."""
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"name": ["in", list(INVOICE_DATE_MAP)]},
		fields=[
			"name",
			"company",
			"docstatus",
			"custom_reference_invoice",
			"posting_date",
			"due_date",
			"is_opening",
			"update_stock",
			"is_return",
			"grand_total",
			"outstanding_amount",
		],
		order_by="name",
	)
	if len(invoices) != EXPECTED_INVOICE_COUNT:
		frappe.throw(
			_("Expected {0} mapped Sales Invoices, found {1}.").format(EXPECTED_INVOICE_COUNT, len(invoices))
		)

	records = []
	for invoice in invoices:
		records.append(_validate_invoice(invoice))

	_invoices_with_source_dates_match_pending_records(records)
	return records


def _validate_invoice(invoice):
	"""Return a validated invoice and the exact ledger rows to update."""
	expected_reference, posting_date, due_date = INVOICE_DATE_MAP[invoice.name]
	if invoice.company != COMPANY:
		_raise_unexpected(invoice.name, "company")
	if invoice.custom_reference_invoice != expected_reference:
		_raise_unexpected(invoice.name, "reference invoice")
	if cint(invoice.docstatus) != 1:
		_raise_unexpected(invoice.name, "document status")
	if invoice.is_opening != "Yes":
		_raise_unexpected(invoice.name, "opening balance flag")
	if cint(invoice.update_stock) or cint(invoice.is_return):
		_raise_unexpected(invoice.name, "stock or return state")
	if flt(invoice.outstanding_amount) != flt(invoice.grand_total):
		_raise_unexpected(invoice.name, "unpaid amount")
	if frappe.db.count("Payment Schedule", {"parenttype": "Sales Invoice", "parent": invoice.name}):
		_raise_unexpected(invoice.name, "payment schedule rows")

	is_correct = dates_match(invoice.posting_date, invoice.due_date, posting_date, due_date)
	is_pending = dates_match(invoice.posting_date, invoice.due_date, SOURCE_POSTING_DATE, SOURCE_DUE_DATE)
	if not is_correct and not is_pending:
		_raise_unexpected(invoice.name, "invoice dates")

	payment_ledger_entry = _get_payment_ledger_entry(invoice.name)
	if not dates_match(
		payment_ledger_entry.posting_date,
		payment_ledger_entry.due_date,
		posting_date if is_correct else SOURCE_POSTING_DATE,
		due_date if is_correct else SOURCE_DUE_DATE,
	):
		_raise_unexpected(invoice.name, "Payment Ledger Entry dates")

	gl_entries = _get_gl_entries(invoice.name)
	expected_gl_date = posting_date if is_correct else SOURCE_POSTING_DATE
	if any(str(gl_entry.posting_date) != expected_gl_date for gl_entry in gl_entries):
		_raise_unexpected(invoice.name, "GL Entry dates")

	return {
		"invoice": invoice,
		"payment_ledger_entry": payment_ledger_entry,
		"gl_entries": gl_entries,
		"posting_date": posting_date,
		"due_date": due_date,
		"is_correct": is_correct,
	}


def _invoices_with_source_dates_match_pending_records(records):
	"""Reject unrelated imports that still have the source closing-balance dates."""
	pending_names = {record["invoice"].name for record in records if not record["is_correct"]}
	source_names = set(
		frappe.get_all(
			"Sales Invoice",
			filters={
				"company": COMPANY,
				"docstatus": 1,
				"is_opening": "Yes",
				"posting_date": SOURCE_POSTING_DATE,
				"due_date": SOURCE_DUE_DATE,
			},
			pluck="name",
		)
	)
	if source_names != pending_names:
		frappe.throw(_("Opening Sales Invoice source-date set differs from the approved correction map."))


def _get_payment_ledger_entry(invoice_name):
	entries = frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"company": COMPANY,
			"voucher_type": "Sales Invoice",
			"voucher_no": invoice_name,
			"against_voucher_type": "Sales Invoice",
			"against_voucher_no": invoice_name,
			"delinked": 0,
		},
		fields=["name", "posting_date", "due_date"],
	)
	if len(entries) != 1:
		_raise_unexpected(invoice_name, "self-referencing Payment Ledger Entry pattern")
	return entries[0]


def _get_gl_entries(invoice_name):
	entries = frappe.get_all(
		"GL Entry",
		filters={
			"company": COMPANY,
			"voucher_type": "Sales Invoice",
			"voucher_no": invoice_name,
			"is_cancelled": 0,
		},
		fields=["name", "posting_date"],
	)
	if len(entries) != 2:
		_raise_unexpected(invoice_name, "active GL Entry pattern")
	return entries


def _apply_date_correction(records):
	"""Write only dates; all document names and accounting values remain intact."""
	for record in records:
		if record["is_correct"]:
			continue

		invoice_name = record["invoice"].name
		frappe.db.set_value(
			"Sales Invoice",
			invoice_name,
			{"posting_date": record["posting_date"], "due_date": record["due_date"]},
			update_modified=False,
		)
		frappe.db.set_value(
			"Payment Ledger Entry",
			record["payment_ledger_entry"].name,
			{"posting_date": record["posting_date"], "due_date": record["due_date"]},
			update_modified=False,
		)
		for gl_entry in record["gl_entries"]:
			frappe.db.set_value(
				"GL Entry",
				gl_entry.name,
				"posting_date",
				record["posting_date"],
				update_modified=False,
			)


def _verify_correction():
	"""Re-run all guards and ensure the correction left no pending invoices."""
	records = _preflight()
	if any(not record["is_correct"] for record in records):
		frappe.throw(_("Opening Sales Invoice correction did not complete."))


def _raise_unexpected(invoice_name, condition):
	frappe.throw(_("Sales Invoice {0} has an unexpected {1}.").format(invoice_name, condition))
