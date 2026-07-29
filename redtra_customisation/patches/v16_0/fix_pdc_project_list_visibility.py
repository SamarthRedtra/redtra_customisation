"""Keep blank Project values from removing transaction List View results."""

import json

import frappe


def execute():
	# A Project title lookup applies Project Access to the parent query. That
	# hides any transaction whose Project is blank, even when the user can read
	# the transaction itself. Disable the automatic Project fetch and remove it
	# from shared List View layouts. It remains available on document forms and
	# in Report View.
	for doctype in (
		"Post Dated Cheques",
		"Purchase Order",
		"Purchase Invoice",
		"Purchase Receipt",
		"Sales Order",
		"Sales Invoice",
		"Payment Entry",
	):
		project_field = frappe.get_meta(doctype).get_field("project")
		if project_field:
			property_setter = frappe.db.get_value(
				"Property Setter",
				{
					"doc_type": doctype,
					"field_name": "project",
					"property": "in_list_view",
				},
			)
			if property_setter:
				frappe.db.set_value(
					"Property Setter",
					property_setter,
					"value",
					"0",
					update_modified=False,
				)
			else:
				frappe.make_property_setter(
					{
						"doctype": doctype,
						"doctype_or_field": "DocField",
						"fieldname": "project",
						"property": "in_list_view",
						"value": "0",
						"property_type": "Check",
					},
					ignore_validate=True,
				)

		if not frappe.db.exists("List View Settings", doctype):
			frappe.clear_cache(doctype=doctype)
			continue

		layout = frappe.get_doc("List View Settings", doctype)
		try:
			fields = json.loads(layout.fields or "[]")
		except (TypeError, ValueError):
			continue

		cleaned_fields = [field for field in fields if field.get("fieldname") != "project"]
		if len(cleaned_fields) != len(fields):
			frappe.db.set_value(
				"List View Settings",
				doctype,
				"fields",
				json.dumps(cleaned_fields, separators=(",", ":")),
				update_modified=False,
			)

		frappe.clear_cache(doctype=doctype)
