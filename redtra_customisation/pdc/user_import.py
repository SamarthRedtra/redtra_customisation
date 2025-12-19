"""
Import users from CSV and create Raven channels by department
"""

import csv
import frappe
from frappe import _
from frappe.utils import get_fullname


# Role mapping based on designation/department
ROLE_MAPPING = {
	"Production Manager": ["Manufacturing Manager"],
	"Accountant": ["Accounts User"],
	"Secretary": ["Employee"],
	"DESIGNEER": ["Manufacturing User"],
	"IT Engineer": ["System Manager"],
	"Invoice": ["Accounts User"],
	"Dispatch": ["Stock User"],
	"Logistics": ["Stock User"],
	"E-Secretary": ["Employee"],
	"Production HOD": ["Manufacturing Manager"],
	"Maintenance Supervisor": ["Manufacturing User"],
	"R&D": ["Manufacturing User"],
	"CEO": ["System Manager", "Accounts Manager"],
	"Financial Controller": ["Accounts Manager"],
	"Printing Supervisor": ["Manufacturing User"],
	"Pro": ["Stock User"],
	"Marketing Manager": ["Sales Manager"],
	"Production Supervisor": ["Manufacturing User"],
	"Payable": ["Accounts User"],
	"Maintenance Supervisor 2": ["Manufacturing User"],
	"Costing": ["Accounts User"],
}

# Department to ERPNext role mapping (fallback)
DEPT_ROLE_MAPPING = {
	"PRODUCTION DEP": ["Manufacturing User"],
	"LOGISTICS": ["Stock User"],
	"RECEPTION": ["Employee"],
	"ENGINEERING DEP": ["Manufacturing User"],
	"IT DEP": ["System Manager"],
	"ACCOUNTS": ["Accounts User"],
	"MAINTENANCE DEP": ["Manufacturing User"],
	"FINANCE": ["Accounts Manager"],
	"PRINTING DEP": ["Manufacturing User"],
	"MARKETING DEP": ["Sales User"],
}


def import_users_from_csv(csv_file_path):
	"""Import users from CSV file"""
	users_created = []
	channels_created = {}
	department_users = {}  # Track users by department for channel assignment
	
	# Get default workspace (Raven workspace)
	workspace = get_or_create_workspace()
	
	with open(csv_file_path, 'r', encoding='utf-8') as file:
		# Skip first line (header comment)
		next(file)
		reader = csv.DictReader(file)
		
		for row in reader:
			# Skip header rows and empty rows
			if not row.get('Name') or row.get('Name').strip() == '':
				continue
			
			name = row.get('Name', '').strip()
			designation = row.get('Designation', '').strip()
			department = row.get('Department', '').strip()
			email = row.get('Email ID', '').strip()
			phone = row.get('PHONE NO', '').strip()
			
			# Skip if email is N/A or empty
			if not email or email.upper() == 'N/A':
				frappe.log_error(
					f"Skipping user {name} - no valid email",
					"User Import"
				)
				continue
			
			# Normalize email
			email = email.lower().strip()
			
			# Get roles for this user
			roles = get_roles_for_user(designation, department)
			
			# Create or update user
			user = create_or_update_user(
				email=email,
				full_name=name,
				roles=roles,
				phone=phone
			)
			
			if user:
				users_created.append(user.name)
				
				# Track user by department for channel assignment
				if department:
					if department not in department_users:
						department_users[department] = []
					department_users[department].append(user.name)
	
	# Create channels for each department
	for dept, user_list in department_users.items():
		if dept and dept.strip():
			channel_name = create_department_channel(dept, workspace, user_list)
			if channel_name:
				channels_created[dept] = channel_name
	
	return {
		"users_created": len(users_created),
		"channels_created": len(channels_created),
		"user_list": users_created,
		"channel_list": channels_created
	}


def get_roles_for_user(designation, department):
	"""Get roles for user based on designation and department"""
	roles = ["Employee", "Raven User"]  # Default roles
	
	# First try designation-based mapping
	if designation and designation in ROLE_MAPPING:
		roles.extend(ROLE_MAPPING[designation])
	else:
		# Fallback to department-based mapping
		if department and department.upper() in DEPT_ROLE_MAPPING:
			roles.extend(DEPT_ROLE_MAPPING[department.upper()])
	
	# Remove duplicates while preserving order
	seen = set()
	unique_roles = []
	for role in roles:
		if role not in seen:
			seen.add(role)
			unique_roles.append(role)
	
	return unique_roles


def create_or_update_user(email, full_name, roles, phone=None):
	"""Create or update user in ERPNext"""
	try:
		# Split full name
		name_parts = full_name.split(' ', 1)
		first_name = name_parts[0] if name_parts else full_name
		last_name = name_parts[1] if len(name_parts) > 1 else ''
		
		if frappe.db.exists("User", email):
			# Update existing user
			user = frappe.get_doc("User", email)
			user.first_name = first_name
			user.last_name = last_name
			if phone:
				user.phone = phone.replace(' ', '').replace('-', '')
			user.enabled = 1
			user.save()
			frappe.db.commit()
		else:
			# Create new user
			user = frappe.new_doc("User")
			user.email = email
			user.first_name = first_name
			user.last_name = last_name
			user.enabled = 1
			user.user_type = "System User"
			user.send_welcome_email = 0  # Don't send welcome email for bulk import
			
			if phone:
				user.phone = phone.replace(' ', '').replace('-', '')
			
			user.insert(ignore_permissions=True)
			frappe.db.commit()
		
		# Add roles
		current_roles = [r.role for r in user.get("roles")]
		for role in roles:
			if role not in current_roles:
				user.append("roles", {"role": role})
		
		user.save(ignore_permissions=True)
		frappe.db.commit()
		
		# Ensure Raven User is created
		if "Raven User" in roles:
			ensure_raven_user(user.name)
		
		return user
		
	except Exception as e:
		frappe.log_error(
			f"Error creating user {email}: {str(e)}",
			"User Import Error"
		)
		return None


def ensure_raven_user(user_id):
	"""Ensure Raven User record exists"""
	try:
		if not frappe.db.exists("Raven User", {"user": user_id}):
			raven_user = frappe.new_doc("Raven User")
			raven_user.user = user_id
			user_doc = frappe.get_doc("User", user_id)
			raven_user.full_name = user_doc.full_name or user_doc.first_name
			raven_user.first_name = user_doc.first_name
			raven_user.enabled = user_doc.enabled
			raven_user.insert(ignore_permissions=True)
			frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Error creating Raven User for {user_id}: {str(e)}", "Raven User Creation")


def get_or_create_workspace():
	"""Get or create default Raven workspace"""
	workspace_name = "Raven"
	
	# Try to get existing workspace
	workspace = frappe.db.get_value("Raven Workspace", {"workspace_name": workspace_name}, "name")
	
	if not workspace:
		# Create workspace
		workspace_doc = frappe.new_doc("Raven Workspace")
		workspace_doc.workspace_name = workspace_name
		workspace_doc.type = "Public"
		workspace_doc.insert(ignore_permissions=True)
		frappe.db.commit()
		workspace = workspace_doc.name
	
	return workspace


def create_department_channel(department, workspace, user_list):
	"""Create a public channel for department and add users"""
	try:
		# Clean department name for channel name
		channel_name = department.strip().replace(' DEP', '').replace('DEP', '').strip()
		# Generate channel ID (slug-like name)
		channel_id = channel_name.lower().replace(' ', '-').replace('_', '-')
		# Remove any special characters
		channel_id = ''.join(c for c in channel_id if c.isalnum() or c == '-')
		
		# Check if channel already exists by channel_name (more reliable)
		existing_channel_name = frappe.db.get_value("Raven Channel", {"channel_name": channel_name}, "name")
		if existing_channel_name:
			# Add users who are not already members
			add_users_to_channel(existing_channel_name, user_list, None)
			return existing_channel_name
		
		# Create new channel
		channel = frappe.new_doc("Raven Channel")
		channel.type = "Public"
		channel.channel_name = channel_name
		channel.workspace = workspace
		channel.is_direct_message = 0
		channel.is_self_message = 0
		channel.flags.do_not_add_member = True  # We'll add members manually
		channel.insert(ignore_permissions=True)
		frappe.db.commit()
		
		# Add users to channel
		add_users_to_channel(channel.name, user_list, channel)
		
		return channel.name
		
	except Exception as e:
		frappe.log_error(
			f"Error creating channel for department {department}: {str(e)}",
			"Channel Creation Error"
		)
		return None


def add_users_to_channel(channel_id, user_list, channel_doc=None):
	"""Add users to a Raven channel"""
	try:
		# Get existing members
		existing_members = [
			m.user_id for m in frappe.get_all(
				"Raven Channel Member",
				filters={"channel_id": channel_id},
				fields=["user_id"]
			)
		]
		
		# Add new members
		for user_id in user_list:
			# Check if user has Raven User role
			user_roles = frappe.get_roles(user_id)
			if "Raven User" not in user_roles:
				continue
			
			# Ensure Raven User exists
			ensure_raven_user(user_id)
			
			# Add to channel if not already a member
			if user_id not in existing_members:
				member = frappe.new_doc("Raven Channel Member")
				member.channel_id = channel_id
				member.user_id = user_id
				member.is_admin = 0
				member.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
	except Exception as e:
		frappe.log_error(
			f"Error adding users to channel {channel_id}: {str(e)}",
			"Channel Member Addition Error"
		)


@frappe.whitelist()
def import_users_from_file(csv_path=None):
	"""Whitelisted method to import users - call from UI or console"""
	import os
	
	# If no path provided, use default
	if not csv_path:
		# Try multiple possible locations
		possible_paths = [
			os.path.join(frappe.get_site_path(), 'David_FX_All_Internal_Users_Email_List.csv'),
			os.path.join(frappe.get_site_path(), '..', 'David_FX_All_Internal_Users_Email_List.csv'),
			os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', '..', 'David_FX_All_Internal_Users_Email_List.csv'),
		]
		
		for path in possible_paths:
			if os.path.exists(path):
				csv_path = path
				break
		
		if not csv_path or not os.path.exists(csv_path):
			frappe.throw(_("CSV file not found. Please provide the full path to the CSV file."))
	
	if not os.path.exists(csv_path):
		frappe.throw(_("CSV file not found at: {0}").format(csv_path))
	
	result = import_users_from_csv(csv_path)
	
	frappe.msgprint(_(
		"Import completed! Created {0} users and {1} channels."
	).format(result["users_created"], result["channels_created"]))
	
	return result
