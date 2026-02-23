# Copyright (c) 2026, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DateSession(Document):
	def validate(self):
		if self.is_active and not self.session_date:
			frappe.throw("Please set a Session Date when Date Session is active.")

		if self.is_active and not self.applicable_doctypes:
			frappe.throw("Please add at least one Applicable Doctype when Date Session is active.")


@frappe.whitelist()
def get_active_date_session():
	"""Return the active date session configuration for the client."""
	doc = frappe.get_single("Date Session")

	if not doc.is_active or not doc.session_date:
		return None

	# Build a map: { doctype: [field1, field2, ...] }
	doctype_map = {}
	for row in doc.applicable_doctypes:
		dt = row.document_type
		fields_str = row.date_field or "posting_date"
		fields = [f.strip() for f in fields_str.split(",") if f.strip()]
		if dt not in doctype_map:
			doctype_map[dt] = []
		for f in fields:
			if f not in doctype_map[dt]:
				doctype_map[dt].append(f)

	return {
		"session_date": str(doc.session_date),
		"doctypes": doctype_map,
	}


@frappe.whitelist()
def get_date_fields(doctype):
	"""Return all Date and Datetime fields for a given doctype."""
	meta = frappe.get_meta(doctype)
	fields = []
	for df in meta.fields:
		if df.fieldtype in ("Date", "Datetime"):
			fields.append({
				"fieldname": df.fieldname,
				"label": df.label or df.fieldname,
				"fieldtype": df.fieldtype,
			})
	return fields
