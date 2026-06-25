# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch, MagicMock
from redtra_customisation.rhr.employee_attendance_tool_custom import mark_employee_attendance


class TestEmployeeAttendanceRange(UnitTestCase):
	@patch("redtra_customisation.rhr.employee_attendance_tool_custom.frappe.db.exists", return_value=False)
	@patch("redtra_customisation.rhr.employee_attendance_tool_custom.frappe.get_doc")
	def test_mark_employee_attendance_date_range(self, mock_get_doc, mock_exists):
		# Create a mock document instance
		mock_doc = MagicMock()
		mock_get_doc.return_value = mock_doc
		
		# Define standard args
		employee_list = ["EMP-001", "EMP-002"]
		status = "Present"
		date = "2026-06-01"
		custom_from_date = "2026-06-01"
		custom_to_date = "2026-06-03" # 3 days range (01, 02, 03)
		
		mark_employee_attendance(
			employee_list=employee_list,
			status=status,
			date=date,
			custom_from_date=custom_from_date,
			custom_to_date=custom_to_date
		)
		
		# For 2 employees and 3 dates (01, 02, 03), get_doc should be called 6 times
		self.assertEqual(mock_get_doc.call_count, 6)
		# And mock_doc.insert and mock_doc.submit should have been called 6 times
		self.assertEqual(mock_doc.insert.call_count, 6)
		self.assertEqual(mock_doc.submit.call_count, 6)
		
		# Check that exists was called for each employee-date combo
		self.assertEqual(mock_exists.call_count, 6)
