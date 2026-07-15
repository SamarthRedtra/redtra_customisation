# Copyright (c) 2026, redtra_customisation contributors

import json
from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from redtra_customisation.override.provisional_purchase_order import (
	bump_provisional_po_qty_before_receipt,
	get_provisional_settings,
	is_provisional_po,
	validate_update_child_qty_rate_items,
)


class TestProvisionalPurchaseOrder(UnitTestCase):
	def test_get_provisional_settings_defaults(self):
		settings = get_provisional_settings()
		self.assertIn("enabled", settings)
		self.assertIn("auto_sync", settings)
		self.assertIn("default_for_nonstock", settings)

	def test_is_provisional_po_respects_master_switch(self):
		with patch(
			"redtra_customisation.override.provisional_purchase_order.get_provisional_settings",
			return_value={"enabled": False, "auto_sync": True, "default_for_nonstock": False},
		):
			self.assertFalse(is_provisional_po("PO-TEST"))

		with patch(
			"redtra_customisation.override.provisional_purchase_order.get_provisional_settings",
			return_value={"enabled": True, "auto_sync": True, "default_for_nonstock": False},
		):
			with patch.object(frappe.get_meta("Purchase Order"), "has_field", return_value=True):
				with patch(
					"frappe.db.get_value",
					return_value=1,
				):
					self.assertTrue(is_provisional_po("PO-TEST"))

	def test_validate_blocks_rate_change_after_receipt(self):
		with patch(
			"redtra_customisation.override.provisional_purchase_order.po_has_submitted_receipt",
			return_value=True,
		):
			with patch(
				"frappe.get_all",
				return_value=[
					frappe._dict(
						{
							"name": "POI-001",
							"item_code": "ITEM-1",
							"rate": 100,
							"uom": "Nos",
							"schedule_date": "2026-01-01",
							"description": "Test",
							"conversion_factor": 1,
						}
					)
				],
			):
				self.assertRaises(
					frappe.ValidationError,
					validate_update_child_qty_rate_items,
					"Purchase Order",
					[
						{
							"docname": "POI-001",
							"item_code": "ITEM-1",
							"rate": 150,
							"qty": 10,
						}
					],
					"PO-TEST",
				)

	def test_validate_blocks_item_code_change_after_receipt(self):
		with patch(
			"redtra_customisation.override.provisional_purchase_order.po_has_submitted_receipt",
			return_value=True,
		):
			with patch(
				"frappe.get_all",
				return_value=[
					frappe._dict(
						{
							"name": "POI-001",
							"item_code": "ITEM-1",
							"rate": 100,
							"uom": "Nos",
							"schedule_date": "2026-01-01",
							"description": "Test",
							"conversion_factor": 1,
						}
					)
				],
			):
				self.assertRaises(
					frappe.ValidationError,
					validate_update_child_qty_rate_items,
					"Purchase Order",
					[
						{
							"docname": "POI-001",
							"item_code": "ITEM-2",
							"rate": 100,
							"qty": 10,
						}
					],
					"PO-TEST",
				)

	def test_bump_builds_required_qty_update(self):
		pr = frappe._dict(
			{
				"items": [
					frappe._dict(
						{
							"purchase_order": "PO-TEST",
							"purchase_order_item": "POI-001",
							"qty": 50,
						}
					)
				]
			}
		)

		po_item = {
			"qty": 40,
			"received_qty": 40,
			"rate": 100,
			"item_code": "ITEM-1",
			"uom": "Nos",
			"schedule_date": "2026-01-01",
			"description": "Test",
			"conversion_factor": 1,
		}

		with patch(
			"redtra_customisation.override.provisional_purchase_order.get_provisional_settings",
			return_value={"enabled": True, "auto_sync": True, "default_for_nonstock": False},
		):
			with patch(
				"redtra_customisation.override.provisional_purchase_order.is_provisional_po",
				return_value=True,
			):
				with patch("frappe.db.get_value", return_value=po_item):
					with patch(
						"redtra_customisation.override.provisional_purchase_order._apply_po_item_updates"
					) as apply_updates:
						bump_provisional_po_qty_before_receipt(pr)

		apply_updates.assert_called_once()
		po_name, trans_items = apply_updates.call_args[0]
		self.assertEqual(po_name, "PO-TEST")
		self.assertEqual(len(trans_items), 1)
		self.assertEqual(trans_items[0]["qty"], 90)

	def test_bump_skips_when_pending_qty_is_enough(self):
		pr = frappe._dict(
			{
				"items": [
					frappe._dict(
						{
							"purchase_order": "PO-TEST",
							"purchase_order_item": "POI-001",
							"qty": 30,
						}
					)
				]
			}
		)

		po_item = {
			"qty": 100,
			"received_qty": 0,
			"rate": 100,
			"item_code": "ITEM-1",
			"uom": "Nos",
			"schedule_date": "2026-01-01",
			"description": "Test",
			"conversion_factor": 1,
		}

		with patch(
			"redtra_customisation.override.provisional_purchase_order.get_provisional_settings",
			return_value={"enabled": True, "auto_sync": True, "default_for_nonstock": False},
		):
			with patch(
				"redtra_customisation.override.provisional_purchase_order.is_provisional_po",
				return_value=True,
			):
				with patch("frappe.db.get_value", return_value=po_item):
					with patch(
						"redtra_customisation.override.provisional_purchase_order._apply_po_item_updates"
					) as apply_updates:
						bump_provisional_po_qty_before_receipt(pr)

		apply_updates.assert_not_called()

	def test_update_po_items_with_restrictions_calls_validator(self):
		from redtra_customisation.override.provisional_purchase_order import (
			update_po_items_with_restrictions,
		)

		trans_items = json.dumps([{"docname": "POI-001", "item_code": "ITEM-1", "qty": 10, "rate": 100}])

		with patch(
			"redtra_customisation.override.provisional_purchase_order.validate_update_child_qty_rate_items"
		) as validate_items:
			with patch(
				"erpnext.controllers.accounts_controller.update_child_qty_rate",
				return_value="ok",
			) as update_items:
				result = update_po_items_with_restrictions("PO-TEST", trans_items)

		validate_items.assert_called_once()
		update_items.assert_called_once()
		self.assertEqual(result, "ok")

	def test_apply_po_item_updates_serializes_schedule_date(self):
		from redtra_customisation.override.provisional_purchase_order import _apply_po_item_updates

		with patch(
			"frappe.get_all",
			return_value=[
				frappe._dict(
					{
						"name": "POI-001",
						"item_code": "ITEM-1",
						"qty": 100,
						"rate": 47,
						"uom": "Nos",
						"schedule_date": "2026-01-01",
						"description": "Test",
						"conversion_factor": 1,
					}
				)
			],
		):
			with patch("erpnext.controllers.accounts_controller.update_child_qty_rate") as update_items:
				_apply_po_item_updates(
					"PO-TEST",
					[
						{
							"docname": "POI-001",
							"item_code": "ITEM-1",
							"qty": 3000,
							"rate": 47,
							"schedule_date": date(2026, 6, 23),
						}
					],
				)

		update_items.assert_called_once()
		payload = update_items.call_args[0][1]
		self.assertIn("2026-06-23", payload)

	def test_apply_po_item_updates_keeps_unreceived_rows(self):
		from redtra_customisation.override.provisional_purchase_order import _apply_po_item_updates

		with patch(
			"frappe.get_all",
			return_value=[
				frappe._dict(
					{
						"name": "POI-001",
						"item_code": "ITEM-1",
						"qty": 40,
						"rate": 100,
						"uom": "Nos",
						"schedule_date": "2026-01-01",
						"description": "Received item",
						"conversion_factor": 1,
					}
				),
				frappe._dict(
					{
						"name": "POI-002",
						"item_code": "ITEM-2",
						"qty": 20,
						"rate": 50,
						"uom": "Nos",
						"schedule_date": "2026-01-01",
						"description": "Pending item",
						"conversion_factor": 1,
					}
				),
			],
		):
			with patch("erpnext.controllers.accounts_controller.update_child_qty_rate") as update_items:
				_apply_po_item_updates(
					"PO-TEST",
					[
						{
							"docname": "POI-001",
							"item_code": "ITEM-1",
							"qty": 90,
							"rate": 100,
							"uom": "Nos",
							"schedule_date": "2026-01-01",
							"description": "Received item",
							"conversion_factor": 1,
						}
					],
				)

		update_items.assert_called_once()
		payload = frappe.parse_json(update_items.call_args[0][1])
		self.assertEqual(len(payload), 2)
		self.assertEqual(payload[0]["docname"], "POI-001")
		self.assertEqual(payload[0]["qty"], 90)
		self.assertEqual(payload[1]["docname"], "POI-002")
		self.assertEqual(payload[1]["qty"], 20)

	def test_make_provisional_purchase_receipt_delegates_for_standard_po(self):
		from redtra_customisation.override.provisional_purchase_order import make_provisional_purchase_receipt

		with patch(
			"redtra_customisation.override.provisional_purchase_order.is_provisional_po",
			return_value=False,
		):
			with patch(
				"erpnext.buying.doctype.purchase_order.mapper.make_purchase_receipt",
				return_value={"name": "PR-1"},
			) as erpnext_make:
				result = make_provisional_purchase_receipt("PO-TEST")

		erpnext_make.assert_called_once_with("PO-TEST", None, None)
		self.assertEqual(result, {"name": "PR-1"})
