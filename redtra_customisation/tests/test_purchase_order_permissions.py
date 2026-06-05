# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe.tests import UnitTestCase

from redtra_customisation.override.purchase_order_permissions import (
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
		self.assertIsNone(result)

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
