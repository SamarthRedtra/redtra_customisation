# Copyright (c) 2026, Redtra Customisation and contributors

import frappe
from frappe.www import printview as frappe_printview


def _serialize_json_arg(value):
	if value is None or isinstance(value, str):
		return value
	if isinstance(value, dict):
		return frappe.as_json(value)
	return value


def _normalize_doc(doc, name=None):
	if isinstance(doc, dict):
		return frappe.as_json(doc)
	return doc


@frappe.whitelist()
def get_html_and_style(
	doc,
	name=None,
	print_format=None,
	no_letterhead=None,
	letterhead=None,
	trigger_print=False,
	style=None,
	settings=None,
):
	"""Print preview API wrapper — accepts frm.doc dict from Print View."""
	return frappe_printview.get_html_and_style(
		doc=_normalize_doc(doc, name),
		name=name,
		print_format=print_format,
		no_letterhead=no_letterhead,
		letterhead=letterhead,
		trigger_print=trigger_print,
		style=style,
		settings=_serialize_json_arg(settings),
	)


@frappe.whitelist()
def get_rendered_raw_commands(doc, name=None, print_format=None):
	"""Raw print commands wrapper — accepts frm.doc dict from Print View."""
	return frappe_printview.get_rendered_raw_commands(
		doc=_normalize_doc(doc, name),
		name=name,
		print_format=print_format,
	)
