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
		self.validate_cheque_status_change()

	def validate_pdc_details(self):
		"""Validate PDC-related fields"""
		if not self.is_cheque_payment():
			return

		if not self.pdc_cheque_number:
			frappe.throw(_("Cheque Number is mandatory for cheque payments"))

		if not self.pdc_cheque_date:
			frappe.throw(_("Cheque Date is mandatory for cheque payments"))

		# Validate bank account is not a group account
		if self.pdc_bank_account:
			self.validate_account_not_group(self.pdc_bank_account, "PDC Bank Account")

		# For post-dated cheques, set posting date to cheque date
		if getdate(self.pdc_cheque_date) > getdate(self.posting_date):
			# Allow posting date to be set to cheque date for PDC
			pass
	
	def validate_cheque_status_change(self):
		"""Allow status changes after submission with proper workflow validation"""
		if not self.is_cheque_payment() or self.docstatus != 1:
			return
		
		# Get previous status from database if this is an update
		if self.name and frappe.db.exists("Payment Entry", self.name):
			old_status = frappe.db.get_value("Payment Entry", self.name, "pdc_cheque_status")
			
			# Allow status changes following proper workflow
			valid_transitions = {
				"Issued": ["Under Collection"],
				"Under Collection": ["Collected", "Bounced", "Paid"],
				"Collected": ["Bounced"],
				"Paid": ["Bounced"],
				"Bounced": []  # Terminal state, no transitions allowed
			}
			
			if old_status and old_status != self.pdc_cheque_status:
				allowed_next = valid_transitions.get(old_status, [])
				if self.pdc_cheque_status not in allowed_next:
					frappe.throw(_(
						"Cannot change status from '{0}' to '{1}'. "
						"Allowed transitions: {2}"
					).format(
						old_status, 
						self.pdc_cheque_status,
						", ".join(allowed_next) if allowed_next else "None (terminal state)"
					))

	def validate_account_not_group(self, account_name, account_label=""):
		"""Validate that account is not a group account"""
		if not account_name:
			return
		
		is_group = frappe.db.get_value("Account", account_name, "is_group")
		if is_group:
			label = account_label or account_name
			frappe.throw(_(
				"Account {0} is a Group Account and group accounts cannot be used in transactions. "
				"Please select a ledger account."
			).format(frappe.bold(label)))
	
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

		# Set initial status only on new records
		if self.is_new() and self.is_cheque_payment() and not self.pdc_cheque_status:
			custom_settings = frappe.get_single("Redtra Custom Setting")
			if custom_settings.create_pdc_directly_under_collection:
				self.pdc_cheque_status = "Under Collection"
			else:
				self.pdc_cheque_status = "Issued"

	def on_submit(self):
		super().on_submit()
		if self.is_cheque_payment():
			self.create_initial_pdc_entry()

	def create_initial_pdc_entry(self):
		"""Create initial PDC accounting entry"""
		if self.pdc_cheque_status not in ["Issued", "Under Collection"]:
			return

		# Get PDC accounts from settings
		pdc_settings = frappe.get_single("PDC Settings")
		custom_settings = frappe.get_single("Redtra Custom Setting")
		
		# Determine which account to check against
		if custom_settings.create_pdc_directly_under_collection:
			target_account = pdc_settings.under_collection_account
			account_label = "Under Collection Account"
		else:
			target_account = pdc_settings.pdc_received_account if self.payment_type == "Receive" else pdc_settings.pdc_issued_account
			account_label = "PDC Received Account" if self.payment_type == "Receive" else "PDC Issued Account"

		if self.payment_type == "Receive":
			# For received cheques: Debit Check Account, Credit AR
			if self.paid_from != target_account:
				frappe.msgprint(_(
					"Please ensure Paid From account is set to {0} "
					"for cheque payments"
				).format(account_label), alert=True)
		else:
			# For issued cheques: Credit Check Account, Debit AP
			if self.paid_to != target_account:
				frappe.msgprint(_(
					"Please ensure Paid To account is set to {0} "
					"for cheque payments"
				).format(account_label), alert=True)
		
		if custom_settings.create_pdc_directly_under_collection:
			self.pdc_cheque_status = "Issued"
			self.mark_under_collection()
			

		# Add initial entry to cheque details
		if not self.pdc_cheque_details:
			self.append("pdc_cheque_details", {
				"journal_entry": "",
				"stage": self.pdc_cheque_status,
				"date": self.posting_date,
				"amount": self.paid_amount if self.payment_type == "Pay" else self.received_amount
			})

	def mark_under_collection(self):
		"""Mark cheque as under collection (deposited but not cleared)"""
		if not self.is_cheque_payment():
			frappe.throw(_("This is not a cheque payment"))

		if self.pdc_cheque_status not in ["Issued"]:
			frappe.throw(_("Cheque status must be 'Issued' to mark as Under Collection"))

		# Allow updating cheque details table after submit
		self.flags.ignore_validate_update_after_submit = True
		self.create_collection_journal_entry()
		self.pdc_cheque_status = "Under Collection"
		self.save()
		frappe.msgprint(_("Cheque marked as Under Collection"))

	def create_collection_journal_entry(self):
		"""Create Journal Entry to move from PDC account to Under Collection"""
		pdc_settings = frappe.get_single("PDC Settings")
		
		# Validate all accounts are not group accounts
		self.validate_account_not_group(pdc_settings.under_collection_account, "Under Collection Account")
		if self.payment_type == "Receive":
			self.validate_account_not_group(pdc_settings.pdc_received_account, "PDC Received Account")
		else:
			self.validate_account_not_group(pdc_settings.pdc_issued_account, "PDC Issued Account")
		
		je = frappe.new_doc("Journal Entry")
		je.posting_date = nowdate()
		je.company = self.company
		je.user_remark = f"PDC Under Collection - {self.name} - Cheque: {self.pdc_cheque_number}"

		amount = self.paid_amount if self.payment_type == "Pay" else self.received_amount

		# Check account type to determine if party is required
		under_collection_account_type = frappe.db.get_value("Account", pdc_settings.under_collection_account, "account_type")
		requires_party = under_collection_account_type in ["Receivable", "Payable"]

		if self.payment_type == "Receive":
			# Debit: Under Collection Account
			# Credit: PDC Received Account
			under_collection_entry = {
				"account": pdc_settings.under_collection_account,
				"debit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			}
			# Add party fields only if account type requires it
			if requires_party and self.party_type and self.party:
				under_collection_entry["party_type"] = self.party_type
				under_collection_entry["party"] = self.party
			
			je.append("accounts", under_collection_entry)
			je.append("accounts", {
				"account": pdc_settings.pdc_received_account,
				"credit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
		else:
			# Debit: PDC Issued Account
			# Credit: Under Collection Account
			je.append("accounts", {
				"account": pdc_settings.pdc_issued_account,
				"debit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			})
			
			under_collection_entry = {
				"account": pdc_settings.under_collection_account,
				"credit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			}
			# Add party fields only if account type requires it
			if requires_party and self.party_type and self.party:
				under_collection_entry["party_type"] = self.party_type
				under_collection_entry["party"] = self.party
			
			je.append("accounts", under_collection_entry)

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

		# Allow updating cheque details table after submit
		self.flags.ignore_validate_update_after_submit = True
		self.create_clearance_journal_entry()
		self.pdc_cheque_status = "Collected" if self.payment_type == "Receive" else "Paid"
		self.save()
		frappe.msgprint(_("Cheque marked as {0}").format(self.pdc_cheque_status))

	def create_clearance_journal_entry(self):
		"""Create Journal Entry to move from Under Collection to Bank"""
		pdc_settings = frappe.get_single("PDC Settings")
		
		amount = self.paid_amount if self.payment_type == "Pay" else self.received_amount
		bank_account = self.pdc_bank_account or self.paid_to if self.payment_type == "Receive" else self.paid_from
		
		# Validate all accounts are not group accounts
		# Provide specific field name in error message
		if self.pdc_bank_account:
			self.validate_account_not_group(bank_account, "PDC Bank Account")
		else:
			# If using fallback account, validate it and mention which field to set
			fallback_field = "Paid To" if self.payment_type == "Receive" else "Paid From"
			if not bank_account:
				frappe.throw(_("Please set PDC Bank Account or ensure {0} account is selected").format(fallback_field))
			# Check if fallback account is group, but suggest setting PDC Bank Account
			is_group = frappe.db.get_value("Account", bank_account, "is_group")
			if is_group:
				frappe.throw(_(
					"The {0} account ({1}) is a Group Account. "
					"Please set a ledger account in the 'PDC Bank Account' field instead."
				).format(fallback_field, frappe.bold(bank_account)))
		
		self.validate_account_not_group(pdc_settings.under_collection_account, "Under Collection Account")
		
		je = frappe.new_doc("Journal Entry")
		je.posting_date = nowdate()
		je.company = self.company
		je.user_remark = f"PDC Collected - {self.name} - Cheque: {self.pdc_cheque_number}"

		# Check account types to determine if party is required
		under_collection_account_type = frappe.db.get_value("Account", pdc_settings.under_collection_account, "account_type")
		bank_account_type = frappe.db.get_value("Account", bank_account, "account_type")
		under_collection_requires_party = under_collection_account_type in ["Receivable", "Payable"]
		bank_requires_party = bank_account_type in ["Receivable", "Payable"]

		if self.payment_type == "Receive":
			# Debit: Bank Account
			# Credit: Under Collection Account
			bank_entry = {
				"account": bank_account,
				"debit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			}
			if bank_requires_party and self.party_type and self.party:
				bank_entry["party_type"] = self.party_type
				bank_entry["party"] = self.party
			je.append("accounts", bank_entry)
			
			under_collection_entry = {
				"account": pdc_settings.under_collection_account,
				"credit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			}
			if under_collection_requires_party and self.party_type and self.party:
				under_collection_entry["party_type"] = self.party_type
				under_collection_entry["party"] = self.party
			je.append("accounts", under_collection_entry)
		else:
			# Debit: Under Collection Account
			# Credit: Bank Account
			under_collection_entry = {
				"account": pdc_settings.under_collection_account,
				"debit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			}
			if under_collection_requires_party and self.party_type and self.party:
				under_collection_entry["party_type"] = self.party_type
				under_collection_entry["party"] = self.party
			je.append("accounts", under_collection_entry)
			
			bank_entry = {
				"account": bank_account,
				"credit_in_account_currency": amount,
				"reference_type": "Payment Entry",
				"reference_name": self.name,
			}
			if bank_requires_party and self.party_type and self.party:
				bank_entry["party_type"] = self.party_type
				bank_entry["party"] = self.party
			je.append("accounts", bank_entry)

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

		# Allow updating cheque details table after submit
		self.flags.ignore_validate_update_after_submit = True
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
