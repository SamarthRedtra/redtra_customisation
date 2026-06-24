# Copyright (c) 2026, Redtra Customisation and contributors

import csv
import io

import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.utils.pdf import get_pdf
from frappe.utils.xlsxutils import make_xlsx

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
	warehouse=None,
	stock_qty_filter=None,
	company=None,
):
	include_disabled = frappe.sbool(include_disabled)
	tree_root = root_item_group or ROOT_LABEL
	search = (search or "").strip()
	warehouse = (warehouse or "").strip() or None
	stock_qty_filter = (stock_qty_filter or "").strip() or None
	company = company or frappe.defaults.get_user_default("Company")

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
			warehouse=warehouse,
			stock_qty_filter=stock_qty_filter,
			company=company,
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
			warehouse=warehouse,
			stock_qty_filter=stock_qty_filter,
			company=company,
		)
		column_warehouses = _get_column_warehouses(company, warehouse=warehouse, warehouse_wise_columns=1)
		stock_warehouses = _get_stock_scope_warehouses(company, warehouse)
		qty_matrix = _get_bin_qty_matrix([item.item_code for item in items], column_warehouses)
		for item in items:
			total_qty = _get_item_total_qty(item.item_code, qty_matrix, stock_warehouses)
			row_qty = (
				flt(qty_matrix.get(item.item_code, {}).get(warehouse, 0))
				if warehouse
				else total_qty
			)
			warehouse_breakdown = []
			if cint(item.get("is_stock_item")):
				for wh in column_warehouses:
					qty = flt(qty_matrix.get(item.item_code, {}).get(wh, 0))
					if qty > 0:
						warehouse_breakdown.append({"warehouse": wh, "qty": qty})
				if warehouse and len(column_warehouses) == 1:
					wh = column_warehouses[0]
					qty = flt(qty_matrix.get(item.item_code, {}).get(wh, 0))
					warehouse_breakdown = [{"warehouse": wh, "qty": qty}]

			nodes.append(
				{
					"value": item.name,
					"title": _get_item_title(item),
					"expandable": 0,
					"is_item": 1,
					"stock_qty": row_qty if cint(item.get("is_stock_item")) else None,
					"stock_uom": item.get("stock_uom"),
					"warehouse_breakdown": warehouse_breakdown,
				}
			)

	return nodes


@frappe.whitelist()
def get_grid_data(
	include_disabled=0,
	is_stock_item=None,
	brand=None,
	root_item_group=None,
	search=None,
	warehouse=None,
	warehouses=None,
	warehouse_wise_columns=1,
	stock_qty_filter=None,
	company=None,
):
	result = build_item_tree_grid_result(
		{
			"include_disabled": include_disabled,
			"is_stock_item": is_stock_item,
			"brand": brand,
			"root_item_group": root_item_group,
			"search": search,
			"warehouse": warehouse,
			"warehouses": warehouses,
			"warehouse_wise_columns": warehouse_wise_columns,
			"stock_qty_filter": stock_qty_filter,
			"company": company,
		}
	)
	return {"columns": result["columns"], "rows": result["data"], "warehouses": result["warehouses"]}


def build_item_tree_grid_result(filters):
	filters = frappe._dict(filters or {})
	company = filters.company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Please set Company"))

	items = _get_items_in_scope(
		include_disabled=filters.include_disabled,
		is_stock_item=filters.is_stock_item,
		brand=filters.brand,
		root_item_group=filters.root_item_group,
		search=filters.search,
		warehouse=filters.warehouse,
		stock_qty_filter=filters.stock_qty_filter,
		company=company,
	)
	column_warehouses = _get_column_warehouses(
		company,
		warehouses=filters.warehouses,
		warehouse=filters.warehouse,
		warehouse_wise_columns=cint(filters.get("warehouse_wise_columns", 1)),
	)
	qty_matrix = _get_bin_qty_matrix([item.item_code for item in items], column_warehouses)
	items_by_group = {}
	for item in items:
		items_by_group.setdefault(item.item_group, []).append(item)

	columns = _build_grid_columns(column_warehouses)
	relevant_groups = None
	if filters.search or (filters.stock_qty_filter and filters.stock_qty_filter != "All"):
		relevant_groups = _build_relevant_groups(items, filters.root_item_group)

	children_map = _get_item_group_children_map()
	data = _build_hierarchical_grid_rows(
		filters.root_item_group,
		children_map,
		items_by_group,
		column_warehouses,
		qty_matrix,
		relevant_groups,
	)

	return {"columns": columns, "data": data, "warehouses": column_warehouses}


def _build_grid_columns(column_warehouses):
	columns = [
		{"label": _("Item Group / Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 110},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
	]
	for wh in column_warehouses:
		columns.append(
			{
				"label": wh,
				"fieldname": _warehouse_field_key(wh),
				"fieldtype": "Float",
				"width": 110,
			}
		)
	columns.append(
		{"label": _("Total Qty"), "fieldname": "total_qty", "fieldtype": "Float", "width": 100}
	)
	return columns


def _get_item_group_children_map():
	children = {}
	for group in frappe.get_all("Item Group", fields=["name", "parent_item_group"], order_by="name"):
		if group.name == ROOT_LABEL:
			# "All Item Groups" is the virtual tree root; skip self-parent mapping.
			continue
		parent = group.parent_item_group or ROOT_LABEL
		children.setdefault(parent, []).append(group.name)
	return children


def _build_hierarchical_grid_rows(
	root_item_group,
	children_map,
	items_by_group,
	column_warehouses,
	qty_matrix,
	relevant_groups,
):
	data = []

	def walk(parent, indent, visited=None):
		if visited is None:
			visited = set()
		rows = []
		for group_name in children_map.get(parent, []):
			if group_name in visited:
				continue
			visited.add(group_name)
			if relevant_groups is not None and group_name not in relevant_groups:
				continue
			rows.append(
				_make_group_grid_row(group_name, indent, column_warehouses, items_by_group, qty_matrix)
			)
			rows.extend(walk(group_name, indent + 1, visited))

		if parent != ROOT_LABEL:
			for item in items_by_group.get(parent, []):
				rows.append(_make_item_grid_row(item, indent, column_warehouses, qty_matrix))
		return rows

	if root_item_group:
		if relevant_groups is None or root_item_group in relevant_groups:
			data.append(
				_make_group_grid_row(
					root_item_group, 0, column_warehouses, items_by_group, qty_matrix
				)
			)
			data.extend(walk(root_item_group, 1))
	else:
		data = walk(ROOT_LABEL, 0)

	return data


def _make_group_grid_row(group_name, indent, column_warehouses, items_by_group, qty_matrix):
	direct_items = items_by_group.get(group_name, [])
	row = {
		"indent": indent,
		"is_group_row": 1,
		"item_code": "",
		"item_name": group_name,
		"item_group": group_name,
		"brand": "",
		"stock_uom": "",
		"total_qty": None,
	}
	total = 0.0
	has_stock = False
	for wh in column_warehouses:
		wh_total = sum(
			flt(qty_matrix.get(item.item_code, {}).get(wh, 0))
			for item in direct_items
			if cint(item.is_stock_item)
		)
		if wh_total:
			has_stock = True
		row[_warehouse_field_key(wh)] = wh_total if wh_total else None
		total += wh_total
	if has_stock:
		row["total_qty"] = total
	return row


def _make_item_grid_row(item, indent, column_warehouses, qty_matrix):
	total_qty = _get_item_total_qty(item.item_code, qty_matrix, column_warehouses)
	row = {
		"indent": indent,
		"is_group_row": 0,
		"item_code": item.item_code,
		"item_name": item.item_name,
		"item_group": item.item_group,
		"brand": item.brand,
		"stock_uom": item.stock_uom,
		"total_qty": total_qty if cint(item.is_stock_item) else None,
	}
	for wh in column_warehouses:
		row[_warehouse_field_key(wh)] = (
			flt(qty_matrix.get(item.item_code, {}).get(wh, 0)) if cint(item.is_stock_item) else None
		)
	return row


@frappe.whitelist()
def export_item_tree_grid(file_format="Excel", **filters):
	filters.pop("cmd", None)
	filters.pop("file_format", None)
	file_format = (file_format or "Excel").strip()

	result = build_item_tree_grid_result(filters)
	columns = result.get("columns") or []
	rows = result.get("data") or []

	header = [col.get("label") or col.get("fieldname") for col in columns]
	data = [header]
	for row in rows:
		data.append([row.get(col.get("fieldname")) for col in columns])

	filename = "Item_Tree_Stock"

	if file_format.lower() == "csv":
		output = io.StringIO()
		writer = csv.writer(output)
		writer.writerows(data)
		frappe.response["filename"] = f"{filename}.csv"
		frappe.response["filecontent"] = output.getvalue()
		frappe.response["type"] = "csv"
		return

	if file_format.lower() == "pdf":
		html = _get_grid_print_html(result, filters, title=_("Item Tree Stock"))
		frappe.response["filename"] = f"{filename}.pdf"
		frappe.response["filecontent"] = get_pdf(html)
		frappe.response["type"] = "pdf"
		return

	frappe.response["filename"] = f"{filename}.xlsx"
	frappe.response["filecontent"] = make_xlsx(data, filename).getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def get_grid_print_html(filters=None, title=None):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	result = build_item_tree_grid_result(filters)
	return _get_grid_print_html(
		{"columns": result["columns"], "rows": result["data"]},
		filters,
		title=title or _("Item Tree Stock"),
	)


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


def _warehouse_field_key(warehouse):
	return "wh_" + frappe.scrub(warehouse)


def _get_item_title(item):
	base = item.item_code or item.name
	if item.item_name and item.item_code != item.item_name:
		base = f"{item.item_code} - {item.item_name}"
	return base


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


def _parse_warehouse_list(warehouses):
	if not warehouses:
		return []
	if isinstance(warehouses, str):
		try:
			warehouses = frappe.parse_json(warehouses)
		except Exception:
			warehouses = [wh.strip() for wh in warehouses.split(",") if wh.strip()]
	if isinstance(warehouses, (list, tuple)):
		return [wh for wh in dict.fromkeys(warehouses) if wh]
	return []


def _get_all_company_warehouses(company):
	return frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="name",
	)


def _get_stock_scope_warehouses(company, warehouse=None):
	if warehouse:
		return [warehouse]
	return _get_all_company_warehouses(company)


def _get_column_warehouses(company, warehouses=None, warehouse=None, warehouse_wise_columns=1):
	parsed = _parse_warehouse_list(warehouses)
	if parsed:
		return parsed
	if warehouse and not cint(warehouse_wise_columns):
		return [warehouse]
	return _get_all_company_warehouses(company)


def _get_warehouses(company, warehouse=None):
	return _get_stock_scope_warehouses(company, warehouse)


def _get_bin_qty_map(item_codes, warehouse):
	item_codes = [code for code in dict.fromkeys(item_codes or []) if code]
	if not item_codes or not warehouse:
		return {}

	rows = frappe.get_all(
		"Bin",
		filters={"warehouse": warehouse, "item_code": ["in", item_codes]},
		fields=["item_code", "actual_qty"],
	)
	return {row.item_code: flt(row.actual_qty) for row in rows}


def _get_bin_qty_matrix(item_codes, warehouses):
	item_codes = [code for code in dict.fromkeys(item_codes or []) if code]
	warehouses = [wh for wh in dict.fromkeys(warehouses or []) if wh]
	if not item_codes or not warehouses:
		return {}

	rows = frappe.get_all(
		"Bin",
		filters={"warehouse": ["in", warehouses], "item_code": ["in", item_codes]},
		fields=["item_code", "warehouse", "actual_qty"],
	)
	matrix = {}
	for row in rows:
		matrix.setdefault(row.item_code, {})[row.warehouse] = flt(row.actual_qty)
	return matrix


def _get_item_total_qty(item_code, qty_matrix, warehouses):
	return sum(flt(qty_matrix.get(item_code, {}).get(wh, 0)) for wh in warehouses)


def _passes_stock_qty_filter(item, qty, stock_qty_filter):
	if not stock_qty_filter or stock_qty_filter == "All":
		return True

	qty = flt(qty)
	is_stock = cint(item.get("is_stock_item"))

	if stock_qty_filter == "Non-Zero":
		return (not is_stock) or qty > 0
	if stock_qty_filter == "Zero":
		return is_stock and qty <= 0
	return True


def _get_items_in_scope(
	include_disabled,
	is_stock_item,
	brand,
	root_item_group=None,
	search=None,
	warehouse=None,
	stock_qty_filter=None,
	company=None,
):
	if search:
		return _get_matching_items(
			include_disabled=include_disabled,
			is_stock_item=is_stock_item,
			brand=brand,
			search=search,
			root_item_group=root_item_group,
			warehouse=warehouse,
			stock_qty_filter=stock_qty_filter,
			company=company,
		)

	filters = _get_item_filters(include_disabled, is_stock_item, brand)
	if root_item_group:
		allowed_groups = _get_descendant_groups(root_item_group)
		allowed_groups.add(root_item_group)
		filters["item_group"] = ["in", list(allowed_groups)]

	items = frappe.get_all(
		"Item",
		filters=filters,
		fields=[
			"name",
			"item_code",
			"item_name",
			"item_group",
			"brand",
			"stock_uom",
			"is_stock_item",
		],
		order_by="item_code",
	)

	if stock_qty_filter and stock_qty_filter != "All":
		warehouses = _get_stock_scope_warehouses(company, warehouse)
		qty_matrix = _get_bin_qty_matrix([item.item_code for item in items], warehouses)
		items = [
			item
			for item in items
			if _passes_stock_qty_filter(
				item,
				_get_item_total_qty(item.item_code, qty_matrix, warehouses),
				stock_qty_filter,
			)
		]

	return items


def _get_matching_items(
	include_disabled,
	is_stock_item,
	brand,
	search,
	root_item_group=None,
	warehouse=None,
	stock_qty_filter=None,
	company=None,
):
	filters = _get_item_filters(include_disabled, is_stock_item, brand)
	search = search.strip()
	search_lower = search.lower()

	items = frappe.get_all(
		"Item",
		filters=filters,
		fields=[
			"name",
			"item_code",
			"item_name",
			"item_group",
			"brand",
			"stock_uom",
			"is_stock_item",
		],
		order_by="item_code",
	)

	items = [
		item
		for item in items
		if search_lower in (item.item_code or "").lower()
		or search_lower in (item.item_name or "").lower()
		or search_lower in (item.name or "").lower()
	]

	if root_item_group:
		allowed_groups = _get_descendant_groups(root_item_group)
		allowed_groups.add(root_item_group)
		items = [item for item in items if item.item_group in allowed_groups]

	if stock_qty_filter and stock_qty_filter != "All":
		warehouses = _get_warehouses(company, warehouse)
		qty_matrix = _get_bin_qty_matrix([item.item_code for item in items], warehouses)
		items = [
			item
			for item in items
			if _passes_stock_qty_filter(
				item,
				_get_item_total_qty(item.item_code, qty_matrix, warehouses),
				stock_qty_filter,
			)
		]

	return items


def _get_items_for_group(
	group,
	include_disabled,
	is_stock_item,
	brand,
	search,
	matching_items_by_group=None,
	warehouse=None,
	stock_qty_filter=None,
	company=None,
):
	if search and matching_items_by_group is not None:
		return matching_items_by_group.get(group, [])

	filters = _get_item_filters(include_disabled, is_stock_item, brand)
	filters["item_group"] = group

	items = frappe.get_all(
		"Item",
		filters=filters,
		fields=[
			"name",
			"item_code",
			"item_name",
			"item_group",
			"brand",
			"stock_uom",
			"is_stock_item",
		],
		order_by="item_code",
	)

	if stock_qty_filter and stock_qty_filter != "All":
		warehouses = _get_warehouses(company, warehouse)
		qty_matrix = _get_bin_qty_matrix([item.item_code for item in items], warehouses)
		items = [
			item
			for item in items
			if _passes_stock_qty_filter(
				item,
				_get_item_total_qty(item.item_code, qty_matrix, warehouses),
				stock_qty_filter,
			)
		]

	return items


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


def _get_grid_print_html(result, filters, title):
	columns = result.get("columns") or []
	rows = result.get("rows") or []
	filter_lines = []
	for key, label in (
		("company", _("Company")),
		("warehouse", _("Stock Filter Warehouse")),
		("warehouses", _("Warehouse Columns")),
		("warehouse_wise_columns", _("Warehouse Wise Columns")),
		("root_item_group", _("Root Item Group")),
		("search", _("Search")),
		("stock_qty_filter", _("Stock Qty")),
		("brand", _("Brand")),
		("is_stock_item", _("Is Stock Item")),
	):
		value = filters.get(key)
		if value:
			filter_lines.append(f"<b>{label}:</b> {frappe.utils.escape_html(str(value))}")

	filter_html = "<br>".join(filter_lines)
	header_cells = "".join(f"<th>{frappe.utils.escape_html(col.get('label') or '')}</th>" for col in columns)
	body_rows = []
	for row in rows:
		cells = []
		for col in columns:
			value = row.get(col.get("fieldname"))
			if col.get("fieldname") == "item_name" and row.get("is_group_row"):
				prefix = "&nbsp;" * (cint(row.get("indent", 0)) * 4)
				cells.append(f"<td><b>{prefix}{frappe.utils.escape_html(str(value or ''))}</b></td>")
				continue
			if col.get("fieldtype") == "Float" and value is not None:
				value = frappe.format_value(value, {"fieldtype": "Float", "precision": 2})
			cells.append(f"<td>{frappe.utils.escape_html(str(value or ''))}</td>")
		body_rows.append(f"<tr>{''.join(cells)}</tr>")

	return f"""
		<h3>{frappe.utils.escape_html(title)}</h3>
		<p>{filter_html}</p>
		<table class="table table-bordered">
			<thead><tr>{header_cells}</tr></thead>
			<tbody>{''.join(body_rows)}</tbody>
		</table>
	"""
