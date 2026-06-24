# Copyright (c) 2026, redtra_customisation contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
import erpnext
from erpnext.accounts.doctype.journal_entry.journal_entry import get_exchange_rate
from erpnext.accounts.party import get_party_account, get_party_account_currency
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


def get_allowed_party_accounts(company, party_type, party):
	accounts = []
	if not party_type or not party:
		return accounts

	# 1. Standard party account (Customer/Supplier -> Group -> Company default)
	party_account = get_party_account(party_type, party, company, include_advance=True)
	if isinstance(party_account, list):
		accounts.extend(party_account)
	elif party_account:
		accounts.append(party_account)

	# 2. Customer/Supplier Group accounts (to allow fallback when customer master overrides it)
	if party_type in ["Customer", "Supplier"]:
		party_group_doctype = "Customer Group" if party_type == "Customer" else "Supplier Group"
		group = frappe.get_cached_value(party_type, party, frappe.scrub(party_group_doctype))
		if group:
			group_account = frappe.db.get_value(
				"Party Account",
				{"parenttype": party_group_doctype, "parent": group, "company": company},
				"account",
			)
			if group_account:
				accounts.append(group_account)

			group_advance = frappe.db.get_value(
				"Party Account",
				{"parenttype": party_group_doctype, "parent": group, "company": company},
				"advance_account",
			)
			if group_advance:
				accounts.append(group_advance)

	# 3. Company default accounts
	default_field = "default_receivable_account" if party_type == "Customer" else "default_payable_account"
	company_default = frappe.get_cached_value("Company", company, default_field)
	if company_default:
		accounts.append(company_default)

	# 4. All active, non-group accounts of the matching type for the company
	expected_account_type = "Receivable" if party_type == "Customer" else "Payable"
	party_type_accounts = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"account_type": expected_account_type,
			"is_group": 0,
			"disabled": 0,
		},
		pluck="name"
	)
	accounts.extend(party_type_accounts)

	# 5. All active, non-group Current Asset accounts if allow_party_on_current_asset setting is checked
	allow_party = False
	try:
		allow_party = frappe.db.get_single_value("Redtra Custom Setting", "allow_party_on_current_asset")
	except Exception:
		pass

	if allow_party:
		asset_accounts = frappe.get_all(
			"Account",
			filters={
				"company": company,
				"account_type": "Current Asset",
				"is_group": 0,
				"disabled": 0,
			},
			pluck="name"
		)
		accounts.extend(asset_accounts)

	return list(set(acc for acc in accounts if acc))


class CashBankEntry(Document):
	def validate(self):
		self.sync_invoice_reference_account_rows()
		self.set_journal_naming_series()
		self.set_invoice_accounts()
		self.set_row_amounts()
		self.set_multi_currency_flag()
		self.validate_accounts()
		self.validate_parties()
		self.validate_taxes()
		self.validate_invoice_references()
		self.validate_settlement_mode()
		self.set_total_amount()

	def set_invoice_accounts(self):
		for row in self.get("accounts") or []:
			refs = get_invoice_refs_for_cbe_row(self, row)
			target_refs = refs or ([row] if row.reference_name and row.reference_doctype else [])
			for ref in target_refs:
				ref_doctype = ref.reference_doctype if hasattr(ref, "reference_doctype") else ref.get("reference_doctype")
				ref_name = ref.reference_name if hasattr(ref, "reference_name") else ref.get("reference_name")
				if not ref_name or not ref_doctype:
					continue
				acc_field = "debit_to" if ref_doctype == "Sales Invoice" else "credit_to"
				inv_acc = frappe.db.get_value(ref_doctype, ref_name, acc_field)
				if inv_acc and row.account != inv_acc:
					row.account = inv_acc
					row.account_currency = frappe.db.get_value("Account", inv_acc, "account_currency")
					break

		for row in self.get("accounts") or []:
			if row.account and not row.account_currency:
				row.account_currency = frappe.db.get_value("Account", row.account, "account_currency")


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
			created_pes = []
			for row in self.get("accounts") or []:
				pe = make_payment_entry_from_cbe_row(self, row)
				pe.insert()
				pe.submit()
				row.db_set("payment_entry", pe.name, update_modified=False)
				created_pes.append(pe.name)
			if created_pes:
				self.db_set("payment_entry", created_pes[0], update_modified=False)

		elif self.settlement_mode == "Post Dated Cheque":
			created_pdcs = []
			for row in self.get("accounts") or []:
				pdc = make_pdc_from_cbe_row(self, row)
				pdc.insert()
				pdc.submit()
				row.db_set("post_dated_cheque", pdc.name, update_modified=False)
				created_pdcs.append(pdc.name)
			if created_pdcs:
				self.db_set("post_dated_cheque", created_pdcs[0], update_modified=False)

		else:
			je = make_journal_entry_from_cbe(self)
			je.insert()
			je.submit()
			self.db_set("journal_entry", je.name, update_modified=False)
		self.db_set("status", "Submitted", update_modified=False)

	def before_cancel(self):
		linked_pes = set()
		if self.payment_entry:
			linked_pes.add(self.payment_entry)
		for row in self.get("accounts") or []:
			if row.get("payment_entry"):
				linked_pes.add(row.payment_entry)

		linked_pdcs = set()
		if self.get("post_dated_cheque"):
			linked_pdcs.add(self.post_dated_cheque)
		for row in self.get("accounts") or []:
			if row.get("post_dated_cheque"):
				linked_pdcs.add(row.post_dated_cheque)

		je_name = self.journal_entry

		# Clear references in database to bypass LinkExistsError
		if self.journal_entry:
			self.db_set("journal_entry", None, update_modified=False)
		if self.payment_entry:
			self.db_set("payment_entry", None, update_modified=False)
		if self.get("post_dated_cheque"):
			self.db_set("post_dated_cheque", None, update_modified=False)

		for row in self.get("accounts") or []:
			if row.get("payment_entry"):
				row.db_set("payment_entry", None, update_modified=False)
			if row.get("post_dated_cheque"):
				row.db_set("post_dated_cheque", None, update_modified=False)

		if je_name and frappe.db.exists("Journal Entry", je_name):
			je = frappe.get_doc("Journal Entry", je_name)
			if je.docstatus == 1:
				je.cancel()

		for pe_name in linked_pes:
			if frappe.db.exists("Payment Entry", pe_name):
				pe = frappe.get_doc("Payment Entry", pe_name)
				if pe.docstatus == 1:
					pe.cancel()

		for pdc_name in linked_pdcs:
			if frappe.db.exists("Post Dated Cheques", pdc_name):
				pdc = frappe.get_doc("Post Dated Cheques", pdc_name)
				if pdc.docstatus == 1:
					pdc.cancel()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def set_row_amounts(self):
		for row in self.get("accounts") or []:
			refs = get_invoice_refs_for_cbe_row(self, row)
			if refs:
				total_allocated = sum(flt(ref.allocated_amount) for ref in refs)
				row.amount = total_allocated
				row.allocated_amount = total_allocated
				first_ref = refs[0]
				row.reference_doctype = first_ref.reference_doctype
				row.reference_name = first_ref.reference_name
			elif not flt(row.allocated_amount) and row.reference_name:
				row.allocated_amount = flt(row.amount)
			row.amount_in_company_currency = flt(row.amount) * flt(row.exchange_rate or 1)
			if not flt(row.tax_amount):
				row.tax_amount = compute_tax_amount(
					row, self.entry_type, flt(row.amount), self.company
				)

	def set_multi_currency_flag(self):
		company_currency = erpnext.get_company_currency(self.company)
		multi = 0
		if self.paid_account:
			paid_currency = self.paid_account_currency or frappe.db.get_value(
				"Account", self.paid_account, "account_currency"
			)
			if paid_currency:
				self.paid_account_currency = paid_currency
			if paid_currency and paid_currency != company_currency:
				multi = 1
		for row in self.get("accounts") or []:
			row_currency = row.account_currency
			if not row_currency and row.account:
				row_currency = frappe.db.get_value("Account", row.account, "account_currency")
				if row_currency:
					row.account_currency = row_currency
			if row_currency and row_currency != company_currency:
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
		if self.settlement_mode not in ("Payment Entry", "Post Dated Cheque"):
			return

		seen_by_row = {}
		for inv_ref in self.get("invoice_references") or []:
			if not inv_ref.reference_name or not inv_ref.reference_doctype:
				continue
			if not inv_ref.account_row:
				frappe.throw(_("Invoice Reference row {0}: Account line link is missing.").format(inv_ref.idx))

			account_row = self._get_account_row_for_invoice_ref(inv_ref)
			if not account_row:
				frappe.throw(
					_("Invoice Reference row {0}: Linked account line no longer exists.").format(inv_ref.idx)
				)

			row_key = account_row.name
			seen_by_row.setdefault(row_key, set())
			if inv_ref.reference_name in seen_by_row[row_key]:
				frappe.throw(
					_("Line {0}: Invoice {1} is linked more than once.").format(
						account_row.idx, inv_ref.reference_name
					)
				)
			seen_by_row[row_key].add(inv_ref.reference_name)

			self._validate_single_invoice_reference(
				account_row,
				inv_ref.reference_doctype,
				inv_ref.reference_name,
				flt(inv_ref.allocated_amount),
			)

		for row in self.get("accounts") or []:
			child_refs = get_invoice_refs_for_cbe_row(self, row)
			if child_refs:
				total_allocated = sum(flt(ref.allocated_amount) for ref in child_refs)
				if abs(total_allocated - flt(row.amount)) > 0.01:
					frappe.throw(
						_("Row {0}: Line amount {1} must equal total invoice allocations {2}.").format(
							row.idx, flt(row.amount), total_allocated
						)
					)
				continue

			if not row.reference_name:
				continue
			if not row.reference_doctype:
				frappe.throw(_("Row {0}: Reference Type is required when invoice is linked.").format(row.idx))

			allocated = flt(row.allocated_amount) or flt(row.amount)
			self._validate_single_invoice_reference(
				row, row.reference_doctype, row.reference_name, allocated
			)

	def sync_invoice_reference_account_rows(self):
		"""Re-link invoice refs when account row names change on first save."""
		if self.settlement_mode not in ("Payment Entry", "Post Dated Cheque"):
			return

		account_rows = list(self.get("accounts") or [])
		by_name = {row.name: row for row in account_rows}
		by_idx = {row.idx: row for row in account_rows}
		orphaned = []

		for inv_ref in self.get("invoice_references") or []:
			if inv_ref.account_row and inv_ref.account_row in by_name:
				inv_ref.account_row_idx = by_name[inv_ref.account_row].idx
				continue

			if inv_ref.account_row_idx and inv_ref.account_row_idx in by_idx:
				inv_ref.account_row = by_idx[inv_ref.account_row_idx].name
				continue

			orphaned.append(inv_ref)

		for inv_ref in orphaned:
			self.remove(inv_ref)

	def _get_account_row_for_invoice_ref(self, inv_ref):
		for row in self.get("accounts") or []:
			if row.name == inv_ref.account_row:
				return row
		if inv_ref.account_row_idx:
			for row in self.get("accounts") or []:
				if row.idx == inv_ref.account_row_idx:
					return row
		return None

	def _get_account_row_by_name(self, account_row_name):
		for row in self.get("accounts") or []:
			if row.name == account_row_name:
				return row
		return None

	def _validate_single_invoice_reference(self, account_row, reference_doctype, reference_name, allocated):
		party_field = "customer" if reference_doctype == "Sales Invoice" else "supplier"
		invoice = frappe.db.get_value(
			reference_doctype,
			reference_name,
			["outstanding_amount", "docstatus", "company", party_field],
			as_dict=True,
		)
		if not invoice or invoice.docstatus != 1:
			frappe.throw(
				_("Row {0}: {1} {2} is not a submitted invoice.").format(
					account_row.idx, reference_doctype, reference_name
				)
			)
		if invoice.company != self.company:
			frappe.throw(_("Row {0}: Invoice company does not match.").format(account_row.idx))

		expected_party = invoice.get(party_field)
		if account_row.party and account_row.party != expected_party:
			frappe.throw(
				_("Row {0}: Party {1} does not match invoice party {2}.").format(
					account_row.idx, account_row.party, expected_party
				)
			)

		remaining = get_remaining_allocatable(
			reference_doctype,
			reference_name,
			current_cbe=self.name if not self.is_new() else None,
		)
		if allocated > remaining + 0.01:
			frappe.throw(
				_("Row {0}: Allocated amount {1} exceeds remaining allocatable {2} for {3}.").format(
					account_row.idx, allocated, remaining, reference_name
				),
				title=_("Allocation Exceeds Outstanding"),
			)

	def validate_settlement_mode(self):
		if self.settlement_mode not in ("Payment Entry", "Post Dated Cheque"):
			return

		if self.settlement_mode == "Payment Entry" and not self.mode_of_payment:
			frappe.throw(_("Mode of Payment is required for Payment Entry settlement."))

		for row in self.get("accounts") or []:
			if not row.party_type or not row.party:
				frappe.throw(
					_("Row {0}: Party Type and Party are required for {1} settlement.").format(
						row.idx, self.settlement_mode
					)
				)
			allowed_accounts = get_allowed_party_accounts(self.company, row.party_type, row.party)
			if row.account not in allowed_accounts:
				frappe.throw(
					_("Row {0}: Account {1} does not match the party account(s) {2}.").format(
						row.idx, frappe.bold(row.account), ", ".join(frappe.bold(a) for a in allowed_accounts)
					)
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
		allowed_accounts = get_allowed_party_accounts(doc.company, row.party_type, row.party)
		if row.account not in allowed_accounts:
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
	party_account = first_row.account

	total_amount = sum(flt(row.amount) * flt(row.exchange_rate or 1) for row in doc.accounts)

	pe = frappe.new_doc("Payment Entry")
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


def make_payment_entry_from_cbe_row(doc, row):
	party_type = row.party_type
	party = row.party
	party_account = row.account
	row_amount = flt(row.amount)

	pe = frappe.new_doc("Payment Entry")
	pe.company = doc.company
	pe.project = row.project or doc.project
	pe.cost_center = row.cost_center or doc.cost_center
	if hasattr(pe, "department"):
		pe.department = row.department or doc.department
	pe.payment_type = "Receive" if doc.entry_type == "Receipt" else "Pay"
	pe.party_type = party_type
	pe.party = party
	pe.party_name = frappe.db.get_value(party_type, party, "customer_name" if party_type == "Customer" else "supplier_name")
	pe.mode_of_payment = doc.mode_of_payment
	pe.posting_date = row.get("posting_date") or doc.posting_date
	pe.reference_no = row.get("reference_no") or doc.reference
	pe.reference_date = row.get("reference_date") or doc.reference_date

	if doc.entry_type == "Receipt":
		pe.paid_from = party_account
		pe.paid_to = doc.paid_account
		pe.received_amount = row_amount
		pe.paid_amount = row_amount
	else:
		pe.paid_from = doc.paid_account
		pe.paid_to = party_account
		pe.paid_amount = row_amount
		pe.received_amount = row_amount

	acc_currency = get_party_account_currency(party_type, party, doc.company)
	if acc_currency:
		pe.paid_from_account_currency = acc_currency
		pe.paid_to_account_currency = acc_currency

	refs = get_invoice_refs_for_cbe_row(doc, row)
	if refs:
		for inv_ref in refs:
			_append_pe_invoice_reference(pe, inv_ref)
	elif row.reference_name:
		_append_pe_invoice_reference(
			pe,
			frappe._dict(
				{
					"reference_doctype": row.reference_doctype,
					"reference_name": row.reference_name,
					"total_amount": None,
					"outstanding_amount": None,
					"allocated_amount": flt(row.allocated_amount) or flt(row.amount),
				}
			),
		)

	return pe


def _append_pe_invoice_reference(pe, inv_ref):
	outstanding = flt(
		frappe.db.get_value(inv_ref.reference_doctype, inv_ref.reference_name, "outstanding_amount")
	)
	grand_total = flt(
		frappe.db.get_value(inv_ref.reference_doctype, inv_ref.reference_name, "grand_total")
	)
	pe.append(
		"references",
		{
			"reference_doctype": inv_ref.reference_doctype,
			"reference_name": inv_ref.reference_name,
			"total_amount": flt(inv_ref.total_amount) or grand_total,
			"outstanding_amount": flt(inv_ref.outstanding_amount) or outstanding,
			"allocated_amount": flt(inv_ref.allocated_amount),
		},
	)


def make_pdc_from_cbe_row(doc, row):
	party_type = row.party_type
	party = row.party
	row_amount = flt(row.amount)

	pdc = frappe.new_doc("Post Dated Cheques")
	pdc.company = doc.company
	pdc.project = row.project or doc.project
	pdc.cost_center = row.cost_center or doc.cost_center
	pdc.department = row.department or doc.department
	pdc.posting_date = row.get("posting_date") or doc.posting_date
	pdc.payment_type = "Receive" if doc.entry_type == "Receipt" else "Pay"
	pdc.party_type = party_type
	pdc.party = party
	pdc.party_name = frappe.db.get_value(party_type, party, "customer_name" if party_type == "Customer" else "supplier_name")
	pdc.mode_of_payment = doc.mode_of_payment
	pdc.reference_no = row.get("reference_no") or doc.reference
	pdc.reference_date = row.get("reference_date") or doc.reference_date
	pdc.amount = row_amount
	pdc.bank_account = doc.paid_account

	refs = get_invoice_refs_for_cbe_row(doc, row)
	if refs:
		for inv_ref in refs:
			_append_pdc_invoice_reference(pdc, inv_ref)
	elif row.reference_name:
		_append_pdc_invoice_reference(
			pdc,
			frappe._dict(
				{
					"reference_doctype": row.reference_doctype,
					"reference_name": row.reference_name,
					"total_amount": None,
					"outstanding_amount": None,
					"allocated_amount": flt(row.allocated_amount) or flt(row.amount),
				}
			),
		)
	return pdc


def _append_pdc_invoice_reference(pdc, inv_ref):
	outstanding = flt(
		frappe.db.get_value(inv_ref.reference_doctype, inv_ref.reference_name, "outstanding_amount")
	)
	grand_total = flt(
		frappe.db.get_value(inv_ref.reference_doctype, inv_ref.reference_name, "grand_total")
	)
	pdc.append(
		"invoice_references",
		{
			"reference_doctype": inv_ref.reference_doctype,
			"reference_name": inv_ref.reference_name,
			"total_amount": flt(inv_ref.total_amount) or grand_total,
			"outstanding_amount": flt(inv_ref.outstanding_amount) or outstanding,
			"allocated_amount": flt(inv_ref.allocated_amount),
		},
	)


def get_invoice_refs_for_cbe_row(doc, row):
	child_refs = [
		ref
		for ref in doc.get("invoice_references") or []
		if ref.reference_name
		and (ref.account_row == row.name or cint(ref.account_row_idx) == cint(row.idx))
	]
	if child_refs:
		for ref in child_refs:
			if ref.account_row != row.name:
				ref.account_row = row.name
			if cint(ref.account_row_idx) != cint(row.idx):
				ref.account_row_idx = row.idx
		return child_refs
	return []


def _scaled_pdc_allocation_subquery(reference_doctype: str, current_pdc: str = "") -> str:
	return f"""
		COALESCE((
			SELECT SUM(
				CASE
					WHEN pdc_totals.total_alloc > IFNULL(pdc.amount, 0)
						AND pdc_totals.total_alloc > 0
						AND IFNULL(pdc.amount, 0) > 0
					THEN ref.allocated_amount * pdc.amount / pdc_totals.total_alloc
					ELSE ref.allocated_amount
				END
			)
			FROM `tabPDC Invoice Reference` ref
			INNER JOIN `tabPost Dated Cheques` pdc ON pdc.name = ref.parent
			INNER JOIN (
				SELECT parent, SUM(allocated_amount) AS total_alloc
				FROM `tabPDC Invoice Reference`
				GROUP BY parent
			) pdc_totals ON pdc_totals.parent = ref.parent
			WHERE ref.reference_doctype = %(reference_doctype)s
				AND ref.reference_name = inv.name
				AND pdc.docstatus = 1
				AND IFNULL(pdc.status, '') != 'Cancelled'
				AND (%(current_pdc)s = '' OR pdc.name != %(current_pdc)s)
		), 0)
	"""


def _cbe_allocation_subquery(reference_doctype: str, current_cbe: str = "") -> str:
	return f"""
		COALESCE((
			SELECT SUM(ref.allocated_amount)
			FROM `tabCash Bank Entry Invoice Reference` ref
			INNER JOIN `tabCash Bank Entry` cbe ON cbe.name = ref.parent
			WHERE ref.reference_doctype = %(reference_doctype)s
				AND ref.reference_name = inv.name
				AND cbe.docstatus < 2
				AND IFNULL(cbe.status, '') != 'Cancelled'
				AND (%(current_cbe)s = '' OR cbe.name != %(current_cbe)s)
		), 0)
	"""


def get_remaining_allocatable(reference_doctype, invoice_name, current_cbe=None):
	if reference_doctype not in ("Sales Invoice", "Purchase Invoice") or not invoice_name:
		return 0

	outstanding = flt(frappe.db.get_value(reference_doctype, invoice_name, "outstanding_amount"))
	if outstanding <= 0:
		return 0

	pdc_reserved = flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(
				CASE
					WHEN pdc_totals.total_alloc > IFNULL(pdc.amount, 0)
						AND pdc_totals.total_alloc > 0
						AND IFNULL(pdc.amount, 0) > 0
					THEN ref.allocated_amount * pdc.amount / pdc_totals.total_alloc
					ELSE ref.allocated_amount
				END
			), 0)
			FROM `tabPDC Invoice Reference` ref
			INNER JOIN `tabPost Dated Cheques` pdc ON pdc.name = ref.parent
			INNER JOIN (
				SELECT parent, SUM(allocated_amount) AS total_alloc
				FROM `tabPDC Invoice Reference`
				GROUP BY parent
			) pdc_totals ON pdc_totals.parent = ref.parent
			WHERE ref.reference_doctype = %s
				AND ref.reference_name = %s
				AND pdc.docstatus = 1
				AND IFNULL(pdc.status, '') != 'Cancelled'
			""",
			(reference_doctype, invoice_name),
		)[0][0]
	)

	cbe_filters = {
		"reference_doctype": reference_doctype,
		"invoice_name": invoice_name,
		"current_cbe": current_cbe or "",
	}
	cbe_reserved = flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(ref.allocated_amount), 0)
			FROM `tabCash Bank Entry Invoice Reference` ref
			INNER JOIN `tabCash Bank Entry` cbe ON cbe.name = ref.parent
			WHERE ref.reference_doctype = %(reference_doctype)s
				AND ref.reference_name = %(invoice_name)s
				AND cbe.docstatus < 2
				AND IFNULL(cbe.status, '') != 'Cancelled'
				AND (%(current_cbe)s = '' OR cbe.name != %(current_cbe)s)
			""",
			cbe_filters,
		)[0][0]
	)

	return max(outstanding - pdc_reserved - cbe_reserved, 0)


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
def get_pending_invoices_for_cbe(company, party_type, party, current_cbe=None):
	if party_type not in ("Customer", "Supplier"):
		return []

	reference_doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
	party_field = "customer" if party_type == "Customer" else "supplier"
	pdc_subquery = _scaled_pdc_allocation_subquery(reference_doctype)
	cbe_subquery = _cbe_allocation_subquery(reference_doctype)

	supplier_invoice_expr = "COALESCE(inv.custom_supplier_invoice_no, '')"
	customer_invoice_expr = "COALESCE(inv.bill_no, '')"

	query = f"""
		SELECT
			inv.name,
			{supplier_invoice_expr if reference_doctype == "Purchase Invoice" else "''"} AS custom_supplier_invoice_no,
			{customer_invoice_expr if reference_doctype == "Sales Invoice" else "''"} AS custom_customer_invoice_no,
			inv.grand_total,
			inv.outstanding_amount,
			(inv.outstanding_amount - {pdc_subquery} - {cbe_subquery}) AS remaining_allocatable
		FROM `tab{reference_doctype}` inv
		WHERE inv.docstatus = 1
			AND inv.company = %(company)s
			AND inv.{party_field} = %(party)s
			AND inv.outstanding_amount > 0
		ORDER BY inv.posting_date DESC, inv.name DESC
	"""

	values = {
		"company": company,
		"party": party,
		"reference_doctype": reference_doctype,
		"current_pdc": "",
		"current_cbe": current_cbe or "",
	}

	rows = frappe.db.sql(query, values, as_dict=True)
	return [row for row in rows if flt(row.remaining_allocatable) > 0.009]


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
	current_cbe = filters.get("current_cbe") or ""
	pdc_subquery = _scaled_pdc_allocation_subquery(reference_doctype)
	cbe_subquery = _cbe_allocation_subquery(reference_doctype)

	query = f"""
		SELECT
			inv.name,
			inv.grand_total,
			inv.outstanding_amount,
			(inv.outstanding_amount - {pdc_subquery} - {cbe_subquery}) AS remaining_allocatable
		FROM `tab{reference_doctype}` inv
		WHERE inv.docstatus = 1
			AND inv.company = %(company)s
			AND inv.{party_field} = %(party)s
			AND inv.outstanding_amount > 0.009
	"""
	values = {
		"company": company,
		"party": party,
		"reference_doctype": reference_doctype,
		"current_pdc": "",
		"current_cbe": current_cbe,
	}

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
		HAVING remaining_allocatable > 0.009
		ORDER BY inv.posting_date DESC, inv.name DESC
		LIMIT %(start)s, %(page_len)s
	"""
	values["start"] = start
	values["page_len"] = page_len

	return frappe.db.sql(query, values, as_dict=False)


@frappe.whitelist()
def get_cbe_invoice_details(reference_doctype, invoices, current_cbe=None):
	if isinstance(invoices, str):
		invoices = frappe.parse_json(invoices)
	invoices = list(dict.fromkeys(invoices or []))

	if reference_doctype not in ("Sales Invoice", "Purchase Invoice") or not invoices:
		return []

	account_field = "debit_to" if reference_doctype == "Sales Invoice" else "credit_to"
	fields = ["name", "grand_total", "outstanding_amount", f"{account_field} as account"]
	rows = frappe.get_all(
		reference_doctype,
		filters={"name": ["in", invoices], "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=fields,
		order_by="posting_date desc, name desc",
	)
	for row in rows:
		row["remaining_allocatable"] = get_remaining_allocatable(
			reference_doctype, row.name, current_cbe=current_cbe
		)
	return [row for row in rows if flt(row.remaining_allocatable) > 0.009]
