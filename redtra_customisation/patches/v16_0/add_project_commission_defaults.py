import frappe


def execute():
	settings = frappe.get_single("Redtra Custom Setting")

	if settings.get("project_commission_slabs"):
		return

	for slab in (
		{"minimum_value": 0, "maximum_value": 40000, "commission_percentage": 2},
		{"minimum_value": 40000, "maximum_value": 100000, "commission_percentage": 1.5},
		{"minimum_value": 100000, "commission_percentage": 1},
	):
		settings.append("project_commission_slabs", slab)

	settings.save(ignore_permissions=True)
