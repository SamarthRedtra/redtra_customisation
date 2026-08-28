"""Petty cash voucher backed by one standard Payment Entry per expense line."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


SUPPORTED_PARTY_TYPES = ("Customer", "Supplier", "Employee", "Shareholder")
PARTY_NAME_FIELDS = {
	"Customer": "customer_name",
	"Supplier": "supplier_name",
	"Employee": "employee_name",
	"Shareholder": "title",
}


class PettyCashEntry(Document):
	def before_validate(self):
		self.set_default_cash_account()

	def before_insert(self):
		if not self.status:
			self.status = "Draft"

	def validate(self):
		self.set_line_dimensions()
		self.validate_party()
		self.validate_cash_account()
		self.validate_expense_lines()
		self.set_total_amount()

	def on_submit(self):
		payment_entries = []
		for line in self.expense_lines:
			payment_entry = make_payment_entry(self, line)
			payment_entry.insert(ignore_permissions=True)
			payment_entry.submit()
			line.db_set("payment_entry", payment_entry.name, update_modified=False)
			link_payment_entry_and_gl_entries(self.name, payment_entry.name)
			payment_entries.append(payment_entry.name)
		if payment_entries:
			self.db_set("payment_entry", payment_entries[0], update_modified=False)
		self.db_set("status", "Submitted", update_modified=False)

	def before_cancel(self):
		allow_petty_cash_entry_ledger_links_on_cancel(self)
		for line in self.expense_lines:
			if not line.payment_entry:
				continue
			payment_entry = frappe.get_doc("Payment Entry", line.payment_entry)
			validate_linked_payment_entry(self, line, payment_entry)
			if payment_entry.docstatus == 1:
				mark_petty_cash_entry_cancellation(payment_entry)
				payment_entry.cancel()

	def on_cancel(self):
		for line in self.expense_lines:
			if line.payment_entry:
				link_payment_entry_and_gl_entries(self.name, line.payment_entry)
		self.db_set("status", "Cancelled", update_modified=False)

	def set_line_dimensions(self):
		for line in self.expense_lines:
			for fieldname in ("project", "cost_center", "department"):
				if not line.get(fieldname) and self.get(fieldname):
					line.set(fieldname, self.get(fieldname))

	def set_default_cash_account(self):
		if self.cash_account:
			return

		default_account = "8100000 - Petty Cash - Administration - PIC"
		if frappe.db.exists("Account", {"name": default_account, "company": self.company}):
			self.cash_account = default_account

	def validate_party(self):
		if self.party_type not in SUPPORTED_PARTY_TYPES:
			frappe.throw(_("Party Type must be Customer, Supplier, Employee, or Shareholder."))
		if not frappe.db.exists(self.party_type, self.party):
			frappe.throw(_("Selected Party does not exist for the chosen Party Type."))
		self.party_name = get_party_display_name(self.party_type, self.party)

	def validate_cash_account(self):
		cash_account = get_account(self.cash_account)
		if cash_account.company != self.company:
			frappe.throw(_("Cash Account must belong to the selected Company."))
		if cash_account.is_group or cash_account.disabled or cash_account.account_type != "Cash":
			frappe.throw(_("Cash Account must be an active, non-group Cash account."))

	def validate_expense_lines(self):
		if not self.expense_lines:
			frappe.throw(_("Add at least one expense line."))

		cash_currency = frappe.db.get_value("Account", self.cash_account, "account_currency")
		payment_entries = set()
		for line in self.expense_lines:
			if flt(line.amount) <= 0:
				frappe.throw(_("Row {0}: Amount must be greater than zero.").format(line.idx))
			if line.expense_account == self.cash_account:
				frappe.throw(_("Row {0}: Expense Account cannot be the Cash Account.").format(line.idx))
			if line.payment_entry:
				if line.payment_entry in payment_entries:
					frappe.throw(_("Row {0}: Payment Entry cannot be linked more than once.").format(line.idx))
				payment_entries.add(line.payment_entry)

			expense_account = get_account(line.expense_account)
			if expense_account.company != self.company:
				frappe.throw(_("Row {0}: Expense Account must belong to the selected Company.").format(line.idx))
			if expense_account.is_group or expense_account.disabled:
				frappe.throw(_("Row {0}: Expense Account must be active and non-group.").format(line.idx))
			if expense_account.root_type != "Expense":
				frappe.throw(_("Row {0}: Expense Account must be an expense account.").format(line.idx))
			if expense_account.account_currency != cash_currency:
				frappe.throw(
					_("Row {0}: Expense Account currency must match the Cash Account currency.").format(
						line.idx
					)
				)

	def set_total_amount(self):
		self.total_amount = sum(flt(line.amount) for line in self.expense_lines)


def make_payment_entry(entry, line):
	"""Create the no-party internal-transfer Payment Entry used by a cash expense."""
	payment_entry = frappe.new_doc("Payment Entry")
	payment_entry.company = entry.company
	payment_entry.payment_type = "Internal Transfer"
	payment_entry.mode_of_payment = entry.mode_of_payment
	payment_entry.posting_date = entry.posting_date
	payment_entry.paid_from = entry.cash_account
	payment_entry.paid_to = line.expense_account
	payment_entry.paid_amount = flt(line.amount)
	payment_entry.received_amount = flt(line.amount)
	payment_entry.project = line.project
	payment_entry.cost_center = line.cost_center
	if hasattr(payment_entry, "department"):
		payment_entry.department = line.department
	payment_entry.reference_no = entry.name
	payment_entry.reference_date = entry.posting_date
	payment_entry.custom_remarks = get_payment_entry_remarks(entry, line)
	if frappe.get_meta("Payment Entry").has_field("custom_petty_cash_entry"):
		payment_entry.custom_petty_cash_entry = entry.name
	return payment_entry


def link_payment_entry_and_gl_entries(entry_name, payment_entry_name):
	"""Store the petty-cash source on its Payment Entry and accounting rows."""
	if frappe.get_meta("Payment Entry").has_field("custom_petty_cash_entry"):
		frappe.db.set_value(
			"Payment Entry",
			payment_entry_name,
			"custom_petty_cash_entry",
			entry_name,
			update_modified=False,
		)
	if frappe.get_meta("GL Entry").has_field("custom_petty_cash_entry"):
		frappe.db.set_value(
			"GL Entry",
			{"voucher_type": "Payment Entry", "voucher_no": payment_entry_name},
			"custom_petty_cash_entry",
			entry_name,
			update_modified=False,
		)


def mark_petty_cash_entry_cancellation(payment_entry):
	"""Tell the Payment Entry override this reversal was initiated by its parent voucher."""
	payment_entry.flags.ignore_petty_cash_entry_link_on_cancel = True


def allow_petty_cash_entry_ledger_links_on_cancel(entry):
	"""Retain GL audit links while ERPNext posts the reversal entries."""
	ignored_doctypes = tuple(getattr(entry, "ignore_linked_doctypes", ()) or ())
	entry.ignore_linked_doctypes = tuple(dict.fromkeys((*ignored_doctypes, "GL Entry")))


def validate_linked_payment_entry(entry, line, payment_entry):
	"""Prevent cancellation from touching a Payment Entry not created by this voucher."""
	if payment_entry.company != entry.company or payment_entry.reference_no != entry.name:
		frappe.throw(
			_("Row {0}: linked Payment Entry {1} does not belong to this Petty Cash Entry.").format(
				line.idx, payment_entry.name
			)
		)
	if payment_entry.payment_type != "Internal Transfer":
		frappe.throw(_("Row {0}: linked Payment Entry has an invalid payment type.").format(line.idx))
	if payment_entry.paid_from != entry.cash_account or payment_entry.paid_to != line.expense_account:
		frappe.throw(_("Row {0}: linked Payment Entry has invalid accounts.").format(line.idx))
	if flt(payment_entry.paid_amount) != flt(line.amount):
		frappe.throw(_("Row {0}: linked Payment Entry has an invalid amount.").format(line.idx))


def get_account(account_name):
	if not account_name:
		frappe.throw(_("Account is required."))
	return frappe.get_cached_doc("Account", account_name)


def get_party_display_name(party_type, party):
	fieldname = PARTY_NAME_FIELDS.get(party_type)
	party_name = frappe.db.get_value(party_type, party, fieldname) if fieldname else None
	return party_name or party


def get_payment_entry_remarks(entry, line):
	remarks = line.remarks or entry.narration or _("Petty Cash Entry {0}").format(entry.name)
	return f"{remarks}\n{_('Paid to')}: {entry.party_name or entry.party}"
