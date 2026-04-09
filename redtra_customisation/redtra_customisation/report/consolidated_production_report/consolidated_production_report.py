import frappe
from frappe import _

def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"label": _("Particulars"), "fieldname": "item", "fieldtype": "Data", "width": 250},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 300},
		{"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 120},
		{"label": _("Unit Cost"), "fieldname": "unit_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 120},
	]

def get_data(filters):
	conditions = []
	values = {}

	if filters.get("company"):
		conditions.append("se.company = %(company)s")
		values["company"] = filters.get("company")
	if filters.get("from_date"):
		conditions.append("se.posting_date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append("se.posting_date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")

	conditions.append("sed.is_finished_item = 1")
	where_clause = " AND ".join(conditions) if conditions else "1=1"

	sed_records = frappe.db.sql(f"""
		SELECT 
			se.work_order,
			sed.item_code,
			sed.item_name,
			sed.qty,
			sed.basic_amount
		FROM `tabStock Entry` se
		JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
		  AND se.purpose = 'Manufacture'
		  AND {where_clause}
	""", values, as_dict=True)

	if not sed_records:
		return []

	work_orders = list(set([r.work_order for r in sed_records if r.work_order]))
	
	wo_operation_map = {}
	if work_orders:
		ops = frappe.db.sql("""
			SELECT parent, operation 
			FROM `tabWork Order Operation` 
			WHERE parent IN %s
		""", (tuple(work_orders),), as_dict=True)
		for op in ops:
			wo_operation_map[op.parent] = op.operation

	grouped = {}

	for row in sed_records:
		operation = wo_operation_map.get(row.work_order, "Other")
		if operation == "ACC Injection Moulding": op_label = "ACC' (Injection Moulding)"
		elif operation == "Blow Moulding": op_label = "WPB' (Blow Moulding)"
		elif operation == "Labeling": op_label = "WPL' (Labelling)"
		elif operation == "Printing": op_label = "WPP' (Printing)"
		elif operation == "Wadding": op_label = "WPW' (Wadding)"
		else: op_label = f"Uncategorized ({operation})"

		if op_label not in grouped: grouped[op_label] = {}
		if row.item_code not in grouped[op_label]:
			grouped[op_label][row.item_code] = {"description": row.item_name, "qty": 0.0, "total_cost": 0.0}
			
		grouped[op_label][row.item_code]["qty"] += float(row.qty or 0)
		grouped[op_label][row.item_code]["total_cost"] += float(row.basic_amount or 0)

	data = []
	grand_total_qty = 0.0
	grand_total_cost = 0.0

	order_list = ["ACC", "WPB", "WPL", "WPP", "WPW"]
	def get_order_index(label):
		for i, prefix in enumerate(order_list):
			if label.startswith(prefix): return i
		return 999

	sorted_groups = sorted(grouped.keys(), key=lambda x: get_order_index(x))

	for grp in sorted_groups:
		items = grouped[grp]
		data.append({"item": frappe.bold(grp), "description": "", "qty": None, "unit_cost": None, "total_cost": None, "indent": 0})

		grp_qty = 0.0
		grp_cost = 0.0

		for item_code, stats in items.items():
			uc = stats["total_cost"] / stats["qty"] if stats["qty"] else 0.0
			data.append({"item": item_code, "description": stats["description"], "qty": stats["qty"], "unit_cost": uc, "total_cost": stats["total_cost"], "indent": 1})
			grp_qty += stats["qty"]
			grp_cost += stats["total_cost"]

		grp_uc = grp_cost / grp_qty if grp_qty else 0.0
		data.append({"item": "Total '", "description": "", "qty": grp_qty, "unit_cost": grp_uc, "total_cost": grp_cost, "indent": 0})
		data.append({"item": "", "description": "", "qty": None, "unit_cost": None, "total_cost": None, "indent": 0})

		grand_total_qty += grp_qty
		grand_total_cost += grp_cost

	if data:
		grand_uc = grand_total_cost / grand_total_qty if grand_total_qty else 0.0
		data.append({"item": frappe.bold("Total '"), "description": "", "qty": grand_total_qty, "unit_cost": grand_uc, "total_cost": grand_total_cost, "indent": 0})

	return data
