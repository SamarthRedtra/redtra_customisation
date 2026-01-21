# Copyright (c) 2024, Redtra Customisation
# License: MIT

"""
Property-Based Tests for Service Item Account Validation
Tests the service item account validation functionality.
Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import frappe
import unittest
from hypothesis import given, strategies as st, settings, assume
from redtra_customisation.redtra_customisation.service_item_validator import (
	ServiceItemValidator,
	validate_item_accounts,
	get_default_expense_account,
	get_default_income_account
)


class TestPropertyServiceItemValidation(unittest.TestCase):
	"""
	Property-based tests for service item validation functionality.
	**Feature: service-item-validation, Property 9: Service Item Validation Consistency**
	**Validates: Requirements 11.1, 11.2, 11.4**
	"""
	
	@classmethod
	def setUpClass(cls):
		"""Set up test data"""
		cls.test_company = "Test Company SIV"
		cls.test_expense_account = "Test Expense Account - TSIV"
		cls.test_income_account = "Test Income Account - TSIV"
		
		# Create test company
		if not frappe.db.exists("Company", cls.test_company):
			company = frappe.new_doc("Company")
			company.company_name = cls.test_company
			company.abbr = "TSIV"
			company.default_currency = "USD"
			company.country = "United States"
			company.flags.ignore_permissions = True
			company.insert()
		
		# Create test accounts
		cls._create_test_accounts()
		
		# Enable service item validation
		cls._enable_service_item_validation()
	
	@classmethod
	def _create_test_accounts(cls):
		"""Create test expense and income accounts"""
		
		# Create expense account
		if not frappe.db.exists("Account", cls.test_expense_account):
			expense_account = frappe.new_doc("Account")
			expense_account.account_name = "Test Expense Account"
			expense_account.company = cls.test_company
			expense_account.root_type = "Expense"
			expense_account.account_type = "Expense Account"
			expense_account.parent_account = f"Expenses - TSIV"
			expense_account.flags.ignore_permissions = True
			expense_account.insert()
		
		# Create income account
		if not frappe.db.exists("Account", cls.test_income_account):
			income_account = frappe.new_doc("Account")
			income_account.account_name = "Test Income Account"
			income_account.company = cls.test_company
			income_account.root_type = "Income"
			income_account.account_type = "Income Account"
			income_account.parent_account = f"Income - TSIV"
			income_account.flags.ignore_permissions = True
			income_account.insert()
	
	@classmethod
	def _enable_service_item_validation(cls):
		"""Enable service item validation in settings"""
		
		settings = frappe.get_single("Redtra Custom Setting")
		settings.service_item_account_mandatory = 1
		settings.flags.ignore_permissions = True
		settings.save()
	
	@given(
		is_stock_item=st.booleans(),
		is_fixed_asset=st.booleans(),
		has_expense_account=st.booleans(),
		has_income_account=st.booleans(),
		is_sales_item=st.booleans(),
		is_purchase_item=st.booleans()
	)
	@settings(max_examples=100, deadline=5000)
	def test_property_service_item_validation_consistency(self, is_stock_item, is_fixed_asset, 
														 has_expense_account, has_income_account,
														 is_sales_item, is_purchase_item):
		"""
		Property: Service item validation should be consistent across all item configurations
		For any combination of item properties, validation should behave predictably.
		**Validates: Requirements 11.1, 11.2, 11.4**
		"""
		
		# Create test item with given properties
		item = self._create_test_item(
			is_stock_item=is_stock_item,
			is_fixed_asset=is_fixed_asset,
			has_expense_account=has_expense_account,
			has_income_account=has_income_account,
			is_sales_item=is_sales_item,
			is_purchase_item=is_purchase_item
		)
		
		# Determine if this is a service item
		is_service_item = ServiceItemValidator.is_service_item(item)
		expected_service_item = not is_stock_item and not is_fixed_asset
		
		# Service item detection should be consistent
		self.assertEqual(is_service_item, expected_service_item,
			f"Service item detection should be consistent: stock={is_stock_item}, asset={is_fixed_asset}")
		
		if is_service_item:
			# Service items should require at least one account
			has_any_account = has_expense_account or has_income_account
			
			try:
				ServiceItemValidator.validate_service_item_accounts(item)
				validation_passed = True
			except frappe.ValidationError:
				validation_passed = False
			
			# Validation should pass only if item has at least one account
			self.assertEqual(validation_passed, has_any_account,
				f"Service item validation should {'pass' if has_any_account else 'fail'} when accounts={'expense' if has_expense_account else ''}{'income' if has_income_account else ''}")
		else:
			# Non-service items should always pass validation
			try:
				ServiceItemValidator.validate_service_item_accounts(item)
				validation_passed = True
			except frappe.ValidationError:
				validation_passed = False
			
			self.assertTrue(validation_passed,
				"Non-service items should always pass validation")
	
	@given(
		validation_enabled=st.booleans(),
		item_count=st.integers(min_value=1, max_value=5)
	)
	@settings(max_examples=30, deadline=5000)
	def test_property_validation_toggle_consistency(self, validation_enabled, item_count):
		"""
		Property: Validation behavior should be consistent when toggled on/off
		For any number of items, enabling/disabling validation should affect all items uniformly.
		**Validates: Requirements 11.3, 11.5**
		"""
		
		# Set validation status
		settings = frappe.get_single("Redtra Custom Setting")
		settings.service_item_account_mandatory = 1 if validation_enabled else 0
		settings.flags.ignore_permissions = True
		settings.save()
		
		# Create multiple service items without accounts
		items = []
		for i in range(item_count):
			item = self._create_test_item(
				is_stock_item=False,
				is_fixed_asset=False,
				has_expense_account=False,
				has_income_account=False,
				item_suffix=f"_toggle_{i}"
			)
			items.append(item)
		
		# Test validation for each item
		for item in items:
			try:
				ServiceItemValidator.validate_service_item_accounts(item)
				validation_passed = True
			except frappe.ValidationError:
				validation_passed = False
			
			# Validation should pass only when disabled or item has accounts
			expected_pass = not validation_enabled  # Items have no accounts
			self.assertEqual(validation_passed, expected_pass,
				f"Validation should {'pass' if expected_pass else 'fail'} when enabled={validation_enabled}")
	
	@given(
		account_type=st.sampled_from(["Expense", "Income", "Asset", "Liability"]),
		is_group_account=st.booleans(),
		correct_company=st.booleans()
	)
	@settings(max_examples=50, deadline=5000)
	def test_property_account_validation_consistency(self, account_type, is_group_account, correct_company):
		"""
		Property: Account validation should be consistent across different account types
		For any account configuration, validation should correctly identify valid accounts.
		**Validates: Requirements 11.2, 11.4**
		"""
		
		# Skip invalid combinations
		assume(not (account_type in ["Asset", "Liability"] and not is_group_account))
		
		# Create test account
		account_name = f"Test {account_type} Account {frappe.generate_hash(length=5)} - TSIV"
		company = self.test_company if correct_company else "Wrong Company"
		
		if not frappe.db.exists("Account", account_name):
			account = frappe.new_doc("Account")
			account.account_name = f"Test {account_type} Account {frappe.generate_hash(length=5)}"
			account.company = company if correct_company else self.test_company  # Create in correct company first
			account.root_type = account_type
			account.is_group = 1 if is_group_account else 0
			
			# Set parent account
			if account_type == "Expense":
				account.parent_account = f"Expenses - TSIV"
			elif account_type == "Income":
				account.parent_account = f"Income - TSIV"
			elif account_type == "Asset":
				account.parent_account = f"Assets - TSIV"
			elif account_type == "Liability":
				account.parent_account = f"Liabilities - TSIV"
			
			account.flags.ignore_permissions = True
			account.insert()
			
			# Update company if needed for testing
			if not correct_company:
				frappe.db.set_value("Account", account_name, "company", company)
		
		# Create service item with this account
		item = self._create_test_item(
			is_stock_item=False,
			is_fixed_asset=False,
			has_expense_account=(account_type == "Expense"),
			has_income_account=(account_type == "Income"),
			custom_expense_account=account_name if account_type == "Expense" else None,
			custom_income_account=account_name if account_type == "Income" else None
		)
		
		# Test validation
		try:
			ServiceItemValidator.validate_service_item_accounts(item)
			validation_passed = True
		except frappe.ValidationError as e:
			validation_passed = False
			error_message = str(e)
		
		# Determine expected result
		if account_type in ["Expense", "Income"]:
			# Should pass only if correct company and not group account
			expected_pass = correct_company and not is_group_account
		else:
			# Asset/Liability accounts should fail for service items
			expected_pass = False
		
		self.assertEqual(validation_passed, expected_pass,
			f"Account validation should {'pass' if expected_pass else 'fail'} for {account_type} account (group={is_group_account}, correct_company={correct_company})")
	
	def _create_test_item(self, **kwargs):
		"""Helper to create test item with specified properties"""
		
		item_name = f"Test Item {frappe.generate_hash(length=8)}{kwargs.get('item_suffix', '')}"
		
		item = frappe.new_doc("Item")
		item.item_code = item_name
		item.item_name = item_name
		item.item_group = "Services" if not kwargs.get('is_stock_item') else "Products"
		item.stock_uom = "Nos"
		item.is_stock_item = kwargs.get('is_stock_item', False)
		item.is_fixed_asset = kwargs.get('is_fixed_asset', False)
		item.is_sales_item = kwargs.get('is_sales_item', True)
		item.is_purchase_item = kwargs.get('is_purchase_item', True)
		item.company = self.test_company
		
		# Set accounts if specified
		if kwargs.get('has_expense_account'):
			item.expense_account = kwargs.get('custom_expense_account', self.test_expense_account)
		
		if kwargs.get('has_income_account'):
			item.income_account = kwargs.get('custom_income_account', self.test_income_account)
		
		item.flags.ignore_permissions = True
		
		return item
	
	@classmethod
	def tearDownClass(cls):
		"""Clean up test data"""
		
		# Clean up test items
		frappe.db.sql("DELETE FROM `tabItem` WHERE item_code LIKE 'Test Item%'")
		
		# Clean up test accounts
		frappe.db.sql("DELETE FROM `tabAccount` WHERE company = %s AND account_name LIKE 'Test%'", cls.test_company)
		
		# Clean up company
		if frappe.db.exists("Company", cls.test_company):
			frappe.delete_doc("Company", cls.test_company, force=True)
		
		# Reset settings
		settings = frappe.get_single("Redtra Custom Setting")
		settings.service_item_account_mandatory = 0
		settings.flags.ignore_permissions = True
		settings.save()
		
		frappe.db.commit()


if __name__ == "__main__":
	unittest.main()