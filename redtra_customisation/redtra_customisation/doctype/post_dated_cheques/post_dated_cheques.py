# Copyright (c) 2026, redtra_customisation contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PostDatedCheques(Document):
	def before_cancel(self):
		"""Cancel submitted Payment Entries linked to this PDC."""
		payment_entries = self._get_linked_payment_entries()
		for payment_entry_name in payment_entries:
			pe = frappe.get_doc("Payment Entry", payment_entry_name)
			if pe.docstatus == 1:
				pe.cancel()

	def on_cancel(self):
		self.status = "Cancelled"
		self.db_update()

	def before_insert(self):
		self.status = "Pending"

	def _get_linked_payment_entries(self):
		linked = set()

		if self.payment_entry:
			linked.add(self.payment_entry)

		# Fallback: include any PDC-generated entries matching this cheque details.
		rows = frappe.get_all(
			"Payment Entry",
			filters={
				"docstatus": ["in", [0, 1]],
				"custom_is_pdc_entry": 1,
				"company": self.company,
				"party_type": self.party_type,
				"party": self.party,
				"reference_no": self.reference_no,
			},
			pluck="name",
		)
		linked.update(rows or [])
		return list(linked)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_purchase_invoice_for_pdc(doctype, txt, searchfield, start, page_len, filters):
	"""Search Purchase Invoice with Supplier Invoice No for PDC fetch dialog."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if not filters:
		filters = {}

	company = filters.get("company")
	supplier = filters.get("supplier")

	if not company or not supplier:
		return []

	page_len = int(page_len) if page_len else 20
	start = int(start) if start else 0
	search_txt = (txt or "").strip()

	query = """
		SELECT
			name,
			COALESCE(custom_supplier_invoice_no, '') AS custom_supplier_invoice_no,
			grand_total,
			outstanding_amount
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1
			AND company = %(company)s
			AND supplier = %(supplier)s
			AND outstanding_amount > 0
	"""
	values = {"company": company, "supplier": supplier}

	if search_txt:
		query += """
			AND (
				name LIKE %(txt)s
				OR custom_supplier_invoice_no LIKE %(txt)s
			)
		"""
		values["txt"] = f"%{search_txt}%"

	query += """
		ORDER BY posting_date DESC, name DESC
		LIMIT %(start)s, %(page_len)s
	"""
	values["start"] = start
	values["page_len"] = page_len

	return frappe.db.sql(query, values, as_dict=True)
						

