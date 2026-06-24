# Copyright (c) 2026, redtra_customisation contributors

"""General Ledger report enhancements for redtra_customisation."""

import frappe
from frappe.utils import cint

import erpnext.accounts.report.general_ledger.general_ledger as gl_report

_ORIGINAL_GET_GL_ENTRIES = gl_report.get_gl_entries


def _get_gl_setting(fieldname, filters, filter_key):
	if filter_key in filters and filters.get(filter_key) is not None:
		return cint(filters.get(filter_key))

	if not frappe.get_meta("Redtra Custom Setting").has_field(fieldname):
		return 1

	value = frappe.db.get_single_value("Redtra Custom Setting", fieldname)
	if value is None:
		return 1
	return cint(value)


def get_gl_entries(filters, accounting_dimensions):
	gl_entries = _ORIGINAL_GET_GL_ENTRIES(filters, accounting_dimensions)

	if filters.get("account") and _get_gl_setting(
		"include_against_account_entries_in_gl",
		filters,
		"include_against_account_entries",
	):
		gl_entries = _append_voucher_contra_entries(filters, accounting_dimensions, gl_entries)
		gl_entries = _sort_gl_entries_by_voucher(gl_entries)

	if filters.get("party_type") or filters.get("party"):
		group_by_against_voucher = bool(
			_get_gl_setting(
				"group_by_against_voucher_in_gl",
				filters,
				"group_by_against_voucher",
			)
		)
		gl_entries = _sort_gl_entries_for_party(gl_entries, group_by_against_voucher)

	return gl_entries


def _append_voucher_contra_entries(filters, accounting_dimensions, gl_entries):
	if not gl_entries:
		return gl_entries

	vouchers = {(gle.voucher_type, gle.voucher_no) for gle in gl_entries}
	if not vouchers:
		return gl_entries

	existing = {gle.gl_entry for gle in gl_entries}
	filters_without_account = frappe._dict(filters)
	filters_without_account.pop("account", None)

	contra_entries = _fetch_gl_entries_for_vouchers(
		filters_without_account, accounting_dimensions, vouchers
	)

	for gle in contra_entries:
		if gle.gl_entry not in existing:
			gl_entries.append(gle)
			existing.add(gle.gl_entry)

	return gl_entries


def _fetch_gl_entries_for_vouchers(filters, accounting_dimensions, vouchers):
	currency_map = gl_report.get_currency(filters)
	select_fields = """, debit, credit, debit_in_account_currency,
		credit_in_account_currency """

	if filters.get("show_remarks"):
		if remarks_length := frappe.get_single_value("Accounts Settings", "general_ledger_remarks_length"):
			select_fields += f",substr(remarks, 1, {remarks_length}) as 'remarks'"
		else:
			select_fields += """,remarks"""

	dimension_fields = ""
	if accounting_dimensions:
		dimension_fields = ", ".join(accounting_dimensions) + ","

	transaction_currency_fields = ""
	if filters.get("add_values_in_transaction_currency"):
		transaction_currency_fields = (
			"debit_in_transaction_currency, credit_in_transaction_currency, transaction_currency,"
		)

	voucher_conditions = " OR ".join(
		[
			f"(voucher_type = {frappe.db.escape(voucher_type)} AND voucher_no = {frappe.db.escape(voucher_no)})"
			for voucher_type, voucher_no in vouchers
		]
	)

	base_conditions = gl_report.get_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			name as gl_entry, posting_date, account, party_type, party,
			voucher_type, voucher_subtype, voucher_no, {dimension_fields}
			cost_center, project, {transaction_currency_fields}
			against_voucher_type, against_voucher, account_currency,
			against, is_opening, creation {select_fields}
		from `tabGL Entry`
		where company=%(company)s {base_conditions}
			and ({voucher_conditions})
		order by posting_date asc, voucher_no asc, account asc, creation asc
		""",
		frappe._dict(filters),
		as_dict=1,
	)

	party_name_map = gl_report.get_party_name_map()
	for gle in rows:
		if gle.party_type and gle.party:
			gle.party_name = party_name_map.get(gle.party_type, {}).get(gle.party)

	if filters.get("presentation_currency"):
		return gl_report.convert_to_presentation_currency(rows, currency_map, filters)
	return rows


def _sort_gl_entries_by_voucher(gl_entries):
	return sorted(
		gl_entries,
		key=lambda gle: (
			gle.get("posting_date") or "",
			gle.get("voucher_no") or "",
			gle.get("account") or "",
			gle.get("creation") or "",
		),
	)


def _sort_gl_entries_for_party(gl_entries, group_by_against_voucher=False):
	def sort_key(gle):
		key = [gle.get("posting_date") or ""]
		if group_by_against_voucher:
			key.append(_group_key_for_party_sort(gle))
		key.extend(
			[
				gle.get("voucher_no") or "",
				gle.get("account") or "",
				gle.get("creation") or "",
			]
		)
		return tuple(key)

	return sorted(gl_entries, key=sort_key)


def _group_key_for_party_sort(gle):
	against_voucher = (gle.get("against_voucher") or "").strip()
	if against_voucher:
		return against_voucher
	return gle.get("voucher_no") or ""


def apply_general_ledger_report_patch():
	"""Patch ERPNext and dependent report modules to use the custom GL fetch."""
	if getattr(gl_report.get_gl_entries, "_redtra_patched", False):
		return

	gl_report.get_gl_entries = get_gl_entries
	gl_report.get_gl_entries._redtra_patched = True

	_patch_consumer_module(
		"construction_management.construction_management.report.advanced_general_ledger.advanced_general_ledger"
	)


def _patch_consumer_module(module_path: str):
	try:
		module = frappe.get_module(module_path)
	except Exception:
		return

	module.get_gl_entries = get_gl_entries
