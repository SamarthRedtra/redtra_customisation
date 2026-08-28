# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests import UnitTestCase

from redtra_customisation.override.purchase_order_permissions import (
	get_permission_query_conditions,
	get_purchase_type_configuration,
	has_permission,
	is_restricted_non_stock_user,
)


class TestPurchaseOrderPermissions(UnitTestCase):
	def test_non_listed_user_can_read_stock_po(self):
		user = "_test_po_perm_normal@example.com"
		self._ensure_user(user, restricted=False)

		result = has_permission(
			{"doctype": "Purchase Order", "name": "TEST-PO", "is_nonstock": 0},
			ptype="read",
			user=user,
		)
		self.assertTrue(result)

	def test_listed_user_cannot_read_stock_po(self):
		user = "_test_po_perm_restricted@example.com"
		self._ensure_user(user, restricted=True)

		result = has_permission(
			{"doctype": "Purchase Order", "name": "TEST-PO", "is_nonstock": 0},
			ptype="read",
			user=user,
		)
		self.assertFalse(result)

	def test_listed_user_can_read_nonstock_po(self):
		user = "_test_po_perm_restricted@example.com"
		self._ensure_user(user, restricted=True)

		result = has_permission(
			{"doctype": "Purchase Order", "name": "TEST-PO", "is_nonstock": 1},
			ptype="read",
			user=user,
		)
		self.assertTrue(result)

	def test_listed_user_can_create_new_po(self):
		user = "_test_po_perm_restricted@example.com"
		self._ensure_user(user, restricted=True)

		result = has_permission(
			{"doctype": "Purchase Order", "__islocal": 1, "is_nonstock": 0},
			ptype="create",
			user=user,
		)
		self.assertTrue(result)

	def test_non_listed_user_create_uses_role_permissions(self):
		user = "_test_po_perm_normal@example.com"
		self._ensure_user(user, restricted=False)

		result = has_permission(
			{"doctype": "Purchase Order", "__islocal": 1},
			ptype="create",
			user=user,
		)
		self.assertTrue(result)

	def test_mapped_user_can_only_access_own_purchase_orders(self):
		user = "_test_po_purchase_type@example.com"
		self._ensure_user(user, restricted=False)
		self._set_purchase_type_mappings(
			[
				{"user": user, "purchase_type": "Domestic"},
				{"user": user, "purchase_type": "International"},
			]
		)

		configuration = get_purchase_type_configuration(user)
		self.assertEqual(configuration.allowed_types, ("Domestic", "International"))
		self.assertIsNone(configuration.default_type)
		self.assertIn(f"owner = '{user}'", get_permission_query_conditions(user))
		self.assertFalse(
			has_permission(
				{"doctype": "Purchase Order", "name": "TEST-OTHER", "owner": "other@example.com"},
				ptype="read",
				user=user,
			)
		)
		self.assertTrue(
			has_permission(
				{"doctype": "Purchase Order", "name": "TEST-OWN", "owner": user, "is_nonstock": 1},
				ptype="read",
				user=user,
			)
		)

	def test_settings_reject_duplicate_purchase_type_mapping(self):
		user = "_test_po_purchase_type_duplicate@example.com"
		self._ensure_user(user, restricted=False)

		settings = frappe.get_single("Redtra Custom Setting")
		settings.set(
			"purchase_type_user_mappings",
			[
				{"user": user, "purchase_type": "Domestic"},
				{"user": user, "purchase_type": "Domestic"},
			],
		)
		self.assertRaises(frappe.ValidationError, settings.save, ignore_permissions=True)

	def _ensure_user(self, email: str, restricted: bool):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Test",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)

		settings = frappe.get_single("Redtra Custom Setting")
		settings.set("restrict_non_stockable_item_user", [])
		if restricted:
			settings.append("restrict_non_stockable_item_user", {"user": email})
		settings.save(ignore_permissions=True)
		frappe.clear_cache()

		self.assertEqual(is_restricted_non_stock_user(email), restricted)

	def _set_purchase_type_mappings(self, mappings):
		settings = frappe.get_single("Redtra Custom Setting")
		settings.set("purchase_type_user_mappings", mappings)
		settings.save(ignore_permissions=True)
