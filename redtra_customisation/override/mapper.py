# Copyright (c) 2026, Redtra Customisation and contributors

import frappe

@frappe.whitelist()
def make_mapped_doc(
	method: str, source_name: str, selected_children=None, args=None
):
	"""Override for frappe.model.mapper.make_mapped_doc to support selected_children as dict."""
	method_attr = frappe.get_attr(frappe.override_whitelisted_method(method))

	frappe.is_whitelisted(method_attr)

	if selected_children:
		selected_children = frappe.parse_json(selected_children)

	if args:
		frappe.flags.args = frappe._dict(frappe.parse_json(args))

	frappe.flags.selected_children = selected_children or None

	return method_attr(source_name)


@frappe.whitelist()
def map_docs(
	method: str, source_names, target_doc, args=None
):
	"""Override for frappe.model.mapper.map_docs to convert target_doc dict to Document."""
	method_attr = frappe.get_attr(frappe.override_whitelisted_method(method))

	frappe.is_whitelisted(method_attr)

	if isinstance(target_doc, str):
		target_doc = frappe.parse_json(target_doc)

	if isinstance(target_doc, dict):
		target_doc = frappe.get_doc(target_doc)

	for src in frappe.parse_json(source_names):
		_args = (src, target_doc, frappe.parse_json(args)) if args else (src, target_doc)
		target_doc = method_attr(*_args)
	return target_doc
