# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch
from redtra_customisation.rpayroll.doctype.salary_slip.salary_slip_overtime import SalarySlipOvertime


class TestSalarySlipAvoidAbsenteeism(UnitTestCase):
	def test_avoid_absenteeism_filters_components_only(self):
		slip = frappe.new_doc("Salary Slip")
		slip.set("custom_avoid_absenteeism", 1)
		
		# Add absenteeism deduction and penalty
		slip.append("deductions", {
			"salary_component": "Absenteeism Penalty",
			"amount": 100,
			"default_amount": 100
		})
		slip.append("deductions", {
			"salary_component": "Absenteeism Deduction",
			"amount": 200,
			"default_amount": 200
		})
		# Add a standard non-absenteeism deduction
		slip.append("deductions", {
			"salary_component": "Income Tax",
			"amount": 150,
			"default_amount": 150
		})
		
		# Mock parent calculate_net_pay call to do nothing (it will just preserve our mock deductions)
		with patch("hrms.payroll.doctype.salary_slip.salary_slip.SalarySlip.calculate_net_pay") as mock_super:
			with patch.object(slip, "set_precision_for_component_amounts") as mock_precision:
				with patch.object(slip, "set_net_pay") as mock_net_pay:
					slip.calculate_net_pay()
					
					mock_super.assert_called_once()
					mock_precision.assert_called_once()
					mock_net_pay.assert_called_once()
					
					# Verify that Absenteeism components were removed, but other deductions remain
					remaining_components = [d.salary_component for d in slip.deductions]
					self.assertNotIn("Absenteeism Penalty", remaining_components)
					self.assertNotIn("Absenteeism Deduction", remaining_components)
					self.assertIn("Income Tax", remaining_components)
