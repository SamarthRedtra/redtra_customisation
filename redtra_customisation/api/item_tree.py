# Copyright (c) 2026, Redtra Customisation and contributors

import frappe

ROOT_LABEL = "All Item Groups"


@frappe.whitelist()
def get_children(
	doctype=None,
	parent=None,
	is_root=False,
	include_disabled=0,
	is_stock_item=None,
	brand=None,
	root_item_group=None,
	search=None,
):
	include_disabled = frappe.sbool(include_disabled)
	tree_root = root_item_group or ROOT_LABEL
	search = (search or "").strip()

	if is_root or not parent:
		parent = tree_root

	relevant_groups = None
	matching_items_by_group = None

	if search:
		matching_items = _get_matching_items(
			include_disabled=include_disabled,
			is_stock_item=is_stock_item,
			brand=brand,
			search=search,
			root_item_group=root_item_group,
		)
		relevant_groups = _build_relevant_groups(matching_items, root_item_group)
		matching_items_by_group = {}
		for item in matching_items:
			matching_items_by_group.setdefault(item.item_group, []).append(item)

	nodes = []

	child_groups = frappe.get_all(
		"Item Group",
		filters={"parent_item_group": parent},
		fields=["name"],
		order_by="name",
	)

	for group in child_groups:
		if relevant_groups is not None and group.name not in relevant_groups:
			continue
		nodes.append(
			{
				"value": group.name,
				"title": group.name,
				"expandable": 1,
				"is_item": 0,
			}
		)

	if parent != ROOT_LABEL:
		items = _get_items_for_group(
			parent,
			include_disabled=include_disabled,
			is_stock_item=is_stock_item,
			brand=brand,
			search=search,
			matching_items_by_group=matching_items_by_group,
		)
		for item in items:
			nodes.append(
				{
					"value": item.name,
					"title": _get_item_title(item),
					"expandable": 0,
					"is_item": 1,
				}
			)

	return nodes


@frappe.whitelist()
def get_all_nodes(doctype=None, label=None, parent=None, tree_method=None, **filters):
	"""Expand-all helper for mixed Item Group + Item trees."""
	filters.pop("cmd", None)
	filters.pop("data", None)
	filters.pop("tree_method", None)
	filters.pop("label", None)
	filters.pop("doctype", None)

	parent = parent or label or ROOT_LABEL
	is_root = frappe.sbool(filters.pop("is_root", False))

	data = get_children(
		doctype=doctype,
		parent=parent,
		is_root=is_root,
		**filters,
	)
	out = [{"parent": parent, "data": data}]

	to_check = [d.get("value") for d in data if d.get("expandable")]

	while to_check:
		parent = to_check.pop()
		data = get_children(
			doctype=doctype,
			parent=parent,
			is_root=False,
			**filters,
		)
		out.append({"parent": parent, "data": data})
		for node in data:
			if node.get("expandable"):
				to_check.append(node.get("value"))

	return out


def _get_item_title(item):
	if item.item_name and item.item_code != item.item_name:
		return f"{item.item_code} - {item.item_name}"
	return item.item_code or item.name


def _get_item_filters(include_disabled, is_stock_item, brand):
	filters = {}
	if not include_disabled:
		filters["disabled"] = 0
	if brand:
		filters["brand"] = brand
	if is_stock_item in ("Yes", "1", 1):
		filters["is_stock_item"] = 1
	elif is_stock_item in ("No", "0", 0):
		filters["is_stock_item"] = 0
	return filters


def _get_matching_items(include_disabled, is_stock_item, brand, search, root_item_group=None):
	filters = _get_item_filters(include_disabled, is_stock_item, brand)
	or_filters = [
		["item_code", "like", f"%{search}%"],
		["item_name", "like", f"%{search}%"],
	]

	items = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_code", "item_name", "item_group"],
		order_by="item_code",
	)

	if root_item_group:
		allowed_groups = _get_descendant_groups(root_item_group)
		allowed_groups.add(root_item_group)
		items = [item for item in items if item.item_group in allowed_groups]

	return items


def _get_items_for_group(
	group,
	include_disabled,
	is_stock_item,
	brand,
	search,
	matching_items_by_group=None,
):
	if search and matching_items_by_group is not None:
		return matching_items_by_group.get(group, [])

	filters = _get_item_filters(include_disabled, is_stock_item, brand)
	filters["item_group"] = group

	return frappe.get_all(
		"Item",
		filters=filters,
		fields=["name", "item_code", "item_name", "item_group"],
		order_by="item_code",
	)


def _build_relevant_groups(matching_items, root_item_group=None):
	relevant = set()

	for item in matching_items:
		group = item.item_group
		while group:
			relevant.add(group)
			if group == root_item_group:
				break
			parent = frappe.db.get_value("Item Group", group, "parent_item_group")
			if not parent or parent == ROOT_LABEL:
				break
			group = parent

	if root_item_group:
		group = root_item_group
		while group and group != ROOT_LABEL:
			relevant.add(group)
			group = frappe.db.get_value("Item Group", group, "parent_item_group")

	return relevant


def _get_descendant_groups(item_group_name):
	item_group = frappe.get_cached_value("Item Group", item_group_name, ["lft", "rgt"], as_dict=True)
	if not item_group:
		return set()

	return {
		d.name
		for d in frappe.get_all(
			"Item Group",
			filters={"lft": (">=", item_group.lft), "rgt": ("<=", item_group.rgt)},
			fields=["name"],
		)
	}
