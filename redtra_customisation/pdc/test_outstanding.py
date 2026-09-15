# Copyright (c) 2026, redtra_customisation contributors
# License: MIT

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from redtra_customisation.redtra_customisation.doctype.post_dated_cheques.post_dated_cheques import (
	get_primary_invoice_outstanding,
)


class TestPDCOutstanding(UnitTestCase):
	@patch(
		"redtra_customisation.redtra_customisation.doctype.post_dated_cheques.post_dated_cheques.frappe.db.sql"
	)
	@patch(
		"redtra_customisation.redtra_customisation.doctype.post_dated_cheques.post_dated_cheques.frappe.db.get_value"
	)
	def test_sales_invoice_uses_primary_debtors_ledger(self, get_value, sql):
		get_value.return_value = frappe._dict(
			debit_to="Debtors - MRG",
			customer="Customer 1",
			outstanding_amount=10632.81,
		)
		sql.return_value = [(55998.694,)]

		outstanding = get_primary_invoice_outstanding(
			"Sales Invoice", "ACC-SINV-2026-00266-2"
		)

		self.assertEqual(outstanding, 55998.694)
