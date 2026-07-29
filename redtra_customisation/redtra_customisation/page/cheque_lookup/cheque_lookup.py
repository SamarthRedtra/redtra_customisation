"""Single-screen lookup for a cheque's PDC, payment, and linked invoices."""

import frappe
from frappe import _


@frappe.whitelist()
def get_cheque_details(cheque_no: str) -> dict:
	cheque_no = (cheque_no or "").strip()
	if not cheque_no:
		frappe.throw(_("Enter a cheque number."))
	frappe.has_permission("Post Dated Cheques", "read", throw=True)
	rows = frappe.get_list(
		"Post Dated Cheques", filters={"reference_no": ("like", f"%{cheque_no}%")}, fields=["name"],
		order_by="reference_no asc, reference_date desc, modified desc", limit_page_length=25,
	)
	matches = [_pdc_details(row.name) for row in rows]
	# A cheque may have been entered directly as a Payment Entry or as a
	# Security Instrument, without a Post Dated Cheques document.
	if not matches:
		matches = _payment_entry_matches(cheque_no) + _security_instrument_matches(cheque_no)
	return {"query": cheque_no, "matches": matches}


def _payment_entry_matches(cheque_no: str) -> list[dict]:
	if not frappe.has_permission("Payment Entry", "read"):
		return []
	rows = frappe.get_list(
		"Payment Entry",
		filters={"reference_no": ("like", f"%{cheque_no}%"), "docstatus": ("!=", 2)},
		fields=["name"], order_by="posting_date desc, modified desc", limit_page_length=25,
	)
	return [_payment_entry_details(row.name) for row in rows]


def _security_instrument_matches(cheque_no: str) -> list[dict]:
	if not frappe.db.exists("DocType", "Security Instrument") or not frappe.has_permission("Security Instrument", "read"):
		return []
	rows = frappe.get_list(
		"Security Instrument",
		filters={"reference_no": ("like", f"%{cheque_no}%"), "docstatus": ("!=", 2)},
		fields=["name"], order_by="reference_date desc, modified desc", limit_page_length=25,
	)
	return [_security_instrument_details(row.name) for row in rows]


def _payment_entry_details(name: str) -> dict:
	payment = _payment(name) or {}
	invoices = payment.get("invoices", [])
	projects = _unique_projects([payment.get("project")] + [project for invoice in invoices for project in invoice.get("projects", [])])
	return {
		"name": name, "source_doctype": "Payment Entry", "source_label": _("Payment Entry"),
		"status": payment.get("status"), "company": payment.get("company"),
		"project": payment.get("project") or (projects[0] if len(projects) == 1 else None), "projects": projects,
		"party_type": payment.get("party_type"), "party": payment.get("party"), "party_name": payment.get("party"),
		"payment_type": payment.get("payment_type"), "mode_of_payment": payment.get("mode_of_payment"),
		"reference_no": payment.get("reference_no"), "reference_date": payment.get("reference_date"),
		"posting_date": payment.get("posting_date"), "amount": payment.get("received_amount") or payment.get("paid_amount"),
		"currency": payment.get("currency"), "bank_account": payment.get("paid_to") or payment.get("paid_from"),
		"notes": payment.get("remarks"), "payment_entry": payment, "invoices": invoices,
	}


def _security_instrument_details(name: str) -> dict:
	instrument = frappe.get_doc("Security Instrument", name)
	payment = _payment(instrument.payment_entry)
	invoices = (payment or {}).get("invoices", [])
	return {
		"name": name, "source_doctype": "Security Instrument", "source_label": _("Security Instrument"),
		"status": instrument.status, "company": instrument.company, "project": instrument.project,
		"projects": _unique_projects([instrument.project]), "party_type": instrument.party_type,
		"party": instrument.party, "party_name": instrument.party, "payment_type": instrument.payment_type,
		"mode_of_payment": instrument.mode_of_payment, "reference_no": instrument.reference_no,
		"reference_date": instrument.reference_date, "posting_date": instrument.posting_date,
		"amount": instrument.amount, "currency": None, "bank_account": instrument.bank_account,
		"notes": instrument.remarks, "payment_entry": payment, "invoices": invoices,
	}


def _pdc_details(name: str) -> dict:
	pdc = frappe.get_doc("Post Dated Cheques", name)
	payment = _payment(pdc.payment_entry)
	pdc_invoices = [_invoice(row) for row in pdc.get("invoice_references") or []]
	invoices = _merge_invoices(pdc_invoices, (payment or {}).pop("invoices", []))
	projects = _unique_projects(
		[pdc.project] + [project for invoice in invoices for project in invoice.get("projects", [])]
	)
	return {
		"name": pdc.name, "status": pdc.status, "company": pdc.company,
		"project": pdc.project or (projects[0] if len(projects) == 1 else None), "projects": projects,
		"party_type": pdc.party_type, "party": pdc.party, "party_name": pdc.party_name,
		"payment_type": pdc.payment_type, "mode_of_payment": pdc.mode_of_payment,
		"reference_no": pdc.reference_no, "reference_date": pdc.reference_date,
		"posting_date": pdc.posting_date, "amount": pdc.amount, "currency": pdc.account_currency,
		"bank_account": pdc.bank_account, "notes": pdc.notes,
		"payment_entry": payment,
		"invoices": invoices,
	}


def _payment(name: str | None) -> dict | None:
	if not name or not frappe.db.exists("Payment Entry", name):
		return None
	if not frappe.has_permission("Payment Entry", "read", doc=name):
		return {"name": name, "has_access": False}
	fields = [
		"name",
		"company",
		"status",
		"posting_date",
		"reference_no",
		"reference_date",
		"mode_of_payment",
		"party_type",
		"party",
		"paid_from",
		"paid_to",
		"received_amount",
		"paid_amount",
		"paid_to_account_currency",
		"paid_from_account_currency",
		"remarks",
	]
	if frappe.get_meta("Payment Entry").has_field("project"):
		fields.append("project")
	row = frappe.db.get_value("Payment Entry", name, fields, as_dict=True)
	if row:
		row.has_access = True
		row["currency"] = row.get("paid_to_account_currency") or row.get("paid_from_account_currency")
		row["invoices"] = [
			_invoice(reference)
			for reference in frappe.get_all(
				"Payment Entry Reference",
				filters={"parent": name, "parenttype": "Payment Entry"},
				fields=[
					"reference_doctype",
					"reference_name",
					"bill_no",
					"custom_supplier_invoice_no",
					"allocated_amount",
					"total_amount",
					"outstanding_amount",
				],
				order_by="idx asc",
			)
		]
	return row


def _invoice(reference) -> dict:
	doctype, name = reference.get("reference_doctype"), reference.get("reference_name")
	row = {
		"doctype": doctype, "name": name,
		"invoice_reference_no": reference.get("invoice_reference_no") or reference.get("bill_no")
		or reference.get("custom_supplier_invoice_no"),
		"allocated_amount": reference.get("allocated_amount"), "total_amount": reference.get("total_amount"),
		"pdc_outstanding_amount": reference.get("outstanding_amount"), "has_access": False,
	}
	if doctype not in ("Sales Invoice", "Purchase Invoice") or not name:
		return row
	if not frappe.has_permission(doctype, "read", doc=name):
		return row
	invoice = frappe.db.get_value(
		doctype, name,
		["posting_date", "due_date", "grand_total", "outstanding_amount", "status", "project", "currency"],
		as_dict=True,
	)
	if invoice:
		row.update(invoice)
		row["has_access"] = True
		if doctype == "Purchase Invoice":
			row["expense_lines"] = frappe.get_all(
				"Purchase Invoice Item",
				filters={"parent": name, "parenttype": "Purchase Invoice"},
				fields=["item_code", "item_name", "expense_account", "amount", "project"],
				order_by="idx asc",
			)
			row["expense_total"] = sum(line.amount or 0 for line in row["expense_lines"])
		else:
			row["expense_lines"] = []

		# Purchase invoices commonly carry the project at item level rather than
		# on the invoice header. Surface that project in both the invoice row and
		# the cheque summary.
		row["projects"] = _unique_projects(
			[row.get("project")] + [line.get("project") for line in row["expense_lines"]]
		)
		if not row.get("project") and len(row["projects"]) == 1:
			row["project"] = row["projects"][0]
	return row


def _unique_projects(projects: list[str | None]) -> list[str]:
	"""Keep project links ordered and unique, ignoring blank values."""
	return list(dict.fromkeys(project for project in projects if project))


def _merge_invoices(*invoice_groups: list[dict]) -> list[dict]:
	"""Combine PDC and Payment Entry references, keeping one row per invoice."""
	merged = {}
	for invoices in invoice_groups:
		for invoice in invoices:
			key = (invoice.get("doctype"), invoice.get("name"))
			if not all(key):
				continue
			if key in merged:
				# Payment Entry references may have the latest allocation while PDC
				# references contain the external invoice reference.
				for field, value in invoice.items():
					if value not in (None, "", [], 0):
						merged[key][field] = value
			else:
				merged[key] = invoice
	return list(merged.values())
