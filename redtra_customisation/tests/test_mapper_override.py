# Copyright (c) 2026, redtra_customisation contributors

from importlib import import_module

from frappe.tests import UnitTestCase

from redtra_customisation import hooks


PURCHASE_RECEIPT_INVOICE_MAPPER = (
	"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice"
)


class TestMapperOverride(UnitTestCase):
	def test_purchase_receipt_invoice_mapper_uses_installed_erpnext_method(self):
		self.assertNotIn(PURCHASE_RECEIPT_INVOICE_MAPPER, hooks.override_whitelisted_methods)
		module_path, method_name = PURCHASE_RECEIPT_INVOICE_MAPPER.rsplit(".", 1)
		self.assertTrue(callable(getattr(import_module(module_path), method_name)))
