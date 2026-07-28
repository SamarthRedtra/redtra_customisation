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
	return {"query": cheque_no, "matches": [_pdc_details(row.name) for row in rows]}


def _pdc_details(name: str) -> dict:
	pdc = frappe.get_doc("Post Dated Cheques", name)
	invoices = [_invoice(row) for row in pdc.get("invoice_references") or []]
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
		"payment_entry": _payment(pdc.payment_entry),
		"invoices": invoices,
	}


def _payment(name: str | None) -> dict | None:
	if not name or not frappe.db.exists("Payment Entry", name):
		return None
	if not frappe.has_permission("Payment Entry", "read", doc=name):
		return {"name": name, "has_access": False}
	fields = ["name", "status", "posting_date", "mode_of_payment", "received_amount", "paid_amount"]
	row = frappe.db.get_value("Payment Entry", name, fields, as_dict=True)
	if row:
		row.has_access = True
	return row


def _invoice(reference) -> dict:
	doctype, name = reference.reference_doctype, reference.reference_name
	row = {
		"doctype": doctype, "name": name, "invoice_reference_no": reference.invoice_reference_no,
		"allocated_amount": reference.allocated_amount, "total_amount": reference.total_amount,
		"pdc_outstanding_amount": reference.outstanding_amount, "has_access": False,
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
