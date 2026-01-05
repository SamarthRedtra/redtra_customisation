# Copyright (c) 2024, Redtra Customisation
# License: MIT

"""
Service Item Account Validation
Enforces expense or income account selection for non-stock, non-asset items.
Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import frappe
from frappe import _


class ServiceItemValidator:
	"""
	Validator for service item account requirements.
	Ensures non-stock, non-asset items have proper expense or income accounts.
	"""
	
	@staticmethod
	def is_validation_enabled():
		"""Check if service item account validation is enabled"""
		try:
			settings = frappe.get_single("Redtra Custom Setting")
			return settings.get("service_item_account_mandatory", 0)
		except Exception:
			return False
	
	@staticmethod
	def is_service_item(item_doc):
		"""
		Determine if an item is a service item requiring account validation.
		Service items are non-stock, non-asset items.
		"""
		return (
			not item_doc.is_stock_item and 
			not item_doc.is_fixed_asset and
			item_doc.item_group != "Products"  # Exclude product groups that might be stock
		)
	
	@staticmethod
	def validate_service_item_accounts(item_doc):
		"""
		Validate that service items have required expense or income accounts.
		Requirements: 11.1, 11.2, 11.4
		"""
		
		# Skip validation if not enabled
		if not ServiceItemValidator.is_validation_enabled():
			return
		
		# Skip validation if not a service item
		if not ServiceItemValidator.is_service_item(item_doc):
			return
		
		# Check if item has expense account (for purchase items)
		has_expense_account = bool(item_doc.expense_account)
		
		# Check if item has income account (for sales items)  
		has_income_account = bool(item_doc.income_account)
		
		# Service items should have at least one account configured
		if not has_expense_account and not has_income_account:
			frappe.throw(_(
				"Service Item '{0}' must have either an Expense Account or Income Account configured. "
				"Please set the appropriate account in the Item master."
			).format(item_doc.item_name or item_doc.name))
		
		# Validate expense account if provided
		if has_expense_account:
			ServiceItemValidator.validate_expense_account(item_doc.expense_account, item_doc.company)
		
		# Validate income account if provided
		if has_income_account:
			ServiceItemValidator.validate_income_account(item_doc.income_account, item_doc.company)
	
	@staticmethod
	def validate_expense_account(expense_account, company):
		"""Validate that expense account is appropriate for service items"""
		
		if not expense_account:
			return
		
		# Check if account exists and belongs to the company
		account_details = frappe.db.get_value(
			"Account", 
			expense_account, 
			["account_type", "root_type", "company", "is_group"], 
			as_dict=True
		)
		
		if not account_details:
			frappe.throw(_("Expense Account '{0}' does not exist").format(expense_account))
		
		if account_details.company != company:
			frappe.throw(_("Expense Account '{0}' does not belong to company '{1}'").format(
				expense_account, company))
		
		if account_details.is_group:
			frappe.throw(_("Expense Account '{0}' cannot be a group account").format(expense_account))
		
		# Ensure it's an expense account
		if account_details.root_type != "Expense":
			frappe.throw(_("Account '{0}' is not an Expense account. Please select a valid expense account.").format(
				expense_account))
	
	@staticmethod
	def validate_income_account(income_account, company):
		"""Validate that income account is appropriate for service items"""
		
		if not income_account:
			return
		
		# Check if account exists and belongs to the company
		account_details = frappe.db.get_value(
			"Account", 
			income_account, 
			["account_type", "root_type", "company", "is_group"], 
			as_dict=True
		)
		
		if not account_details:
			frappe.throw(_("Income Account '{0}' does not exist").format(income_account))
		
		if account_details.company != company:
			frappe.throw(_("Income Account '{0}' does not belong to company '{1}'").format(
				income_account, company))
		
		if account_details.is_group:
			frappe.throw(_("Income Account '{0}' cannot be a group account").format(income_account))
		
		# Ensure it's an income account
		if account_details.root_type != "Income":
			frappe.throw(_("Account '{0}' is not an Income account. Please select a valid income account.").format(
				income_account))
	
	@staticmethod
	def get_validation_message(item_doc):
		"""
		Get a helpful validation message for service items.
		This can be used in UI to guide users.
		"""
		
		if not ServiceItemValidator.is_service_item(item_doc):
			return ""
		
		if not ServiceItemValidator.is_validation_enabled():
			return ""
		
		has_expense = bool(item_doc.expense_account)
		has_income = bool(item_doc.income_account)
		
		if not has_expense and not has_income:
			return _("This service item requires either an Expense Account or Income Account to be configured.")
		
		return ""


# Hook functions for integration with ERPNext

def validate_item_accounts(doc, method=None):
	"""
	Validation hook for Item DocType.
	This should be called from hooks.py on Item validate event.
	Requirements: 11.2, 11.4
	"""
	try:
		ServiceItemValidator.validate_service_item_accounts(doc)
	except Exception as e:
		frappe.logger().error(f"Service Item Validation Error: {str(e)}")
		raise


def before_save_item_accounts(doc, method=None):
	"""
	Before save hook for Item DocType.
	This can be used for additional validations or auto-corrections.
	"""
	
	# Auto-set default accounts for service items if validation is enabled
	if (ServiceItemValidator.is_validation_enabled() and 
		ServiceItemValidator.is_service_item(doc)):
		
		# Auto-set expense account if not provided and item is purchasable
		if not doc.expense_account and doc.is_purchase_item:
			default_expense = get_default_expense_account(doc.company)
			if default_expense:
				doc.expense_account = default_expense
				frappe.msgprint(_("Auto-set default expense account: {0}").format(default_expense))
		
		# Auto-set income account if not provided and item is saleable
		if not doc.income_account and doc.is_sales_item:
			default_income = get_default_income_account(doc.company)
			if default_income:
				doc.income_account = default_income
				frappe.msgprint(_("Auto-set default income account: {0}").format(default_income))


def get_default_expense_account(company):
	"""Get default expense account for a company"""
	
	# Try to get from Company defaults
	default_account = frappe.db.get_value("Company", company, "default_expense_account")
	if default_account:
		return default_account
	
	# Fallback to common expense account patterns
	expense_accounts = frappe.db.sql("""
		SELECT name FROM `tabAccount` 
		WHERE company = %s 
		AND root_type = 'Expense'
		AND is_group = 0
		AND (account_name LIKE '%Service%' OR account_name LIKE '%Expense%')
		ORDER BY account_name
		LIMIT 1
	""", company)
	
	return expense_accounts[0][0] if expense_accounts else None


def get_default_income_account(company):
	"""Get default income account for a company"""
	
	# Try to get from Company defaults
	default_account = frappe.db.get_value("Company", company, "default_income_account")
	if default_account:
		return default_account
	
	# Fallback to common income account patterns
	income_accounts = frappe.db.sql("""
		SELECT name FROM `tabAccount` 
		WHERE company = %s 
		AND root_type = 'Income'
		AND is_group = 0
		AND (account_name LIKE '%Service%' OR account_name LIKE '%Income%')
		ORDER BY account_name
		LIMIT 1
	""", company)
	
	return income_accounts[0][0] if income_accounts else None


# Whitelisted API functions

@frappe.whitelist()
def check_service_item_validation_status():
	"""Check if service item validation is enabled"""
	return {
		"enabled": ServiceItemValidator.is_validation_enabled(),
		"message": _("Service item account validation is {}").format(
			_("enabled") if ServiceItemValidator.is_validation_enabled() else _("disabled")
		)
	}


@frappe.whitelist()
def validate_service_item(item_name):
	"""Validate a specific service item"""
	
	if not item_name:
		frappe.throw(_("Item name is required"))
	
	item_doc = frappe.get_doc("Item", item_name)
	
	try:
		ServiceItemValidator.validate_service_item_accounts(item_doc)
		return {
			"valid": True,
			"message": _("Service item validation passed")
		}
	except Exception as e:
		return {
			"valid": False,
			"message": str(e)
		}


@frappe.whitelist()
def get_service_items_without_accounts(company=None):
	"""Get list of service items that don't have proper accounts configured"""
	
	if not ServiceItemValidator.is_validation_enabled():
		return []
	
	conditions = ["is_stock_item = 0", "is_fixed_asset = 0"]
	if company:
		conditions.append(f"company = '{company}'")
	
	items = frappe.db.sql(f"""
		SELECT name, item_name, expense_account, income_account, company
		FROM `tabItem`
		WHERE {' AND '.join(conditions)}
		AND (expense_account IS NULL OR expense_account = '')
		AND (income_account IS NULL OR income_account = '')
		ORDER BY item_name
	""", as_dict=True)
	
	return items