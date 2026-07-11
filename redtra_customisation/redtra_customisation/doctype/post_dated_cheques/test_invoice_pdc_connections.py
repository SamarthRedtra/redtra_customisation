# Copyright (c) 2026, redtra_customisation contributors
# License: MIT

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from redtra_customisation.redtra_customisation.doctype.post_dated_cheques.post_dated_cheques import (
	_effective_pdc_line_allocation,
)


class TestInvoicePDCConnections(FrappeTestCase):
	def test_effective_allocation_prorates_when_exceeding_cheque(self):
		cheque_amount = 29220.83
		row_allocation = 58441.64
		total_allocated = 58441.64

		effective = _effective_pdc_line_allocation(
			row_allocation,
			cheque_amount,
			total_allocated,
		)
		self.assertEqual(flt(effective, 2), flt(cheque_amount, 2))

	def test_effective_allocation_unchanged_when_within_cheque(self):
		effective = _effective_pdc_line_allocation(1000, 5000, 1000)
		self.assertEqual(flt(effective), 1000)
