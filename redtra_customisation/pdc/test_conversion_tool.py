# Copyright (c) 2026, redtra_customisation contributors
# License: MIT

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from redtra_customisation.pdc.conversion_tool import _make_payment_entry_from_pdc


class TestPDCConversionTool(FrappeTestCase):
	@patch("redtra_customisation.pdc.conversion_tool.get_account_details")
	@patch("redtra_customisation.pdc.conversion_tool.get_party_account", return_value="Creditors - TC")
	@patch("redtra_customisation.pdc.conversion_tool.get_party_account_currency", return_value="AED")
	def test_make_payment_entry_prorates_allocations_to_cheque_amount(
		self, _mock_party_currency, _mock_party_account, mock_get_account_details
	):
		mock_get_account_details.return_value = MagicMock(
			account_currency="AED",
			account_type="Bank",
		)

		ref = MagicMock()
		ref.reference_doctype = "Purchase Invoice"
		ref.reference_name = "PI-TEST-001"
		ref.total_amount = 58441.64
		ref.outstanding_amount = 58441.64
		ref.allocated_amount = 58441.64

		pdc = MagicMock()
		pdc.company = "_Test Company"
		pdc.project = None
		pdc.payment_type = "Pay"
		pdc.party_type = "Supplier"
		pdc.party = "Test Supplier"
		pdc.party_name = "Test Supplier"
		pdc.mode_of_payment = "Cheque"
		pdc.reference_no = "CHQ-001"
		pdc.reference_date = "2026-07-01"
		pdc.posting_date = "2026-07-01"
		pdc.amount = 29220.83
		pdc.account_currency = "AED"
		pdc.exchange_rate = 1
		pdc.get = MagicMock(
			side_effect=lambda key, default=None: {
				"bank_account": "BOB MAIN - SC",
				"cost_center": None,
				"department": None,
				"invoice_references": [ref],
			}.get(key, default)
		)

		pe = _make_payment_entry_from_pdc(pdc, bank_account="BOB MAIN - SC")
		self.assertEqual(flt(pe.paid_amount), 29220.83)
		self.assertEqual(len(pe.references), 1)
		self.assertEqual(flt(pe.references[0].allocated_amount), 29220.83)
