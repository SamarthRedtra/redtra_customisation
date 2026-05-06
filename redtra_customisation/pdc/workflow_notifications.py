# Copyright (c) 2026, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.user import get_users_with_role

def send_workflow_system_notification(doc, method):
	"""
	Called after_insert on Workflow Action.
	Sends a system notification (bell icon) to users who can act on the document.
	"""
	if doc.status != "Open":
		return

	roles = [r.role for r in doc.permitted_roles]
	if not roles:
		return

	# Identify users with the permitted roles
	users = []
	for role in roles:
		users.extend(get_users_with_role(role))
	
	# Unique users and exclude the person who triggered the action
	users = list(set(users))
	current_user = frappe.session.user
	if current_user in users:
		users.remove(current_user)
	
	if not users:
		return

	subject = _("Workflow Action: {0} required for {1}").format(
		doc.workflow_state or _("Action"), 
		doc.reference_name
	)

	# Create notification logs for each user
	for user in users:
		# Check for existing open notification for same doc to avoid spamming
		if frappe.db.exists("Notification Log", {
			"document_type": doc.reference_doctype,
			"document_name": doc.reference_name,
			"for_user": user,
			"subject": subject
		}):
			continue

		notification = frappe.new_doc("Notification Log")
		notification.subject = subject
		notification.for_user = user
		notification.type = "Alert"
		notification.document_type = doc.reference_doctype
		notification.document_name = doc.reference_name
		notification.from_user = current_user
		notification.insert(ignore_permissions=True)
