# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe import _
from frappe.utils import cint, flt

from redtra_customisation.override.purchase_order import po_has_submitted_receipt
from redtra_customisation.override.purchase_order_permissions import is_restricted_non_stock_user


def get_provisional_settings() -> dict:
	if not frappe.db.exists("DocType", "Redtra Custom Setting"):
		return {"enabled": False, "auto_sync": False, "default_for_nonstock": False}

	meta = frappe.get_meta("Redtra Custom Setting")
	settings = {
		"enabled": False,
		"auto_sync": False,
		"default_for_nonstock": False,
	}

	if meta.has_field("enable_provisional_purchase_order"):
		settings["enabled"] = cint(
			frappe.db.get_single_value("Redtra Custom Setting", "enable_provisional_purchase_order")
		)
	if meta.has_field("auto_sync_po_qty_on_receipt"):
		settings["auto_sync"] = cint(
			frappe.db.get_single_value("Redtra Custom Setting", "auto_sync_po_qty_on_receipt")
		)
	if meta.has_field("default_provisional_po_for_nonstock"):
		settings["default_for_nonstock"] = cint(
			frappe.db.get_single_value("Redtra Custom Setting", "default_provisional_po_for_nonstock")
		)

	return settings


def is_provisional_po(purchase_order: str) -> bool:
	if not purchase_order:
		return False

	settings = get_provisional_settings()
	if not settings["enabled"]:
		return False

	if not frappe.get_meta("Purchase Order").has_field("custom_is_provisional_po"):
		return False

	return cint(frappe.db.get_value("Purchase Order", purchase_order, "custom_is_provisional_po"))


def set_default_provisional_po(doc, method=None):
	settings = get_provisional_settings()
	if not settings["enabled"] or not settings["default_for_nonstock"]:
		return

	if not doc.is_new() or cint(doc.get("custom_is_provisional_po")):
		return

	if cint(doc.get("is_nonstock")) or is_restricted_non_stock_user(frappe.session.user):
		doc.custom_is_provisional_po = 1


def on_purchase_receipt_submit(doc, method=None):
	if frappe.flags.in_provisional_po_sync:
		return

	settings = get_provisional_settings()
	if not settings["enabled"] or not settings["auto_sync"]:
		return

	sync_provisional_po_qty_from_receipt(doc)


def bump_provisional_po_qty_before_receipt(purchase_receipt):
	"""Increase PO qty when PR qty exceeds pending qty for provisional POs."""
	if frappe.flags.in_provisional_po_sync:
		return

	settings = get_provisional_settings()
	if not settings["enabled"]:
		return

	po_updates: dict[str, list[dict]] = {}

	for item in purchase_receipt.get("items") or []:
		if not item.purchase_order or not item.purchase_order_item:
			continue
		if not is_provisional_po(item.purchase_order):
			continue

		po_item = frappe.db.get_value(
			"Purchase Order Item",
			item.purchase_order_item,
			["qty", "received_qty", "rate", "item_code", "uom", "schedule_date", "description", "conversion_factor"],
			as_dict=True,
		)
		if not po_item:
			continue

		pending_qty = flt(po_item.get("qty")) - flt(po_item.get("received_qty"))
		pr_qty = flt(item.qty)
		if pr_qty <= pending_qty:
			continue

		required_qty = flt(po_item.get("received_qty")) + pr_qty
		po_updates.setdefault(item.purchase_order, []).append(
			{
				"docname": item.purchase_order_item,
				"item_code": po_item.get("item_code"),
				"qty": required_qty,
				"rate": po_item.get("rate"),
				"uom": po_item.get("uom"),
				"schedule_date": _serialize_schedule_date(po_item.get("schedule_date")),
				"description": po_item.get("description"),
				"conversion_factor": po_item.get("conversion_factor"),
			}
		)

	for po_name, trans_items in po_updates.items():
		_apply_po_item_updates(po_name, trans_items)


def sync_provisional_po_qty_from_receipt(purchase_receipt):
	"""Only increase PO qty when received exceeds ordered qty; never reduce estimate."""
	po_names = {
		item.purchase_order
		for item in (purchase_receipt.get("items") or [])
		if item.purchase_order and is_provisional_po(item.purchase_order)
	}

	for po_name in po_names:
		po = frappe.get_doc("Purchase Order", po_name)
		trans_items = []

		for po_item in po.items:
			received_qty = flt(po_item.received_qty)
			po_qty = flt(po_item.qty)
			if received_qty <= po_qty:
				continue

			trans_items.append(_build_trans_item_row(po_item, received_qty))

		if trans_items:
			_apply_po_item_updates(po_name, trans_items)


def _build_trans_item_row(po_item, qty):
	return {
		"docname": po_item.name,
		"item_code": po_item.item_code,
		"qty": qty,
		"rate": po_item.rate,
		"uom": po_item.uom,
		"schedule_date": _serialize_schedule_date(po_item.schedule_date),
		"description": po_item.description,
		"conversion_factor": po_item.conversion_factor,
	}


def _serialize_schedule_date(value):
	return str(value) if value else value


def _apply_po_item_updates(po_name: str, trans_items: list[dict]):
	from erpnext.controllers.accounts_controller import update_child_qty_rate

	frappe.flags.in_provisional_po_sync = True
	try:
		update_child_qty_rate("Purchase Order", frappe.as_json(trans_items), po_name, "items")
	finally:
		frappe.flags.in_provisional_po_sync = False


def validate_update_child_qty_rate_items(parent_doctype: str, trans_items: list[dict], parent_name: str):
	"""Server-side guard for restricted Update Items dialog and direct API calls."""
	if parent_doctype != "Purchase Order" or not po_has_submitted_receipt(parent_name):
		return

	original_rows = {
		row.name: row
		for row in frappe.get_all(
			"Purchase Order Item",
			filters={"parent": parent_name},
			fields=["name", "item_code", "rate", "uom", "schedule_date", "description", "conversion_factor"],
		)
	}

	for item in trans_items:
		original = original_rows.get(item.get("docname"))
		if not original:
			continue

		if original.item_code and item.get("item_code") != original.item_code:
			frappe.throw(
				_("Item Code cannot be changed for existing rows after a Receive Note is created.")
			)

		if flt(item.get("rate")) != flt(original.rate):
			frappe.throw(
				_("Rate cannot be changed for existing rows after a Receive Note is created.")
			)


def validate_purchase_order_item_rate(doc, method=None):
	if doc.doctype != "Purchase Order Item" or doc.is_new():
		return
	if frappe.flags.in_provisional_po_sync:
		return
	if not doc.has_value_changed("rate"):
		return

	if not po_has_submitted_receipt(doc.parent):
		return

	frappe.throw(
		_("Rate cannot be changed for existing rows after a Receive Note is created."),
		title=_("Rate Change Not Allowed"),
	)


@frappe.whitelist()
def get_provisional_po_settings():
	settings = get_provisional_settings()
	return {
		"enabled": settings["enabled"],
		"auto_sync": settings["auto_sync"],
		"default_for_nonstock": settings["default_for_nonstock"],
	}


@frappe.whitelist()
def update_po_items_with_restrictions(parent_doctype_name: str, trans_items: str, child_docname: str = "items"):
	from erpnext.controllers.accounts_controller import update_child_qty_rate

	items = frappe.parse_json(trans_items)
	validate_update_child_qty_rate_items("Purchase Order", items, parent_doctype_name)
	return update_child_qty_rate("Purchase Order", trans_items, parent_doctype_name, child_docname)


@frappe.whitelist()
def make_provisional_purchase_receipt(source_name, target_doc=None, args=None):
	"""Create Purchase Receipt from an open/provisional PO (supports multiple receipts)."""
	from frappe.model.mapper import get_mapped_doc
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_receipt as erpnext_make_purchase_receipt,
		set_missing_values,
	)

	if not is_provisional_po(source_name):
		return erpnext_make_purchase_receipt(source_name, target_doc, args)

	if args is None:
		args = {}
	elif isinstance(args, str):
		import json

		args = json.loads(args)

	def update_item(obj, target, source_parent):
		pending_qty = flt(obj.qty) - flt(obj.received_qty)
		target.qty = pending_qty if pending_qty > 0 else 0
		target.stock_qty = flt(target.qty) * flt(obj.conversion_factor)
		target.amount = flt(target.qty) * flt(obj.rate)
		target.base_amount = flt(target.qty) * flt(obj.rate) * flt(source_parent.conversion_rate)

	def select_item(doc):
		filtered_items = args.get("filtered_children", [])
		if filtered_items:
			return doc.name in filtered_items
		return True

	def include_item(doc):
		if doc.delivered_by_supplier or not select_item(doc):
			return False

		pending_qty = flt(doc.qty) - flt(doc.received_qty)
		if pending_qty > 0:
			return True

		# Allow another receipt even when current PO qty is fully received.
		return is_provisional_po(source_name)

	doc = get_mapped_doc(
		"Purchase Order",
		source_name,
		{
			"Purchase Order": {
				"doctype": "Purchase Receipt",
				"field_map": {"supplier_warehouse": "supplier_warehouse"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Purchase Order Item": {
				"doctype": "Purchase Receipt Item",
				"field_map": {
					"name": "purchase_order_item",
					"parent": "purchase_order",
					"bom": "bom",
					"material_request": "material_request",
					"material_request_item": "material_request_item",
					"sales_order": "sales_order",
					"sales_order_item": "sales_order_item",
					"wip_composite_asset": "wip_composite_asset",
				},
				"postprocess": update_item,
				"condition": include_item,
			},
			"Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "reset_value": True},
		},
		target_doc,
		set_missing_values,
	)

	return doc
