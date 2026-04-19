# Copyright (c) 2026, redtra_customisation contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from erpnext.accounts.party import get_party_account, get_party_account_currency


def _coerce_json_arg(value, arg_name: str, expected_type: type):
	if value is None:
		return expected_type()

	if isinstance(value, expected_type):
		return value

	if isinstance(value, str):
		try:
			value = frappe.parse_json(value)
		except Exception as exc:
			raise frappe.ValidationError(_("{0} must be valid JSON").format(arg_name)) from exc

	if not isinstance(value, expected_type):
		raise frappe.ValidationError(_("{0} must be a {1}").format(arg_name, expected_type.__name__))

	return value


def _coerce_account_link(value, field_label: str) -> str:
	"""Normalize account values to a single Link-compatible account name."""
	if isinstance(value, (list, tuple)):
		value = next((v for v in value if isinstance(v, str) and v.strip()), None)

	if not isinstance(value, str) or not value.strip():
		raise frappe.ValidationError(_("{0} must resolve to a valid account").format(field_label))

	return value.strip()


@frappe.whitelist()
def get_pending_post_dated_cheques(filters: dict | None = None) -> list[dict]:
	filters = _coerce_json_arg(filters, "filters", dict)
	conditions = ["pdc.status = 'Pending'","pdc.docstatus = 1"]
	values = {}

	if filters.get("company"):
		conditions.append("pdc.company = %(company)s")
		values["company"] = filters["company"]

	if filters.get("from_date"):
		conditions.append("pdc.reference_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("pdc.reference_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("name"):
		conditions.append("pdc.name = %(name)s")
		values["name"] = filters["name"]

	if filters.get("currency"):
		conditions.append("pdc.account_currency = %(currency)s")
		values["currency"] = filters["currency"]

	rows = frappe.db.sql(
		f"""
		SELECT
			pdc.name,
			pdc.company,
			pdc.project,
			pdc.status,
			pdc.payment_type,
			pdc.party_type,
			pdc.party,
			pdc.party_name,
			pdc.mode_of_payment,
			pdc.reference_no,
			pdc.reference_date,
			pdc.amount,
			pdc.account_currency,
			pdc.exchange_rate,
			pdc.bank_account,
			pdc.payment_entry
		FROM `tabPost Dated Cheques` pdc
		WHERE {" AND ".join(conditions)}
		ORDER BY pdc.reference_date ASC, pdc.name ASC
		""",
		values,
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def convert_post_dated_cheques(rows: list[dict], defaults: dict | None = None) -> dict:
	"""
	rows: [{pdc: <name>, bank_account: <optional>}, ...]
	"""
	rows = _coerce_json_arg(rows, "rows", list)
	defaults = _coerce_json_arg(defaults, "defaults", dict)
	if not rows:
		return {"created": [], "failures": []}

	out_created = []
	out_failures = []

	settings = frappe.get_single("Redtra Custom Setting")
	auto_submit = bool(getattr(settings, "pdc_auto_submit_payment_entry", 0))

	for row in rows:
		pdc_name = (row or {}).get("pdc")
		try:
			if not pdc_name:
				raise frappe.ValidationError(_("Missing PDC name"))

			pdc = frappe.get_doc("Post Dated Cheques", pdc_name)
			pdc.check_permission("read")

			# Idempotent behavior: if already converted with a linked Payment Entry,
			# return it as a successful row instead of failing on retries.
			if pdc.status != "Pending":
				if pdc.status == "Converted" and pdc.payment_entry:
					out_created.append(
						{
							"pdc": pdc_name,
							"payment_entry": pdc.payment_entry,
							"submitted": 0,
							"already_converted": 1,
						}
					)
					continue
				raise frappe.ValidationError(_("PDC is not Pending"))
			if pdc.payment_entry:
				raise frappe.ValidationError(_("PDC already linked to Payment Entry {0}").format(pdc.payment_entry))

			# Validate user permissions early
			if auto_submit:
				if not frappe.has_permission("Payment Entry", "submit"):
					raise frappe.PermissionError(_("You do not have permission to submit Payment Entry"))
			else:
				if not frappe.has_permission("Payment Entry", "create"):
					raise frappe.PermissionError(_("You do not have permission to create Payment Entry"))

			pe = _make_payment_entry_from_pdc(pdc, bank_account=row.get("bank_account") or defaults.get("default_bank_account"))
			pe.insert()

			if auto_submit:
				pe.submit()

			pdc.db_set("payment_entry", pe.name, update_modified=False)
			pdc.db_set("status", "Converted", update_modified=False)
			# payment_entry_status is a fetch_from field; setting is optional but harmless if column exists
			if frappe.db.has_column("Post Dated Cheques", "payment_entry_status"):
				pdc.db_set("payment_entry_status", pe.status, update_modified=False)

			out_created.append({"pdc": pdc_name, "payment_entry": pe.name, "submitted": int(auto_submit)})

		except Exception as e:
			out_failures.append({"pdc": pdc_name, "error": frappe.get_traceback() if frappe.conf.developer_mode else str(e)})

	return {"created": out_created, "failures": out_failures}


def _make_payment_entry_from_pdc(pdc, bank_account: str | None):
	if not bank_account:
		# prefer bank_account stored on PDC itself
		bank_account = pdc.get("bank_account")
	if not bank_account:
		raise frappe.ValidationError(_("Bank Account is required to create Payment Entry"))

	party_account = _coerce_account_link(
		get_party_account(pdc.party_type, pdc.party, pdc.company, include_advance=True),
		_("Party Account"),
	)
	if not party_account:
		raise frappe.ValidationError(_("No party account found for {0} {1}").format(pdc.party_type, pdc.party))

	pe = frappe.new_doc("Payment Entry")
	if hasattr(pe, "custom_is_pdc_entry"):
		pe.custom_is_pdc_entry = 1
	pe.company = pdc.company
	pe.project = pdc.project
	pe.cost_center = pdc.get("cost_center")
	pe.department = pdc.get("department")
	pe.payment_type = pdc.payment_type
	pe.party_type = pdc.party_type
	pe.party = pdc.party
	pe.mode_of_payment = pdc.mode_of_payment

	# Standard ERPNext fields
	pe.reference_no = pdc.reference_no
	pe.reference_date = pdc.reference_date

	# PDC override fields (existing custom fields in this app)
	if hasattr(pe, "pdc_cheque_number"):
		pe.pdc_cheque_number = pdc.reference_no
	if hasattr(pe, "pdc_cheque_date"):
		pe.pdc_cheque_date = pdc.reference_date

	# Set posting date to cheque date for post-dated flows (override will also do it)
	pe.posting_date = pdc.posting_date or pdc.reference_date or nowdate()

	# Accounts
	if pdc.payment_type == "Receive":
		pe.paid_from = party_account
		pe.paid_to = bank_account
		pe.received_amount = flt(pdc.amount)
		pe.paid_amount = flt(pdc.amount)
	else:
		pe.paid_from = bank_account
		pe.paid_to = party_account
		pe.paid_amount = flt(pdc.amount)
		pe.received_amount = flt(pdc.amount)

	# Currency
	acc_currency = pdc.account_currency or get_party_account_currency(pdc.party_type, pdc.party, pdc.company)
	if acc_currency:
		pe.paid_from_account_currency = acc_currency
		pe.paid_to_account_currency = acc_currency
		# Keep a sane exchange rate if provided
		if hasattr(pe, "source_exchange_rate") and flt(pdc.exchange_rate):
			pe.source_exchange_rate = flt(pdc.exchange_rate)
		if hasattr(pe, "target_exchange_rate") and flt(pdc.exchange_rate):
			pe.target_exchange_rate = flt(pdc.exchange_rate)

	# References (allocate invoices)
	for ref in pdc.get("invoice_references") or []:
		pe.append("references", {
			"reference_doctype": ref.reference_doctype,
			"reference_name": ref.reference_name,
			"total_amount": ref.total_amount,
			"outstanding_amount": ref.outstanding_amount,
			"allocated_amount": ref.allocated_amount
		})

	return pe
