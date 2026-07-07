# Copyright (c) 2026, redtra_customisation contributors

from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests import UnitTestCase

from redtra_customisation.rpayroll.doctype.salary_slip.salary_slip_overtime import SalarySlipOvertime


class TestSalarySlipPaymentDays(UnitTestCase):
	def test_partial_relieving_slip_uses_standard_cycle_denominator(self):
		slip = SimpleNamespace(
			employee="EMP-TEST-001",
			salary_structure="Monthly Test Structure",
			start_date="2026-06-25",
			end_date="2026-07-08",
			payment_days=13,
			total_working_days=14,
			relieving_date="2026-07-07",
			joining_date=None,
			name="Sal Slip/TEST/00001",
		)

		def fake_get_value(doctype, filters=None, fieldname=None, order_by=None, **kwargs):
			if doctype == "Salary Structure" and fieldname == "payroll_frequency":
				return "Monthly"
			if doctype == "Salary Slip" and fieldname == "total_working_days":
				return 31
			return None

		with patch("frappe.db.get_value", side_effect=fake_get_value):
			SalarySlipOvertime._set_monthly_payment_days_denominator(slip)

		self.assertEqual(slip.total_working_days, 31)
		self.assertEqual(slip.payment_days, 13)
