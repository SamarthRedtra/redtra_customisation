# Copyright (c) 2026, samarth.upare@redtra.com and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestPostDatedCheques(IntegrationTestCase):
	"""
	Integration tests for PostDatedCheques.
	Use this class for testing interactions between multiple components.
	"""

	def test_cancel_converted_pdc_cancels_linked_payment_entry(self):
		pdc = frappe.get_doc(
			{
				"doctype": "Post Dated Cheques",
				"company": "_Test Company",
				"party_type": "Supplier",
				"party": "_Test Supplier",
				"payment_type": "Pay",
				"mode_of_payment": "Cheque",
				"reference_no": "TEST-PDC-CANCEL-001",
				"reference_date": "2026-01-01",
				"amount": 100,
				"status": "Converted",
			}
		)
		pdc.insert()
		pdc.submit()

		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Pay",
				"company": "_Test Company",
				"party_type": "Supplier",
				"party": "_Test Supplier",
				"paid_from": "_Test Bank - _TC",
				"paid_to": "_Test Creditors - _TC",
				"paid_amount": 100,
				"received_amount": 100,
				"reference_no": "TEST-PDC-CANCEL-001",
				"custom_is_pdc_entry": 1,
			}
		)
		pe.insert()
		pe.submit()

		pdc.db_set("payment_entry", pe.name, update_modified=False)
		pdc.reload()

		pdc.cancel()

		pdc.reload()
		pe.reload()
		self.assertEqual(pdc.docstatus, 2)
		self.assertEqual(pdc.status, "Cancelled")
		self.assertIsNone(pdc.payment_entry)
		self.assertEqual(pe.docstatus, 2)
