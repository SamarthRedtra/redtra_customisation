"""Set the approved Delta opening Sales Invoice dates to 31 July 2026."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from redtra_customisation.patches.v16_0.opening_sales_invoice_date_map import INVOICE_DATE_MAP


COMPANY = "Deltachem Middle East LLC"
SOURCE_POSTING_DATE = "2026-08-16"
SOURCE_DUE_DATE = "2026-07-31"
TARGET_DATE = "2026-07-31"
EXPECTED_INVOICE_COUNT = 133


def execute():
	"""Apply the guarded, idempotent closing-date correction."""
	if not frappe.db.exists("Company", COMPANY) or not _has_mapped_invoices():
		return
	if len(INVOICE_DATE_MAP) != EXPECTED_INVOICE_COUNT:
		frappe.throw(
			_("Opening Sales Invoice date map must contain {0} entries.").format(EXPECTED_INVOICE_COUNT)
		)

	records = _preflight()
	_apply_target_date(records)
	_verify_target_date()


def _has_mapped_invoices():
	"""Avoid applying Delta's historical correction on unrelated sites."""
	return bool(
		frappe.get_all(
			"Sales Invoice",
			filters={"name": ("in", list(INVOICE_DATE_MAP))},
			limit_page_length=1,
			pluck="name",
		)
	)


def _preflight():
	"""Validate the exact invoice and ledger patterns before changing dates."""
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"name": ("in", list(INVOICE_DATE_MAP))},
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

	return [_validate_invoice(invoice) for invoice in invoices]


def _validate_invoice(invoice):
	"""Return one fully validated correction record."""
	expected_reference, mapped_posting_date, mapped_due_date = INVOICE_DATE_MAP[invoice.name]
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

	is_correct = _dates_match(invoice.posting_date, invoice.due_date, TARGET_DATE, TARGET_DATE)
	if not is_correct and not _is_pre_target_date(invoice, mapped_posting_date, mapped_due_date):
		_raise_unexpected(invoice.name, "invoice dates")

	payment_ledger_entry = _get_payment_ledger_entry(invoice.name)
	expected_posting_date, expected_due_date = _expected_current_dates(
		invoice, mapped_posting_date, mapped_due_date, is_correct
	)
	if not _dates_match(
		payment_ledger_entry.posting_date,
		payment_ledger_entry.due_date,
		expected_posting_date,
		expected_due_date,
	):
		_raise_unexpected(invoice.name, "Payment Ledger Entry dates")

	gl_entries = _get_gl_entries(invoice.name)
	if any(str(gl_entry.posting_date) != expected_posting_date for gl_entry in gl_entries):
		_raise_unexpected(invoice.name, "GL Entry dates")

	return {
		"invoice": invoice,
		"payment_ledger_entry": payment_ledger_entry,
		"gl_entries": gl_entries,
		"is_correct": is_correct,
	}


def _is_pre_target_date(invoice, mapped_posting_date, mapped_due_date):
	"""Allow either previous approved mapping or the original import dates."""
	return _dates_match(
		invoice.posting_date, invoice.due_date, mapped_posting_date, mapped_due_date
	) or _dates_match(invoice.posting_date, invoice.due_date, SOURCE_POSTING_DATE, SOURCE_DUE_DATE)


def _expected_current_dates(invoice, mapped_posting_date, mapped_due_date, is_correct):
	if is_correct:
		return TARGET_DATE, TARGET_DATE
	if _dates_match(invoice.posting_date, invoice.due_date, mapped_posting_date, mapped_due_date):
		return mapped_posting_date, mapped_due_date
	return SOURCE_POSTING_DATE, SOURCE_DUE_DATE


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


def _apply_target_date(records):
	"""Write dates only; document names, values, and accounting remain unchanged."""
	for record in records:
		if record["is_correct"]:
			continue

		frappe.db.set_value(
			"Sales Invoice",
			record["invoice"].name,
			{"posting_date": TARGET_DATE, "due_date": TARGET_DATE},
			update_modified=False,
		)
		frappe.db.set_value(
			"Payment Ledger Entry",
			record["payment_ledger_entry"].name,
			{"posting_date": TARGET_DATE, "due_date": TARGET_DATE},
			update_modified=False,
		)
		for gl_entry in record["gl_entries"]:
			frappe.db.set_value(
				"GL Entry",
				gl_entry.name,
				"posting_date",
				TARGET_DATE,
				update_modified=False,
			)


def _verify_target_date():
	"""Re-run the complete preflight after writing the target dates."""
	if any(not record["is_correct"] for record in _preflight()):
		frappe.throw(_("Opening Sales Invoice closing-date correction did not complete."))


def _dates_match(actual_posting_date, actual_due_date, expected_posting_date, expected_due_date):
	return str(actual_posting_date) == expected_posting_date and str(actual_due_date) == expected_due_date


def _raise_unexpected(invoice_name, condition):
	frappe.throw(_("Sales Invoice {0} has an unexpected {1}.").format(invoice_name, condition))
