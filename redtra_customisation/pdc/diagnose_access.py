import frappe
from frappe.permissions import has_permission


@frappe.whitelist()
def diagnose_user_pdc_access(email: str):
	frappe.only_for("System Manager")
	frappe.set_user(email)

	result = {
		"email": email,
		"enabled": frappe.db.get_value("User", email, "enabled"),
		"roles": frappe.get_roles(email),
		"user_permissions": frappe.get_all(
			"User Permission",
			filters={"user": email},
			fields=["allow", "for_value", "apply_to_all_doctypes"],
		),
		"doctype_perm_roles": [p.role for p in frappe.get_meta("Post Dated Cheques Tool").permissions],
		"role_permissions": dict(frappe.permissions.get_role_permissions(frappe.get_meta("Post Dated Cheques Tool"))),
		"permissions": {
			"Post Dated Cheques Tool_read": has_permission("Post Dated Cheques Tool", "read"),
			"Post Dated Cheques Tool_write": has_permission("Post Dated Cheques Tool", "write"),
			"Post Dated Cheques_read": has_permission("Post Dated Cheques", "read"),
			"Post Dated Cheques_write": has_permission("Post Dated Cheques", "write"),
		},
		"desktop_icons": frappe.get_all(
			"Desktop Icon",
			filters={"label": ["like", "%PDC%"]},
			fields=["name", "label", "hidden", "link_to", "link_type"],
		),
		"workspace_sidebar": frappe.get_all(
			"Workspace Sidebar",
			filters={"name": "PDC Cheque"},
			fields=["name", "title", "module"],
		),
	}

	try:
		doc = frappe.get_doc("Post Dated Cheques Tool", "Post Dated Cheques Tool")
		result["can_load_tool"] = True
		result["tool_company"] = doc.get("company")
	except Exception as exc:
		result["can_load_tool"] = False
		result["load_error"] = str(exc)

	result["has_permission_with_doc"] = has_permission(
		"Post Dated Cheques Tool", "read", doc=frappe.get_doc("Post Dated Cheques Tool", "Post Dated Cheques Tool")
	)

	frappe.set_user("Administrator")
	return result
