# Copyright (c) 2026, redtra_customisation contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
import erpnext
from erpnext.accounts.doctype.journal_entry.journal_entry import get_exchange_rate
from erpnext.accounts.party import get_party_account, get_party_account_currency
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CashBankEntry(Document):
	def validate(self):
		self.set_journal_naming_series()
		self.set_row_amounts()
		self.set_multi_currency_flag()
		self.validate_accounts()
		self.validate_parties()
		self.validate_taxes()
		self.validate_invoice_references()
		self.validate_settlement_mode()
		self.set_total_amount()

	def before_insert(self):
		if not self.status:
			self.status = "Draft"
		self.set_journal_naming_series()

	def set_journal_naming_series(self):
		options = get_journal_naming_series_options()
		if not self.journal_naming_series:
			self.journal_naming_series = get_default_journal_naming_series(
				self.account_type, self.entry_type, options
			)
		if self.journal_naming_series not in options:
			frappe.throw(
				_("Journal Series {0} is not valid. Allowed: {1}").format(
					frappe.bold(self.journal_naming_series),
					", ".join(options),
				)
			)

	def on_submit(self):
		if self.settlement_mode == "Payment Entry":
			pe = make_payment_entry_from_cbe(self)
			pe.insert()
			pe.submit()
			self.db_set("payment_entry", pe.name, update_modified=False)
		else:
			je = make_journal_entry_from_cbe(self)
			je.insert()
			je.submit()
			self.db_set("journal_entry", je.name, update_modified=False)
		self.db_set("status", "Submitted", update_modified=False)

	def before_cancel(self):
		if self.journal_entry:
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
		if self.payment_entry:
			pe = frappe.get_doc("Payment Entry", self.payment_entry)
			if pe.docstatus == 1:
				pe.cancel()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def set_row_amounts(self):
		for row in self.get("accounts") or []:
			if not flt(row.allocated_amount) and row.reference_name:
				row.allocated_amount = flt(row.amount)
			row.amount_in_company_currency = flt(row.amount) * flt(row.exchange_rate or 1)
			if not flt(row.tax_amount):
				row.tax_amount = compute_tax_amount(
					row, self.entry_type, flt(row.amount), self.company
				)

	def set_multi_currency_flag(self):
		company_currency = erpnext.get_company_currency(self.company)
		multi = 0
		if self.paid_account_currency and self.paid_account_currency != company_currency:
			multi = 1
		for row in self.get("accounts") or []:
			if row.account_currency and row.account_currency != company_currency:
				multi = 1
		self.multi_currency = multi

	def set_total_amount(self):
		total = 0.0
		for row in self.get("accounts") or []:
			total += flt(row.amount) * flt(row.exchange_rate or 1)
		self.amount = total

	def validate_accounts(self):
		if not self.get("accounts"):
			frappe.throw(_("Add at least one account line."))

		if not self.paid_account:
			frappe.throw(_("Paid Account is required."))

		paid_type = frappe.db.get_value("Account", self.paid_account, "account_type")
		if paid_type != self.account_type:
			frappe.throw(
				_("Paid Account {0} must be of type {1}.").format(
					frappe.bold(self.paid_account), self.account_type
				)
			)

		for row in self.get("accounts") or []:
			if not row.account:
				frappe.throw(_("Row {0}: Account is required.").format(row.idx))
			if flt(row.amount) <= 0:
				frappe.throw(_("Row {0}: Amount must be greater than zero.").format(row.idx))

			account_company = frappe.db.get_value("Account", row.account, "company")
			if account_company != self.company:
				frappe.throw(
					_("Row {0}: Account {1} does not belong to company {2}.").format(
						row.idx, row.account, self.company
					)
				)

			if self.multi_currency and flt(row.exchange_rate) <= 0:
				frappe.throw(_("Row {0}: Exchange Rate must be greater than zero.").format(row.idx))

		if self.multi_currency and flt(self.paid_account_exchange_rate) <= 0:
			frappe.throw(_("Paid Account Exchange Rate must be greater than zero."))

	def validate_parties(self):
		for row in self.get("accounts") or []:
			account_type = frappe.db.get_value("Account", row.account, "account_type")
			if account_type in ("Receivable", "Payable") and not (row.party_type and row.party):
				frappe.throw(
					_("Row {0}: Party is required for receivable/payable account {1}.").format(
						row.idx, row.account
					)
				)

			if row.party_type and row.party:
				expected = "Customer" if account_type == "Receivable" else "Supplier"
				if account_type in ("Receivable", "Payable") and row.party_type != expected:
					frappe.throw(
						_("Row {0}: Party Type must be {1} for account {2}.").format(
							row.idx, expected, row.account
						)
					)

	def validate_taxes(self):
		for row in self.get("accounts") or []:
			tax_amount = flt(row.tax_amount)
			if tax_amount <= 0:
				continue
			if not row.tax_account:
				frappe.throw(
					_("Row {0}: Tax Account is required when Tax Amount is set.").format(row.idx)
				)
			if tax_amount >= flt(row.amount):
				frappe.throw(
					_("Row {0}: Tax Amount must be less than line Amount.").format(row.idx)
				)

	def validate_invoice_references(self):
		for row in self.get("accounts") or []:
			if not row.reference_name:
				continue
			if not row.reference_doctype:
				frappe.throw(_("Row {0}: Reference Type is required when invoice is linked.").format(row.idx))

			invoice = frappe.db.get_value(
				row.reference_doctype,
				row.reference_name,
				["outstanding_amount", "docstatus", "company", "customer", "supplier"],
				as_dict=True,
			)
			if not invoice or invoice.docstatus != 1:
				frappe.throw(
					_("Row {0}: {1} {2} is not a submitted invoice.").format(
						row.idx, row.reference_doctype, row.reference_name
					)
				)
			if invoice.company != self.company:
				frappe.throw(_("Row {0}: Invoice company does not match.").format(row.idx))

			party_field = "customer" if row.reference_doctype == "Sales Invoice" else "supplier"
			expected_party = invoice.get(party_field)
			if row.party and row.party != expected_party:
				frappe.throw(
					_("Row {0}: Party {1} does not match invoice party {2}.").format(
						row.idx, row.party, expected_party
					)
				)

			allocated = flt(row.allocated_amount) or flt(row.amount)
			outstanding = flt(invoice.outstanding_amount)
			if allocated > outstanding + 0.01:
				frappe.throw(
					_("Row {0}: Allocated amount {1} exceeds invoice outstanding {2}.").format(
						row.idx, allocated, outstanding
					),
					title=_("Allocation Exceeds Outstanding"),
				)

	def validate_settlement_mode(self):
		if self.settlement_mode != "Payment Entry":
			return
		if not self.mode_of_payment:
			frappe.throw(_("Mode of Payment is required for Payment Entry settlement."))
		if not is_pe_eligible(self):
			frappe.throw(
				_(
					"Payment Entry settlement requires a single party, party receivable/payable accounts only, "
					"and no mixed expense or income lines."
				),
				title=_("Payment Entry Not Eligible"),
			)


def is_pe_eligible(doc) -> bool:
	rows = doc.get("accounts") or []
	if not rows:
		return False

	parties = set()
	party_types = set()
	for row in rows:
		if not row.party_type or not row.party:
			return False
		parties.add(row.party)
		party_types.add(row.party_type)
		party_account = get_party_account(row.party_type, row.party, doc.company, include_advance=True)
		if row.account != party_account:
			return False

	if len(parties) != 1 or len(party_types) != 1:
		return False
	return True


def compute_tax_amount(row, entry_type: str, base_amount: float, company: str) -> float:
	base_amount = flt(base_amount)
	if base_amount <= 0:
		return 0.0

	template_name = row.purchase_tax_template if entry_type == "Payment" else row.sales_tax_template
	if template_name:
		return _tax_from_template(template_name, entry_type, base_amount, company)

	if flt(row.tax_rate):
		return flt(base_amount) * flt(row.tax_rate) / 100.0
	return 0.0


def _tax_from_template(template_name: str, entry_type: str, base_amount: float, company: str) -> float:
	template_doctype = (
		"Purchase Taxes and Charges Template"
		if entry_type == "Payment"
		else "Sales Taxes and Charges Template"
	)
	if not frappe.db.exists(template_doctype, template_name):
		return 0.0

	template = frappe.get_doc(template_doctype, template_name)
	if template.company and template.company != company:
		return 0.0

	total_tax = 0.0
	for tax_row in template.taxes or []:
		rate = flt(tax_row.rate)
		if rate:
			total_tax += flt(base_amount) * rate / 100.0
	return total_tax


def get_tax_lines(row, entry_type: str, base_amount: float, company: str) -> list[dict]:
	"""Return list of {account, amount} tax components for a row."""
	base_amount = flt(base_amount)
	template_name = row.purchase_tax_template if entry_type == "Payment" else row.sales_tax_template

	if template_name:
		template_doctype = (
			"Purchase Taxes and Charges Template"
			if entry_type == "Payment"
			else "Sales Taxes and Charges Template"
		)
		template = frappe.get_doc(template_doctype, template_name)
		lines = []
		for tax_row in template.taxes or []:
			rate = flt(tax_row.rate)
			if not rate:
				continue
			amount = flt(base_amount) * rate / 100.0
			if amount <= 0:
				continue
			lines.append({"account": tax_row.account_head, "amount": amount, "rate": rate})
		if lines:
			return lines

	if flt(row.tax_amount) and row.tax_account:
		return [{"account": row.tax_account, "amount": flt(row.tax_amount), "rate": flt(row.tax_rate)}]

	if flt(row.tax_rate) and row.tax_account:
		amount = flt(base_amount) * flt(row.tax_rate) / 100.0
		if amount > 0:
			return [{"account": row.tax_account, "amount": amount, "rate": flt(row.tax_rate)}]

	return []


def make_journal_entry_from_cbe(doc):
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Bank Entry" if doc.account_type == "Bank" else "Cash Entry"
	je.naming_series = doc.journal_naming_series or get_default_journal_naming_series(
		doc.account_type, doc.entry_type, get_journal_naming_series_options()
	)
	je.company = doc.company
	je.posting_date = doc.posting_date
	je.cheque_no = doc.reference
	je.cheque_date = doc.reference_date
	je.user_remark = doc.user_remark or f"Cash/Bank Entry {doc.name}"
	if hasattr(je, "custom_cash_bank_entry"):
		je.custom_cash_bank_entry = doc.name
	if doc.multi_currency:
		je.multi_currency = 1

	total_debit_company = 0.0
	total_credit_company = 0.0
	is_payment = doc.entry_type == "Payment"

	for row in doc.get("accounts") or []:
		gross = flt(row.amount)
		exchange_rate = flt(row.exchange_rate) or 1
		tax_lines = get_tax_lines(row, doc.entry_type, gross, doc.company)
		tax_total = sum(flt(t["amount"]) for t in tax_lines)
		if not tax_total and flt(row.tax_amount):
			tax_total = flt(row.tax_amount)
			if row.tax_account and not tax_lines:
				tax_lines = [{"account": row.tax_account, "amount": tax_total, "rate": flt(row.tax_rate)}]
		net = gross - tax_total

		line_kwargs = {
			"party_type": row.party_type,
			"party": row.party,
			"cost_center": row.cost_center or doc.cost_center,
			"project": row.project or doc.project,
			"user_remark": row.remark,
		}
		party_line_amount = net
		if row.reference_name:
			line_kwargs["reference_type"] = row.reference_doctype
			line_kwargs["reference_name"] = row.reference_name
			party_line_amount = flt(row.allocated_amount) or net

		if is_payment:
			_append_je_line(je, row.account, party_line_amount, exchange_rate, debit=True, **line_kwargs)
			total_debit_company += party_line_amount * exchange_rate
			for tax_line in tax_lines:
				_append_je_line(
					je, tax_line["account"], tax_line["amount"], exchange_rate, debit=True, **line_kwargs
				)
				total_debit_company += flt(tax_line["amount"]) * exchange_rate
		else:
			_append_je_line(je, row.account, party_line_amount, exchange_rate, debit=False, **line_kwargs)
			total_credit_company += party_line_amount * exchange_rate
			for tax_line in tax_lines:
				_append_je_line(
					je, tax_line["account"], tax_line["amount"], exchange_rate, debit=False, **line_kwargs
				)
				total_credit_company += flt(tax_line["amount"]) * exchange_rate

	paid_exchange = flt(doc.paid_account_exchange_rate) or 1
	if is_payment:
		credit_company = total_debit_company
		credit_in_account = credit_company / paid_exchange if paid_exchange else credit_company
		_append_je_line(
			je,
			doc.paid_account,
			credit_in_account,
			paid_exchange,
			debit=False,
			cost_center=doc.cost_center,
			project=doc.project,
		)
	else:
		debit_company = total_credit_company
		debit_in_account = debit_company / paid_exchange if paid_exchange else debit_company
		_append_je_line(
			je,
			doc.paid_account,
			debit_in_account,
			paid_exchange,
			debit=True,
			cost_center=doc.cost_center,
			project=doc.project,
		)

	return je


def _append_je_line(je, account, amount_in_account_currency, exchange_rate, debit=True, **kwargs):
	amount_in_account_currency = flt(amount_in_account_currency)
	if amount_in_account_currency <= 0:
		return

	account_currency = frappe.db.get_value("Account", account, "account_currency")
	row = je.append("accounts", {"account": account, "exchange_rate": flt(exchange_rate) or 1})
	if account_currency:
		row.account_currency = account_currency

	for key, value in kwargs.items():
		if value:
			row.set(key, value)

	if debit:
		row.debit_in_account_currency = amount_in_account_currency
	else:
		row.credit_in_account_currency = amount_in_account_currency


def make_payment_entry_from_cbe(doc):
	first_row = doc.accounts[0]
	party_type = first_row.party_type
	party = first_row.party
	party_account = get_party_account(party_type, party, doc.company, include_advance=True)

	total_amount = sum(flt(row.amount) * flt(row.exchange_rate or 1) for row in doc.accounts)

	pe = frappe.new_doc("Payment Entry")
	if hasattr(pe, "custom_cash_bank_entry"):
		pe.custom_cash_bank_entry = doc.name

	pe.company = doc.company
	pe.project = doc.project
	pe.cost_center = doc.cost_center
	if hasattr(pe, "department"):
		pe.department = doc.department
	pe.payment_type = "Receive" if doc.entry_type == "Receipt" else "Pay"
	pe.party_type = party_type
	pe.party = party
	pe.party_name = frappe.db.get_value(party_type, party, "customer_name" if party_type == "Customer" else "supplier_name")
	pe.mode_of_payment = doc.mode_of_payment
	pe.posting_date = doc.posting_date
	pe.reference_no = doc.reference
	pe.reference_date = doc.reference_date

	if doc.entry_type == "Receipt":
		pe.paid_from = party_account
		pe.paid_to = doc.paid_account
		pe.received_amount = total_amount
		pe.paid_amount = total_amount
	else:
		pe.paid_from = doc.paid_account
		pe.paid_to = party_account
		pe.paid_amount = total_amount
		pe.received_amount = total_amount

	acc_currency = get_party_account_currency(party_type, party, doc.company)
	if acc_currency:
		pe.paid_from_account_currency = acc_currency
		pe.paid_to_account_currency = acc_currency

	for row in doc.accounts:
		if not row.reference_name:
			continue
		outstanding = flt(
			frappe.db.get_value(row.reference_doctype, row.reference_name, "outstanding_amount")
		)
		grand_total = flt(
			frappe.db.get_value(row.reference_doctype, row.reference_name, "grand_total")
		)
		allocated = flt(row.allocated_amount) or flt(row.amount)
		pe.append(
			"references",
			{
				"reference_doctype": row.reference_doctype,
				"reference_name": row.reference_name,
				"total_amount": grand_total,
				"outstanding_amount": outstanding,
				"allocated_amount": allocated,
			},
		)

	return pe


def get_journal_naming_series_options() -> list[str]:
	options = frappe.get_meta("Journal Entry").get_field("naming_series").options or ""
	return [opt.strip() for opt in options.split("\n") if opt.strip()]


def get_default_journal_naming_series(account_type: str, entry_type: str, options: list[str] | None = None) -> str:
	options = options or get_journal_naming_series_options()
	if not options:
		return "ACC-JV-.YYYY.-"

	preferred_prefixes = []
	if entry_type == "Receipt":
		preferred_prefixes.extend(["ACC-REC", "R-V"])
	else:
		preferred_prefixes.extend(["ACC-JVPAY", "ACC-BANK", "P-V"])

	if account_type == "Cash":
		preferred_prefixes.extend(["ACC-CASH"])
	elif account_type == "Bank":
		preferred_prefixes.extend(["ACC-BANK"])

	preferred_prefixes.append("ACC-JV")

	for prefix in preferred_prefixes:
		for option in options:
			if option.startswith(prefix):
				return option
	return options[0]


@frappe.whitelist()
def get_default_journal_naming_series_for_cbe(account_type="Bank", entry_type="Payment"):
	return get_default_journal_naming_series(account_type, entry_type)


@frappe.whitelist()
def get_journal_naming_series():
	return {
		"options": get_journal_naming_series_options(),
		"default": get_default_journal_naming_series("Bank", "Payment"),
	}


@frappe.whitelist()
def get_exchange_rate_for_row(
	posting_date,
	account,
	company,
	account_currency=None,
	reference_type=None,
	reference_name=None,
	debit=None,
	credit=None,
	exchange_rate=None,
):
	return get_exchange_rate(
		posting_date,
		account=account,
		account_currency=account_currency,
		company=company,
		reference_type=reference_type,
		reference_name=reference_name,
		debit=debit,
		credit=credit,
		exchange_rate=exchange_rate,
	)


@frappe.whitelist()
def get_tax_from_template(template, amount, entry_type, company=None):
	amount = flt(amount)
	if not template or amount <= 0:
		return {"tax_amount": 0, "tax_account": None, "tax_lines": []}

	row = frappe._dict(
		{
			"purchase_tax_template": template if entry_type == "Payment" else None,
			"sales_tax_template": template if entry_type == "Receipt" else None,
			"tax_account": None,
			"tax_rate": 0,
			"tax_amount": 0,
		}
	)
	tax_amount = compute_tax_amount(row, entry_type, amount, company)
	tax_lines = get_tax_lines(row, entry_type, amount, company)
	tax_account = tax_lines[0]["account"] if tax_lines else None
	return {"tax_amount": tax_amount, "tax_account": tax_account, "tax_lines": tax_lines}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_invoices_for_cbe(doctype, txt, searchfield, start, page_len, filters):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if not filters:
		filters = {}

	reference_doctype = filters.get("reference_doctype") or doctype
	company = filters.get("company")
	party = filters.get("party")

	if reference_doctype not in ("Sales Invoice", "Purchase Invoice"):
		return []
	if not company or not party:
		return []

	party_field = "customer" if reference_doctype == "Sales Invoice" else "supplier"
	search_txt = (txt or "").strip()
	start = int(start or 0)
	page_len = int(page_len or 20)

	query = f"""
		SELECT
			inv.name,
			inv.grand_total,
			inv.outstanding_amount,
			inv.outstanding_amount AS remaining_allocatable
		FROM `tab{reference_doctype}` inv
		WHERE inv.docstatus = 1
			AND inv.company = %(company)s
			AND inv.{party_field} = %(party)s
			AND inv.outstanding_amount > 0.009
	"""
	values = {"company": company, "party": party}

	if search_txt:
		if reference_doctype == "Purchase Invoice":
			query += """
				AND (
					inv.name LIKE %(txt)s
					OR IFNULL(inv.custom_supplier_invoice_no, '') LIKE %(txt)s
				)
			"""
		else:
			query += " AND inv.name LIKE %(txt)s"
		values["txt"] = f"%{search_txt}%"

	query += """
		ORDER BY inv.posting_date DESC, inv.name DESC
		LIMIT %(start)s, %(page_len)s
	"""
	values["start"] = start
	values["page_len"] = page_len

	return frappe.db.sql(query, values, as_dict=True)


@frappe.whitelist()
def get_cbe_invoice_details(reference_doctype, invoices):
	if isinstance(invoices, str):
		invoices = frappe.parse_json(invoices)
	invoices = list(dict.fromkeys(invoices or []))

	if reference_doctype not in ("Sales Invoice", "Purchase Invoice") or not invoices:
		return []

	fields = ["name", "grand_total", "outstanding_amount"]
	rows = frappe.get_all(
		reference_doctype,
		filters={"name": ["in", invoices], "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=fields,
		order_by="posting_date desc, name desc",
	)
	for row in rows:
		row["remaining_allocatable"] = flt(row.outstanding_amount)
	return rows
