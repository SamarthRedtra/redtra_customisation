from unittest.mock import patch

from frappe.tests import UnitTestCase

from redtra_customisation.override.landed_cost_voucher import _get_submitted_claimed_amount
from redtra_customisation.patches.v16_0.correct_opening_sales_invoice_dates import _dates_match
from redtra_customisation.patches.v16_0.opening_sales_invoice_date_map import INVOICE_DATE_MAP


class TestDeltaTransactionCorrections(UnitTestCase):
	def test_opening_sales_invoice_date_map_is_complete(self):
		self.assertEqual(len(INVOICE_DATE_MAP), 133)
		self.assertEqual(
			INVOICE_DATE_MAP["SA-2026-3038"],
			("SA2026/0610", "2026-07-23", "2026-07-24"),
		)
		self.assertEqual(
			INVOICE_DATE_MAP["SA-2026-3240"],
			("DC/SA/10461/2025", "2025-09-23", "2025-12-22"),
		)

	def test_date_match_requires_both_posting_and_due_dates(self):
		self.assertTrue(_dates_match("2026-07-23", "2026-07-24", "2026-07-23", "2026-07-24"))
		self.assertFalse(_dates_match("2026-07-23", "2026-07-31", "2026-07-23", "2026-07-24"))

	@patch("redtra_customisation.override.landed_cost_voucher.frappe.get_all")
	def test_lcv_claim_total_uses_submitted_vendor_rows(self, get_all):
		get_all.return_value = [12.5, 7.25]

		self.assertEqual(_get_submitted_claimed_amount("PINV-TEST-0001"), 19.75)
		get_all.assert_called_once_with(
			"Landed Cost Vendor Invoice",
			filters={
				"parenttype": "Landed Cost Voucher",
				"vendor_invoice": "PINV-TEST-0001",
				"docstatus": 1,
			},
			pluck="amount",
		)
