# Copyright (c) 2026, Redtra
# License: MIT

from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests import UnitTestCase

from redtra_customisation.patches.v16_0.fix_base_total_commission_for_tinv_1099_1145 import (
	EXPLICIT_INVOICES,
	fix_invoice_commission_from_base_total,
)


class TestFixTinvCommissionBaseTotal(UnitTestCase):
	def test_explicit_invoice_names_include_amended_forms(self):
		self.assertIn("TINV/1099/2026-AUG/1", EXPLICIT_INVOICES)
		self.assertIn("TINV/1099/2026-AUG/1-1", EXPLICIT_INVOICES)
		self.assertIn("TINV/1145/2026-AUG/1", EXPLICIT_INVOICES)
		self.assertIn("TINV/1145/2026-AUG/1-1", EXPLICIT_INVOICES)

	def test_fix_rewrites_header_and_team_from_base_total(self):
		writes = []

		def capture_set_value(doctype, name, values, update_modified=True):
			writes.append((doctype, name, dict(values), update_modified))

		with patch(
			"redtra_customisation.patches.v16_0.fix_base_total_commission_for_tinv_1099_1145.frappe.get_all",
			return_value=[
				SimpleNamespace(name="team-1", allocated_percentage=100, commission_rate=1),
			],
		), patch(
			"redtra_customisation.patches.v16_0.fix_base_total_commission_for_tinv_1099_1145.frappe.db.set_value",
			side_effect=capture_set_value,
		), patch(
			"redtra_customisation.patches.v16_0.fix_base_total_commission_for_tinv_1099_1145.flt",
			side_effect=lambda value, precision=None: round(float(value or 0), precision)
			if precision is not None
			else float(value or 0),
		):
			result = fix_invoice_commission_from_base_total(
				"TINV/1099/2026-AUG/1",
				rate=1,
				base=608052.32,
			)

		self.assertEqual(result["amount_eligible_for_commission"], 608052.32)
		self.assertEqual(result["total_commission"], 6080.52)
		self.assertEqual(result["sales_team"][0]["allocated_amount"], 608052.32)
		self.assertEqual(result["sales_team"][0]["incentives"], 6080.52)

		self.assertEqual(writes[0][0], "Sales Invoice")
		self.assertEqual(writes[0][1], "TINV/1099/2026-AUG/1")
		self.assertEqual(writes[0][2]["amount_eligible_for_commission"], 608052.32)
		self.assertEqual(writes[0][2]["total_commission"], 6080.52)
		self.assertFalse(writes[0][3])

		self.assertEqual(writes[1][0], "Sales Team")
		self.assertEqual(writes[1][1], "team-1")
		self.assertEqual(writes[1][2]["allocated_amount"], 608052.32)
		self.assertEqual(writes[1][2]["incentives"], 6080.52)
