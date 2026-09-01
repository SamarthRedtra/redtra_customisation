"""Shared helpers for Sales Invoice date corrections from the closing-balance workbook."""

import frappe
from frappe.utils import flt

COMPANY = "Deltachem Middle East LLC"
AMOUNT_TOLERANCE = 0.05


def dates_match(actual_posting_date, actual_due_date, expected_posting_date, expected_due_date):
	return str(actual_posting_date) == expected_posting_date and str(actual_due_date) == expected_due_date


def amounts_match(invoice, pending_amount):
	for field in ("outstanding_amount", "grand_total"):
		if abs(flt(invoice.get(field)) - flt(pending_amount)) <= AMOUNT_TOLERANCE:
			return True
	return False


def find_sales_invoice(invoice_ref, pending_amount):
	"""Resolve a submitted Sales Invoice for one Customer Ageing row."""
	fields = [
		"name",
		"company",
		"docstatus",
		"custom_reference_invoice",
		"posting_date",
		"due_date",
		"grand_total",
		"outstanding_amount",
		"is_opening",
	]
	filters = {"company": COMPANY, "docstatus": 1}

	candidates = {}
	for match_filter in ({"name": invoice_ref}, {"custom_reference_invoice": invoice_ref}):
		for row in frappe.get_all("Sales Invoice", filters={**filters, **match_filter}, fields=fields):
			candidates[row.name] = row

	if not candidates:
		return None, "not_found"

	matched = list(candidates.values())
	if len(matched) == 1:
		return matched[0], None

	amount_matches = [row for row in matched if amounts_match(row, pending_amount)]
	if len(amount_matches) == 1:
		return amount_matches[0], None

	return None, "ambiguous"


def get_payment_ledger_entries(invoice_name):
	return frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"company": COMPANY,
			"voucher_type": "Sales Invoice",
			"voucher_no": invoice_name,
			"delinked": 0,
		},
		fields=["name", "posting_date", "due_date"],
	)


def get_gl_entries(invoice_name):
	return frappe.get_all(
		"GL Entry",
		filters={
			"company": COMPANY,
			"voucher_type": "Sales Invoice",
			"voucher_no": invoice_name,
			"is_cancelled": 0,
		},
		fields=["name", "posting_date"],
	)


def apply_sales_invoice_dates(invoice_name, posting_date, due_date):
	frappe.db.set_value(
		"Sales Invoice",
		invoice_name,
		{"posting_date": posting_date, "due_date": due_date},
		update_modified=False,
	)

	for entry in get_payment_ledger_entries(invoice_name):
		frappe.db.set_value(
			"Payment Ledger Entry",
			entry.name,
			{"posting_date": posting_date, "due_date": due_date},
			update_modified=False,
		)

	for entry in get_gl_entries(invoice_name):
		frappe.db.set_value(
			"GL Entry",
			entry.name,
			"posting_date",
			posting_date,
			update_modified=False,
		)


class AgeingCorrectionReport:
	def __init__(self):
		self.corrected = []
		self.already_correct = []
		self.not_found = []
		self.ambiguous = []
		self.blocked = []

	def add(self, status, row):
		getattr(self, status).append(row)

	def as_dict(self):
		return {
			"corrected": self.corrected,
			"already_correct": self.already_correct,
			"not_found": self.not_found,
			"ambiguous": self.ambiguous,
			"blocked": self.blocked,
		}

	def log_summary(self):
		summary = self.as_dict()
		message = (
			"Sales Invoice ageing date correction: "
			f"corrected={len(summary['corrected'])}, "
			f"already_correct={len(summary['already_correct'])}, "
			f"not_found={len(summary['not_found'])}, "
			f"ambiguous={len(summary['ambiguous'])}, "
			f"blocked={len(summary['blocked'])}"
		)
		frappe.logger("redtra_customisation").info(message)
		print(message)
