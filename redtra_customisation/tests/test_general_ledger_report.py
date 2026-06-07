# Copyright (c) 2026, redtra_customisation contributors

from frappe.tests import UnitTestCase

from redtra_customisation.override.general_ledger_report import (
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
