# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import flt

from redtra_customisation.paid_invoice_commission import (
	backfill_project_paid_commissions,
	clear_paid_invoice_commission,
	compute_true_up_incentives,
	get_or_create_sales_person_from_employee,
	get_project_sales_manager_employee,
	record_paid_invoice_commission,
	should_defer_commission_to_payment,
	sync_commission_from_payment_entry,
)


class TestPaidInvoiceCommission(UnitTestCase):
	def test_should_defer_when_project_wise_enabled(self):
		doc = frappe._dict(project="PROJ-1", custom_enable_sales_based=0)
		settings = frappe._dict(enable_project_wise_commission=1)
		with patch("frappe.get_cached_doc", return_value=settings):
			self.assertTrue(should_defer_commission_to_payment(doc))

	def test_should_not_defer_for_sales_based(self):
		doc = frappe._dict(project="PROJ-1", custom_enable_sales_based=1)
		settings = frappe._dict(enable_project_wise_commission=1)
		with patch("frappe.get_cached_doc", return_value=settings):
			self.assertFalse(should_defer_commission_to_payment(doc))

	def test_get_project_sales_manager_employee_prefers_manager_role(self):
		with patch(
			"frappe.get_all",
			side_effect=[
				[frappe._dict(employee="EMP-MGR")],
				[],
			],
		):
			with patch("frappe.db.get_value", return_value="EMP-LEGACY"):
				self.assertEqual(get_project_sales_manager_employee("PROJ-1"), "EMP-MGR")

	def test_get_project_sales_manager_falls_back_to_salesman_then_legacy(self):
		with patch(
			"frappe.get_all",
			side_effect=[
				[],
				[frappe._dict(employee="EMP-SALES")],
			],
		):
			self.assertEqual(get_project_sales_manager_employee("PROJ-1"), "EMP-SALES")

		with patch("frappe.get_all", return_value=[]):
			with patch("frappe.db.get_value", return_value="EMP-LEGACY"):
				self.assertEqual(get_project_sales_manager_employee("PROJ-1"), "EMP-LEGACY")

	def test_get_or_create_sales_person_finds_by_employee(self):
		with patch("frappe.db.get_value", side_effect=["SP-EXISTING"]):
			self.assertEqual(get_or_create_sales_person_from_employee("EMP-1"), "SP-EXISTING")

	def test_get_or_create_sales_person_finds_by_name_and_links_employee(self):
		def get_value(doctype, name, field=None, **kwargs):
			if doctype == "Sales Person" and isinstance(name, dict) and "employee" in name:
				return None
			if doctype == "Employee":
				return "John Doe"
			if doctype == "Sales Person" and isinstance(name, dict) and "sales_person_name" in name:
				return "John Doe"
			if doctype == "Sales Person" and name == "John Doe" and field == "employee":
				return None
			return None

		with patch("frappe.db.get_value", side_effect=get_value):
			with patch("frappe.db.set_value") as set_value:
				result = get_or_create_sales_person_from_employee("EMP-1")
				self.assertEqual(result, "John Doe")
				set_value.assert_called_once()

	def test_get_or_create_sales_person_creates_when_missing(self):
		created = MagicMock()
		created.name = "New Person"
		created.insert = MagicMock()

		def get_value(doctype, name, field=None, **kwargs):
			if doctype == "Sales Person" and isinstance(name, dict) and "employee" in name:
				return None
			if doctype == "Employee":
				return "New Person"
			if doctype == "Sales Person" and isinstance(name, dict) and "sales_person_name" in name:
				return None
			return None

		with patch("frappe.db.get_value", side_effect=get_value):
			with patch("frappe.db.exists", return_value=False):
				with patch("frappe.utils.nestedset.get_root_of", return_value="Sales Team"):
					with patch("frappe.get_doc", return_value=created) as get_doc:
						result = get_or_create_sales_person_from_employee("EMP-NEW")
						self.assertEqual(result, "New Person")
						created.insert.assert_called_once_with(ignore_permissions=True)
						get_doc.assert_called_once()

	def test_compute_true_up_incentives_on_slab_drop(self):
		"""Inv1 4000 @ 2% = 80; Inv2 2000 with rate 1% → incentives -20."""
		paid = [
			frappe._dict(
				name="SI-1",
				posting_date="2026-01-01",
				base_total=4000,
				base_net_total=4000,
				amount_eligible_for_commission=4000,
				custom_commission_recorded=1,
				paid_date=frappe.utils.getdate("2026-01-05"),
			),
			frappe._dict(
				name="SI-2",
				posting_date="2026-02-01",
				base_total=2000,
				base_net_total=2000,
				amount_eligible_for_commission=2000,
				custom_commission_recorded=0,
				paid_date=frappe.utils.getdate("2026-02-05"),
			),
		]

		with patch(
			"redtra_customisation.paid_invoice_commission.get_paid_project_invoices",
			return_value=paid,
		):
			with patch(
				"redtra_customisation.paid_invoice_commission._invoice_has_sales_order_items",
				return_value=False,
			):
				with patch(
					"redtra_customisation.paid_invoice_commission._get_recorded_incentives",
					return_value=80.0,
				):
					incentives, base = compute_true_up_incentives("PROJ-1", "SI-2", 1.0)
					self.assertAlmostEqual(base, 2000.0)
					# target = 6000 * 1% = 60; already = 80; this = -20
					self.assertAlmostEqual(incentives, -20.0)

	def test_compute_true_up_first_invoice(self):
		paid = [
			frappe._dict(
				name="SI-1",
				posting_date="2026-01-01",
				base_total=4000,
				base_net_total=4000,
				amount_eligible_for_commission=4000,
				custom_commission_recorded=0,
				paid_date=frappe.utils.getdate("2026-01-05"),
			),
		]
		with patch(
			"redtra_customisation.paid_invoice_commission.get_paid_project_invoices",
			return_value=paid,
		):
			with patch(
				"redtra_customisation.paid_invoice_commission._invoice_has_sales_order_items",
				return_value=False,
			):
				incentives, base = compute_true_up_incentives("PROJ-1", "SI-1", 2.0)
				self.assertAlmostEqual(base, 4000.0)
				self.assertAlmostEqual(incentives, 80.0)

	def test_record_paid_invoice_commission_writes_values(self):
		si = frappe._dict(
			name="SI-1",
			project="PROJ-1",
			docstatus=1,
			outstanding_amount=0,
			sales_partner="PARTNER-1",
			custom_enable_sales_based=0,
			custom_commission_recorded=0,
			is_return=0,
		)
		settings = frappe._dict(
			enable_project_wise_commission=1,
			sales_partner_comssion_percentage=10,
		)

		with patch(
			"redtra_customisation.paid_invoice_commission._ensure_commission_recorded_field"
		):
			with patch("frappe.db.get_value", return_value=si):
				with patch(
					"redtra_customisation.paid_invoice_commission.should_defer_commission_to_payment",
					return_value=True,
				):
					with patch("frappe.get_cached_doc", return_value=settings):
						with patch(
							"redtra_customisation.paid_invoice_commission.get_project_commission_rate",
							return_value=2.0,
						):
							with patch(
								"redtra_customisation.paid_invoice_commission.get_project_sales_manager_employee",
								return_value="EMP-1",
							):
								with patch(
									"redtra_customisation.paid_invoice_commission.get_or_create_sales_person_from_employee",
									return_value="SP-1",
								):
									with patch(
										"redtra_customisation.paid_invoice_commission.compute_true_up_incentives",
										return_value=(80.0, 4000.0),
									):
										with patch(
											"redtra_customisation.paid_invoice_commission._write_sales_team"
										) as write_team:
											with patch(
												"redtra_customisation.paid_invoice_commission._write_header_commission"
											) as write_header:
												with patch(
													"frappe.get_meta",
													return_value=MagicMock(
														has_field=lambda f: True
													),
												):
													ok = record_paid_invoice_commission("SI-1")
													self.assertTrue(ok)
													write_team.assert_called_once_with(
														"SI-1", "SP-1", 2.0, 80.0, 4000.0
													)
													self.assertTrue(write_header.called)
													preview = write_header.call_args[0][1]
													self.assertAlmostEqual(
														flt(preview["sales_partner_commission_amount"]),
														8.0,
													)

	def test_record_skips_when_already_recorded(self):
		si = frappe._dict(
			name="SI-1",
			project="PROJ-1",
			docstatus=1,
			outstanding_amount=0,
			sales_partner=None,
			custom_enable_sales_based=0,
			custom_commission_recorded=1,
			is_return=0,
		)
		with patch(
			"redtra_customisation.paid_invoice_commission._ensure_commission_recorded_field"
		):
			with patch("frappe.db.get_value", return_value=si):
				with patch(
					"redtra_customisation.paid_invoice_commission.should_defer_commission_to_payment",
					return_value=True,
				):
					self.assertFalse(record_paid_invoice_commission("SI-1"))

	def test_clear_paid_invoice_commission(self):
		with patch(
			"redtra_customisation.paid_invoice_commission._ensure_commission_recorded_field"
		):
			with patch("frappe.db.get_value", return_value=1):
				with patch(
					"redtra_customisation.paid_invoice_commission._clear_sales_team_commission"
				) as clear_team:
					with patch(
						"redtra_customisation.paid_invoice_commission._clear_header_commission"
					) as clear_header:
						self.assertTrue(clear_paid_invoice_commission("SI-1"))
						clear_team.assert_called_once_with("SI-1")
						clear_header.assert_called_once_with("SI-1")

	def test_sync_from_payment_entry(self):
		pe = frappe._dict(
			references=[
				frappe._dict(reference_doctype="Sales Invoice", reference_name="SI-1"),
				frappe._dict(reference_doctype="Sales Invoice", reference_name="SI-1"),
				frappe._dict(reference_doctype="Purchase Invoice", reference_name="PI-1"),
			]
		)
		with patch(
			"redtra_customisation.paid_invoice_commission.maybe_record_or_clear_paid_commission_by_name"
		) as sync:
			sync_commission_from_payment_entry(pe)
			sync.assert_called_once_with("SI-1")

	def test_backfill_idempotent_second_pass(self):
		with patch(
			"frappe.get_all",
			return_value=["PROJ-1"],
		):
			with patch(
				"redtra_customisation.paid_invoice_commission.should_defer_commission_to_payment",
				return_value=True,
			):
				with patch(
					"redtra_customisation.paid_invoice_commission.get_paid_project_invoices",
					return_value=[
						frappe._dict(name="SI-1", custom_commission_recorded=1),
					],
				):
					with patch(
						"redtra_customisation.paid_invoice_commission.clear_paid_invoice_commission"
					) as clear_fn:
						with patch(
							"redtra_customisation.paid_invoice_commission.record_paid_invoice_commission",
							side_effect=[True, False],
						) as record_fn:
							stats1 = backfill_project_paid_commissions(force=True)
							self.assertEqual(stats1["recorded"], 1)
							clear_fn.assert_called_once_with("SI-1")

							# second pass with force still clears then records
							clear_fn.reset_mock()
							record_fn.side_effect = [True]
							stats2 = backfill_project_paid_commissions(project="PROJ-1", force=True)
							self.assertEqual(stats2["recorded"], 1)
							clear_fn.assert_called_once()
