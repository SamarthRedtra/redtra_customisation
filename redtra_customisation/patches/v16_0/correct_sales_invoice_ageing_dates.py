"""Correct Sales Invoice posting/due dates from Customer Ageing workbook rows."""

import frappe

from redtra_customisation.patches.v16_0.sales_invoice_ageing_date_map import (
	EXPECTED_RECEIVABLE_COUNT,
	RECEIVABLE_AGEING_ROWS,
)
from redtra_customisation.patches.v16_0.sales_invoice_date_utils import (
	COMPANY,
	AgeingCorrectionReport,
	apply_sales_invoice_dates,
	dates_match,
	find_sales_invoice,
	get_gl_entries,
)


def execute(dry_run=False):
	"""Apply workbook dates to all matched receivable Sales Invoices."""
	if not frappe.db.exists("Company", COMPANY):
		return

	if len(RECEIVABLE_AGEING_ROWS) != EXPECTED_RECEIVABLE_COUNT:
		frappe.throw(
			f"Customer Ageing map must contain {EXPECTED_RECEIVABLE_COUNT} receivable rows."
		)

	report = AgeingCorrectionReport()
	for invoice_ref, posting_date, due_date, pending_amount in RECEIVABLE_AGEING_ROWS:
		_process_row(report, invoice_ref, posting_date, due_date, pending_amount, dry_run=dry_run)

	report.log_summary()
	_log_gap_details(report)
	frappe.db.commit()


def _process_row(report, invoice_ref, posting_date, due_date, pending_amount, dry_run=False):
	row_info = {
		"invoice_ref": invoice_ref,
		"posting_date": posting_date,
		"due_date": due_date,
		"pending_amount": pending_amount,
	}

	invoice, issue = find_sales_invoice(invoice_ref, pending_amount)
	if issue:
		report.add(issue, row_info)
		return

	row_info["sales_invoice"] = invoice.name
	if dates_match(invoice.posting_date, invoice.due_date, posting_date, due_date):
		report.add("already_correct", row_info)
		return

	if not get_gl_entries(invoice.name):
		row_info["reason"] = "no active GL Entry rows"
		report.add("blocked", row_info)
		return

	if dry_run:
		report.add("corrected", row_info)
		return

	apply_sales_invoice_dates(invoice.name, posting_date, due_date)
	report.add("corrected", row_info)


def _log_gap_details(report):
	for label in ("not_found", "ambiguous", "blocked"):
		rows = getattr(report, label)
		if not rows:
			continue
		print(f"\n{label}:")
		for row in rows:
			extra = f" reason={row['reason']}" if row.get("reason") else ""
			print(
				f"  {row['invoice_ref']} pending={row['pending_amount']} "
				f"target={row['posting_date']}/{row['due_date']}{extra}"
			)
