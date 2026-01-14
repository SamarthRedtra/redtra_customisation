"""
Payment Entry Override for PDC Management
"""

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
from frappe import _
from frappe.utils import flt, getdate, nowdate


class CustomPaymentEntry(PaymentEntry):
	"""
	Extended Payment Entry class with PDC management functionality
	"""

	def validate(self):
		super().validate()
		self.validate_pdc_details()

	def validate_pdc_details(self):
		"""Validate PDC-related fields"""
		if not self.is_cheque_payment():
			return

		if not self.pdc_cheque_number:
			frappe.throw(_("Cheque Number is mandatory for cheque payments"))

		if not self.pdc_cheque_date:
			frappe.throw(_("Cheque Date is mandatory for cheque payments"))

		# For post-dated cheques, set posting date to cheque date
		if getdate(self.pdc_cheque_date) > getdate(self.posting_date):
			# Allow posting date to be set to cheque date for PDC
			pass

	def is_cheque_payment(self):
		"""Check if payment mode is cheque"""
		if not self.mode_of_payment:
			return False
		
		try:
			# Check if mode name contains "cheque" (case insensitive)
			if "cheque" in self.mode_of_payment.lower():
				return True
			
			# Also check mode of payment configuration
			mode_of_payment = frappe.get_doc("Mode of Payment", self.mode_of_payment)
			# Check if any account type is Bank
			for account in mode_of_payment.accounts or []:
				if account.default_account:
					acc_doc = frappe.get_doc("Account", account.default_account)
					if acc_doc.account_type == "Bank":
						return True
		except Exception:
			# If mode of payment doc doesn't exist, just check name
			return "cheque" in str(self.mode_of_payment).lower()
		
		return False

	def before_save(self):
		"""Set posting date to cheque date for PDC"""
		if self.is_cheque_payment() and self.pdc_cheque_date:
			# For post-dated cheques, set posting date to cheque date
			if getdate(self.pdc_cheque_date) > getdate(self.posting_date):
				self.posting_date = self.pdc_cheque_date

		# Set initial status
		if self.is_cheque_payment() and not self.pdc_cheque_status:
			self.pdc_cheque_status = "Issued"

	def on_submit(self):
		super().on_submit()
		if self.is_cheque_payment():
			self.create_initial_pdc_entry()

	def create_initial_pdc_entry(self):
		"""Create initial PDC accounting entry"""
		if self.pdc_cheque_status != "Issued":
			return

		# Get PDC accounts from settings
		pdc_settings = frappe.get_single("PDC Settings")
		
		if self.payment_type == "Receive":
			# For received cheques: Debit PDC Received, Credit AR
			# This is already handled by Payment Entry, just verify accounts
			if self.paid_from != pdc_settings.pdc_received_account:
				frappe.msgprint(_(
					"Please ensure Paid From account is set to PDC Received Account "
					"for cheque payments"
				), alert=True)
		else:
			# For issued cheques: Credit PDC Issued, Debit AP
			if self.paid_to != pdc_settings.pdc_issued_account:
				frappe.msgprint(_(
					"Please ensure Paid To account is set to PDC Issued Account "
					"for cheque payments"
				), alert=True)

		# Add initial entry to cheque details
		if not self.pdc_cheque_details:
			self.append("pdc_cheque_details", {
				"journal_entry": "",
				"stage": "Issued",
				"date": self.posting_date,
				"amount": self.paid_amount if self.payment_type == "Pay" else self.received_amount
			})

	def mark_under_collection(self):
		"""Mark cheque as under collection (deposited but not cleared)"""
		if not self.is_cheque_payment():
			frappe.throw(_("This is not a cheque payment"))

		if self.pdc_cheque_status not in ["Issued"]:
			frappe.throw(_("Cheque status must be 'Issued' to mark as Under Collection"))

		self.create_collection_journal_entry()
		self.pdc_cheque_status = "Under Collection"
		self.save()
		frappe.msgprint(_("Cheque marked as Under Collection"))

	def create_collection_journal_entry(self):
		"""Create Journal Entry to move from PDC account to Under Collection"""
		pdc_settings = frappe.get_single("PDC Settings")
		
		je = frappe.new_doc("Journal Entry")
		je.posting_date = nowdate()
		je.company = self.company
		je.user_remark = f"PDC Under Collection - {self.name} - Cheque: {self.pdc_cheque_number}"

		amount = self.paid_amount if self.payment_type == "Pay" else self.received_amount

		if self.payment_type == "Receive":
			# Debit: Under Collection Account
			# Credit: PDC Received Account
			je.append("accounts", {
				"account": pdc_settings.under_collection_account,
				"debit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
			je.append("accounts", {
				"account": pdc_settings.pdc_received_account,
				"credit_in_account_currency": amount,
				"party_type": self.party_type,
				"party": self.party,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
		else:
			# Debit: PDC Issued Account
			# Credit: Under Collection Account
			je.append("accounts", {
				"account": pdc_settings.pdc_issued_account,
				"debit_in_account_currency": amount,
				"party_type": self.party_type,
				"party": self.party,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
			je.append("accounts", {
				"account": pdc_settings.under_collection_account,
				"credit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})

		je.insert()
		je.submit()

		# Add to cheque details
		self.append("pdc_cheque_details", {
			"journal_entry": je.name,
			"stage": "Under Collection",
			"date": je.posting_date,
			"amount": amount
		})

	def mark_collected(self):
		"""Mark cheque as collected (cleared)"""
		if not self.is_cheque_payment():
			frappe.throw(_("This is not a cheque payment"))

		if self.pdc_cheque_status not in ["Under Collection"]:
			frappe.throw(_("Cheque status must be 'Under Collection' to mark as Collected"))

		self.create_clearance_journal_entry()
		self.pdc_cheque_status = "Collected" if self.payment_type == "Receive" else "Paid"
		self.save()
		frappe.msgprint(_("Cheque marked as {0}").format(self.pdc_cheque_status))

	def create_clearance_journal_entry(self):
		"""Create Journal Entry to move from Under Collection to Bank"""
		pdc_settings = frappe.get_single("PDC Settings")
		
		je = frappe.new_doc("Journal Entry")
		je.posting_date = nowdate()
		je.company = self.company
		je.user_remark = f"PDC Collected - {self.name} - Cheque: {self.pdc_cheque_number}"

		amount = self.paid_amount if self.payment_type == "Pay" else self.received_amount
		bank_account = self.pdc_bank_account or self.paid_to if self.payment_type == "Receive" else self.paid_from

		if self.payment_type == "Receive":
			# Debit: Bank Account
			# Credit: Under Collection Account
			je.append("accounts", {
				"account": bank_account,
				"debit_in_account_currency": amount,
				"party_type": self.party_type,
				"party": self.party,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
			je.append("accounts", {
				"account": pdc_settings.under_collection_account,
				"credit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
		else:
			# Debit: Under Collection Account
			# Credit: Bank Account
			je.append("accounts", {
				"account": pdc_settings.under_collection_account,
				"debit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
			je.append("accounts", {
				"account": bank_account,
				"credit_in_account_currency": amount,
				"party_type": self.party_type,
				"party": self.party,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})

		je.insert()
		je.submit()

		# Add to cheque details
		self.append("pdc_cheque_details", {
			"journal_entry": je.name,
			"stage": "Collected" if self.payment_type == "Receive" else "Paid",
			"date": je.posting_date,
			"amount": amount
		})

	def mark_bounced(self):
		"""Mark cheque as bounced and reverse the collection entry"""
		if not self.is_cheque_payment():
			frappe.throw(_("This is not a cheque payment"))

		if self.pdc_cheque_status not in ["Under Collection", "Collected", "Paid"]:
			frappe.throw(_("Cannot mark bounced. Cheque must be Under Collection, Collected, or Paid"))

		self.reverse_collection_entry()
		self.pdc_cheque_status = "Bounced"
		self.save()
		frappe.msgprint(_("Cheque marked as Bounced"))

	def reverse_collection_entry(self):
		"""Reverse the collection journal entry"""
		# Find the latest Under Collection or Collected entry
		collection_entry = None
		for detail in reversed(self.pdc_cheque_details or []):
			if detail.stage in ["Under Collection", "Collected", "Paid"] and detail.journal_entry:
				collection_entry = detail.journal_entry
				break

		if not collection_entry:
			frappe.throw(_("No collection entry found to reverse"))

		# Get the original JE
		original_je = frappe.get_doc("Journal Entry", collection_entry)
		
		# Create reversal JE
		reverse_je = frappe.copy_doc(original_je)
		reverse_je.posting_date = nowdate()
		reverse_je.user_remark = f"PDC Bounced - Reversal - {self.name} - Cheque: {self.pdc_cheque_number}"
		
		# Reverse the amounts
		for account in reverse_je.accounts:
			debit = account.debit_in_account_currency
			credit = account.credit_in_account_currency
			account.debit_in_account_currency = credit
			account.credit_in_account_currency = debit

		reverse_je.insert()
		reverse_je.submit()

		# Add to cheque details
		self.append("pdc_cheque_details", {
			"journal_entry": reverse_je.name,
			"stage": "Bounced",
			"date": reverse_je.posting_date,
			"amount": reverse_je.total_debit
		})


# Whitelisted methods for client-side calls
@frappe.whitelist()
def mark_pdc_under_collection(name):
	"""Mark cheque as under collection - called from client"""
	doc = frappe.get_doc("Payment Entry", name)
	doc.mark_under_collection()
	return doc


@frappe.whitelist()
def mark_pdc_collected(name):
	"""Mark cheque as collected - called from client"""
	doc = frappe.get_doc("Payment Entry", name)
	doc.mark_collected()
	return doc


@frappe.whitelist()
def mark_pdc_bounced(name):
	"""Mark cheque as bounced - called from client"""
	doc = frappe.get_doc("Payment Entry", name)
	doc.mark_bounced()
	return doc
