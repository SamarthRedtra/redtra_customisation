# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch
from redtra_customisation.override.query_report import get_data_for_custom_field


class TestQueryReportOverride(UnitTestCase):
	@patch("frappe.has_permission", return_value=True)
	@patch("frappe.get_list", return_value=[])
	def test_get_data_for_custom_field_with_none_in_list(self, mock_get_list, mock_has_perm):
		# Pass a list containing None, which would trigger Pydantic TypeError in the original method
		names = [None, "DOC-001", "", None, "DOC-002"]
		
		# Invoke the overridden wrapper
		get_data_for_custom_field(doctype="Purchase Invoice", field="bill_no", names=names)
		
		# Verify get_list was called with cleaned filters (excluding None)
		mock_get_list.assert_called_once()
		filters = mock_get_list.call_args[1].get("filters")
		self.assertIn("name", filters)
		self.assertEqual(filters["name"][1], ["DOC-001", "", "DOC-002"])
