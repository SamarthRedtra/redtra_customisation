# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class BulkPaymentEntryTool(Document):
	pass

@frappe.whitelist()
def create_bulk_payments(company, posting_date, action_type, payment_document_type, payments):
	if not company:
		frappe.throw(_("Company is mandatory"))
	if not posting_date:
		frappe.throw(_("Posting Date is mandatory"))
	if not payments:
		frappe.throw(_("Payments list is empty"))

	payments_list = json.loads(payments)
	results = []

	for row in payments_list:
		# Use transaction savepoints so a single failed row does not block others
		savepoint_name = f"row_{row.get('name') or frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint_name)
		try:
			if payment_document_type == "Post Dated Cheque":
				doc = create_single_pdc(company, posting_date, action_type, row)
			else:
				doc = create_single_payment(company, posting_date, action_type, row)
			results.append({
				"name": row.get("name"),
				"status": "Success",
				"payment_entry": doc.name,
				"error_message": ""
			})
		except Exception as e:
			frappe.db.rollback(save_point=savepoint_name)
			friendly_msg = str(e).split('\n')[0]
			results.append({
				"name": row.get("name"),
				"status": "Failed",
				"payment_entry": "",
				"error_message": friendly_msg
			})

	return results

def create_single_payment(company, posting_date, action_type, row):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	from erpnext.accounts.party import get_party_account

	invoice_doctype = row.get("invoice_doctype")
	invoice_name = row.get("invoice_name")
	party_type = row.get("party_type")
	party = row.get("party")
	payment_type = row.get("payment_type")
	amount = flt(row.get("amount"))
	mode_of_payment = row.get("mode_of_payment")
	bank_cash_account = row.get("bank_cash_account")
	reference_no = row.get("reference_no")
	reference_date = row.get("reference_date")
	remarks = row.get("remarks")

	if not party:
		frappe.throw(_("Party is mandatory"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than 0"))

	if invoice_doctype and invoice_name and invoice_doctype != "None":
		pe = get_payment_entry(
			dt=invoice_doctype,
			dn=invoice_name,
			party_amount=amount,
			bank_account=bank_cash_account,
			party_type=party_type,
			payment_type=payment_type,
			reference_date=reference_date
		)
		pe.posting_date = posting_date
		if mode_of_payment:
			pe.mode_of_payment = mode_of_payment
		if reference_no:
			pe.reference_no = reference_no
		if reference_date:
			pe.reference_date = reference_date
		if remarks:
			pe.remarks = remarks
	else:
		if not bank_cash_account:
			frappe.throw(_("Bank/Cash Account is mandatory when no invoice is linked"))

		pe = frappe.new_doc("Payment Entry")
		pe.company = company
		pe.payment_type = payment_type
		pe.posting_date = posting_date
		pe.party_type = party_type
		pe.party = party
		pe.mode_of_payment = mode_of_payment
		pe.reference_no = reference_no
		pe.reference_date = reference_date

		party_account = get_party_account(party_type, party, company)
		pe.party_account = party_account
		pe.party_account_currency = frappe.db.get_value("Account", party_account, "account_currency") or frappe.db.get_value("Company", company, "default_currency")

		pe.paid_from = party_account if payment_type == "Receive" else bank_cash_account
		pe.paid_to = party_account if payment_type == "Pay" else bank_cash_account

		bank_currency = frappe.db.get_value("Account", bank_cash_account, "account_currency") or frappe.db.get_value("Company", company, "default_currency")
		pe.paid_from_account_currency = frappe.db.get_value("Account", pe.paid_from, "account_currency") or bank_currency
		pe.paid_to_account_currency = frappe.db.get_value("Account", pe.paid_to, "account_currency") or bank_currency

		pe.source_exchange_rate = 1.0
		pe.target_exchange_rate = 1.0

		pe.paid_amount = amount
		pe.received_amount = amount

		pe.set_amounts()
		pe.set_title()
		if remarks:
			pe.remarks = remarks
		else:
			pe.set_remarks()

	pe.insert(ignore_permissions=True)

	if action_type == "Submit":
		pe.submit()

	return pe

def create_single_pdc(company, posting_date, action_type, row):
	party_type = row.get("party_type")
	party = row.get("party")
	payment_type = row.get("payment_type")
	amount = flt(row.get("amount"))
	mode_of_payment = row.get("mode_of_payment")
	bank_cash_account = row.get("bank_cash_account")
	reference_no = row.get("reference_no")
	reference_date = row.get("reference_date")
	remarks = row.get("remarks")
	invoice_doctype = row.get("invoice_doctype")
	invoice_name = row.get("invoice_name")

	if not party:
		frappe.throw(_("Party is mandatory"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than 0"))
	if not bank_cash_account:
		frappe.throw(_("Bank/Cash Account is mandatory"))
	if not mode_of_payment:
		frappe.throw(_("Mode of Payment is mandatory"))
	if not reference_no:
		frappe.throw(_("Cheque/Reference No is mandatory"))
	if not reference_date:
		frappe.throw(_("Cheque/Reference Date is mandatory"))

	pdc = frappe.new_doc("Post Dated Cheques")
	pdc.company = company
	pdc.posting_date = posting_date
	pdc.payment_type = payment_type
	pdc.party_type = party_type
	pdc.party = party
	pdc.mode_of_payment = mode_of_payment
	pdc.reference_no = reference_no
	pdc.reference_date = reference_date
	pdc.amount = amount
	pdc.bank_account = bank_cash_account
	pdc.notes = remarks
	pdc.status = "Pending"

	pdc.party_name = frappe.db.get_value(party_type, party, "customer_name" if party_type == "Customer" else "supplier_name")
	pdc.account_currency = frappe.db.get_value("Account", bank_cash_account, "account_currency") or frappe.db.get_value("Company", company, "default_currency")
	pdc.exchange_rate = 1.0

	if invoice_doctype and invoice_name and invoice_doctype != "None":
		if invoice_doctype not in ("Sales Invoice", "Purchase Invoice"):
			frappe.throw(_("PDCs can only be linked to Sales Invoice or Purchase Invoice"))
		
		inv_totals = frappe.db.get_value(invoice_doctype, invoice_name, ["grand_total", "outstanding_amount"], as_dict=True)
		if inv_totals:
			pdc.append("invoice_references", {
				"reference_doctype": invoice_doctype,
				"reference_name": invoice_name,
				"total_amount": inv_totals.grand_total,
				"outstanding_amount": inv_totals.outstanding_amount,
				"allocated_amount": amount
			})

	pdc.insert(ignore_permissions=True)

	if action_type == "Submit":
		pdc.submit()

	return pdc
