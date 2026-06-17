# Copyright (c) 2026, redtra_customisation contributors

from unittest.mock import patch

from frappe.tests import UnitTestCase

from redtra_customisation.override.general_ledger_report import (
	_get_gl_setting,
	_group_key_for_party_sort,
	_sort_gl_entries_for_party,
)


class TestGeneralLedgerReport(UnitTestCase):
	def test_party_sort_groups_payment_with_invoice(self):
		rows = [
			{"voucher_no": "PE-001", "against_voucher": "INV-001", "posting_date": "2026-03-10"},
			{"voucher_no": "INV-001", "against_voucher": "", "posting_date": "2026-02-01"},
		]
		sorted_rows = _sort_gl_entries_for_party(rows)
		self.assertEqual(sorted_rows[0]["voucher_no"], "INV-001")
		self.assertEqual(sorted_rows[1]["voucher_no"], "PE-001")

	def test_group_key_uses_against_voucher(self):
		self.assertEqual(
			_group_key_for_party_sort({"voucher_no": "PE-001", "against_voucher": "INV-001"}),
			"INV-001",
		)
		self.assertEqual(
			_group_key_for_party_sort({"voucher_no": "INV-001", "against_voucher": ""}),
			"INV-001",
		)

	def test_get_gl_setting_uses_report_filter_when_present(self):
		filters = {"include_against_account_entries": 0}
		with patch(
			"redtra_customisation.override.general_ledger_report.frappe.db.get_single_value",
			return_value=1,
		):
			self.assertEqual(
				_get_gl_setting(
					"include_against_account_entries_in_gl",
					filters,
					"include_against_account_entries",
				),
				0,
			)

	def test_get_gl_setting_falls_back_to_redtra_setting(self):
		filters = {}
		with patch(
			"redtra_customisation.override.general_ledger_report.frappe.get_meta"
		) as mock_meta, patch(
			"redtra_customisation.override.general_ledger_report.frappe.db.get_single_value",
			return_value=1,
		) as mock_get:
			mock_meta.return_value.has_field.return_value = True
			self.assertEqual(
				_get_gl_setting(
					"include_against_account_entries_in_gl",
					filters,
					"include_against_account_entries",
				),
				1,
			)
			mock_get.assert_called_once_with(
				"Redtra Custom Setting", "include_against_account_entries_in_gl"
			)

	def test_get_gl_setting_respects_disabled_redtra_setting(self):
		filters = {}
		with patch(
			"redtra_customisation.override.general_ledger_report.frappe.get_meta"
		) as mock_meta, patch(
			"redtra_customisation.override.general_ledger_report.frappe.db.get_single_value",
			return_value=0,
		):
			mock_meta.return_value.has_field.return_value = True
			self.assertEqual(
				_get_gl_setting(
					"include_against_account_entries_in_gl",
					filters,
					"include_against_account_entries",
				),
				0,
			)

	def test_get_gl_setting_defaults_when_field_missing(self):
		filters = {}
		with patch(
			"redtra_customisation.override.general_ledger_report.frappe.get_meta"
		) as mock_meta, patch(
			"redtra_customisation.override.general_ledger_report.frappe.db.get_single_value",
		) as mock_get:
			mock_meta.return_value.has_field.return_value = False
			self.assertEqual(
				_get_gl_setting(
					"include_against_account_entries_in_gl",
					filters,
					"include_against_account_entries",
				),
				1,
			)
			mock_get.assert_not_called()
