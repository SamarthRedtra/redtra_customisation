from unittest.mock import patch

from frappe.tests import UnitTestCase

from redtra_customisation.override.landed_cost_voucher import _get_submitted_claimed_amount
from redtra_customisation.patches.v16_0.opening_sales_invoice_date_map import INVOICE_DATE_MAP
from redtra_customisation.patches.v16_0.sales_invoice_ageing_date_map import (
	EXPECTED_RECEIVABLE_COUNT,
	RECEIVABLE_AGEING_ROWS,
)
from redtra_customisation.patches.v16_0.sales_invoice_date_utils import (
	amounts_match,
	dates_match,
	find_sales_invoice,
)


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

	def test_customer_ageing_map_has_all_receivable_rows(self):
		self.assertEqual(len(RECEIVABLE_AGEING_ROWS), EXPECTED_RECEIVABLE_COUNT)
		self.assertEqual(EXPECTED_RECEIVABLE_COUNT, 208)

		duplicate_refs = {}
		for invoice_ref, posting_date, due_date, pending_amount in RECEIVABLE_AGEING_ROWS:
			duplicate_refs.setdefault(invoice_ref, []).append(
				(posting_date, due_date, pending_amount)
			)

		self.assertEqual(len(duplicate_refs["SA2026/0585"]), 2)
		self.assertEqual(
			duplicate_refs["SA2026/0585"],
			[
				("2026-07-17", "2026-10-15", 5271.0),
				("2026-07-17", "2026-08-16", 40425.0),
			],
		)

	def test_date_match_requires_both_posting_and_due_dates(self):
		self.assertTrue(dates_match("2026-07-23", "2026-07-24", "2026-07-23", "2026-07-24"))
		self.assertFalse(dates_match("2026-07-23", "2026-07-31", "2026-07-23", "2026-07-24"))

	def test_amount_match_uses_outstanding_or_grand_total(self):
		invoice = {"outstanding_amount": 5271, "grand_total": 5271}
		self.assertTrue(amounts_match(invoice, 5271))
		self.assertTrue(amounts_match(invoice, 5271.04))
		self.assertFalse(amounts_match(invoice, 40425))

	@patch("redtra_customisation.patches.v16_0.sales_invoice_date_utils.frappe.get_all")
	def test_find_sales_invoice_disambiguates_duplicate_refs_by_amount(self, get_all):
		get_all.side_effect = [
			[],
			[
				{
					"name": "SA2026/0585-A",
					"company": "Deltachem Middle East LLC",
					"docstatus": 1,
					"custom_reference_invoice": "SA2026/0585",
					"posting_date": "2026-07-17",
					"due_date": "2026-10-15",
					"grand_total": 5271,
					"outstanding_amount": 5271,
					"is_opening": "No",
				},
				{
					"name": "SA2026/0585-B",
					"company": "Deltachem Middle East LLC",
					"docstatus": 1,
					"custom_reference_invoice": "SA2026/0585",
					"posting_date": "2026-07-17",
					"due_date": "2026-08-16",
					"grand_total": 40425,
					"outstanding_amount": 40425,
					"is_opening": "No",
				},
			],
		]

		invoice, issue = find_sales_invoice("SA2026/0585", 40425)
		self.assertIsNone(issue)
		self.assertEqual(invoice.name, "SA2026/0585-B")

	@patch("redtra_customisation.patches.v16_0.sales_invoice_date_utils.frappe.get_all")
	def test_find_sales_invoice_returns_ambiguous_when_amounts_do_not_resolve(self, get_all):
		get_all.side_effect = [
			[],
			[
				{
					"name": "INV-1",
					"company": "Deltachem Middle East LLC",
					"docstatus": 1,
					"custom_reference_invoice": "SA2026/0585",
					"posting_date": "2026-07-17",
					"due_date": "2026-10-15",
					"grand_total": 1000,
					"outstanding_amount": 1000,
					"is_opening": "No",
				},
				{
					"name": "INV-2",
					"company": "Deltachem Middle East LLC",
					"docstatus": 1,
					"custom_reference_invoice": "SA2026/0585",
					"posting_date": "2026-07-17",
					"due_date": "2026-08-16",
					"grand_total": 2000,
					"outstanding_amount": 2000,
					"is_opening": "No",
				},
			],
		]

		invoice, issue = find_sales_invoice("SA2026/0585", 40425)
		self.assertIsNone(invoice)
		self.assertEqual(issue, "ambiguous")

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
