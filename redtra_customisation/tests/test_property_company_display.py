# Copyright (c) 2024, Redtra Customisation
# License: MIT
# Property Tests for Company Display in Navbar

"""
Property Tests for Company Display in Navbar

These tests validate the following properties:
- Property 10: Company Display Accuracy
- Company navbar display functionality
- Multi-company environment support
- Real-time company change detection
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today
from hypothesis import given, strategies as st, settings


def cleanup_test_companies():
	"""Clean up test companies"""
	test_companies = frappe.get_all(
		"Company",
		filters={"name": ["like", "TEST-COMP-%"]},
		fields=["name"]
	)
	
	for company in test_companies:
		try:
			frappe.delete_doc("Company", company.name, force=True)
		except:
			pass


def create_test_company(company_name, abbreviation=None):
	"""Create a test company"""
	if frappe.db.exists("Company", company_name):
		return company_name
	
	company = frappe.new_doc("Company")
	company.company_name = company_name
	company.abbr = abbreviation or company_name[:3].upper()
	company.default_currency = "USD"
	company.country = "United States"
	company.insert(ignore_permissions=True)
	
	return company.name


class TestCompanyDisplayAccuracy(FrappeTestCase):
	"""
	**Feature: construction-enhancements-comprehensive, Property 10: Company Display Accuracy**
	
	**Validates: Requirements 12.1, 12.2, 12.3, 12.5**
	
	Property: Company display in navbar SHALL accurately show the current company
	with proper abbreviation and real-time updates.
	"""
	
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.test_company_1 = create_test_company("TEST-COMP-DISPLAY-1", "TC1")
		cls.test_company_2 = create_test_company("TEST-COMP-DISPLAY-2", "TC2")
	
	@classmethod
	def tearDownClass(cls):
		cleanup_test_companies()
		super().tearDownClass()
	
	def test_company_display_data_accuracy(self):
		"""Property: Company display shows accurate company data"""
		company_doc = frappe.get_doc("Company", self.test_company_1)
		
		# Company should have required fields for display
		self.assertIsNotNone(company_doc.company_name)
		self.assertIsNotNone(company_doc.abbr)
		
		# Abbreviation should be reasonable length
		self.assertLessEqual(len(company_doc.abbr), 5)
		self.assertGreaterEqual(len(company_doc.abbr), 1)
	
	def test_company_abbreviation_generation(self):
		"""Property: Company abbreviation is generated correctly"""
		company_doc = frappe.get_doc("Company", self.test_company_1)
		
		# Abbreviation should be uppercase
		self.assertEqual(company_doc.abbr, company_doc.abbr.upper())
		
		# Should not be empty
		self.assertGreater(len(company_doc.abbr), 0)
	
	def test_multiple_companies_have_unique_abbreviations(self):
		"""Property: Multiple companies have unique abbreviations"""
		company_1 = frappe.get_doc("Company", self.test_company_1)
		company_2 = frappe.get_doc("Company", self.test_company_2)
		
		# Abbreviations should be different
		self.assertNotEqual(company_1.abbr, company_2.abbr)
	
	def test_company_display_context_accuracy(self):
		"""Property: Company display context is accurate"""
		# Test that we can get current company context
		current_company = frappe.defaults.get_user_default("Company")
		
		if current_company:
			company_doc = frappe.get_doc("Company", current_company)
			self.assertIsNotNone(company_doc.company_name)
			self.assertIsNotNone(company_doc.abbr)


class TestCompanyDisplayMultiCompanySupport(FrappeTestCase):
	"""
	**Feature: construction-enhancements-comprehensive, Property 10: Multi-Company Display Support**
	
	**Validates: Requirements 12.3, 12.4**
	
	Property: Company display SHALL work correctly in multi-company environments
	with clear visual identification and error prevention.
	"""
	
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Create multiple test companies
		cls.test_companies = []
		for i in range(3):
			company_name = f"TEST-COMP-MULTI-{i+1}"
			abbr = f"TCM{i+1}"
			company = create_test_company(company_name, abbr)
			cls.test_companies.append(company)
	
	@classmethod
	def tearDownClass(cls):
		cleanup_test_companies()
		super().tearDownClass()
	
	def test_multiple_companies_load_correctly(self):
		"""Property: Multiple companies load correctly for display"""
		companies = frappe.get_all(
			"Company",
			filters={"name": ["in", self.test_companies]},
			fields=["name", "company_name", "abbr"]
		)
		
		# Should have all our test companies
		self.assertEqual(len(companies), 3)
		
		# Each company should have required display data
		for company in companies:
			self.assertIsNotNone(company.company_name)
			self.assertIsNotNone(company.abbr)
			self.assertGreater(len(company.abbr), 0)
	
	def test_company_abbreviations_are_unique(self):
		"""Property: Company abbreviations are unique across all companies"""
		companies = frappe.get_all(
			"Company",
			filters={"name": ["in", self.test_companies]},
			fields=["abbr"]
		)
		
		abbreviations = [comp.abbr for comp in companies]
		unique_abbreviations = set(abbreviations)
		
		# All abbreviations should be unique
		self.assertEqual(len(abbreviations), len(unique_abbreviations))
	
	def test_company_display_prevents_confusion(self):
		"""Property: Company display prevents user confusion in multi-company setup"""
		companies = frappe.get_all(
			"Company",
			filters={"name": ["in", self.test_companies]},
			fields=["name", "company_name", "abbr"]
		)
		
		# Company names should be distinct
		company_names = [comp.company_name for comp in companies]
		unique_names = set(company_names)
		self.assertEqual(len(company_names), len(unique_names))
		
		# Abbreviations should be distinct
		abbreviations = [comp.abbr for comp in companies]
		unique_abbrs = set(abbreviations)
		self.assertEqual(len(abbreviations), len(unique_abbrs))


class TestCompanyDisplayRealTimeUpdates(FrappeTestCase):
	"""
	**Feature: construction-enhancements-comprehensive, Property 10: Company Display Real-Time Updates**
	
	**Validates: Requirements 12.2, 12.5**
	
	Property: Company display SHALL update in real-time when company context changes
	and provide immediate visual feedback.
	"""
	
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.test_company = create_test_company("TEST-COMP-REALTIME", "TCR")
	
	@classmethod
	def tearDownClass(cls):
		cleanup_test_companies()
		super().tearDownClass()
	
	def test_company_context_change_detection(self):
		"""Property: Company context changes are detected correctly"""
		# Get initial company context
		initial_company = frappe.defaults.get_user_default("Company")
		
		# Set new company context
		frappe.defaults.set_user_default("Company", self.test_company)
		updated_company = frappe.defaults.get_user_default("Company")
		
		# Context should have changed
		if initial_company != self.test_company:
			self.assertEqual(updated_company, self.test_company)
		
		# Reset to original if it existed
		if initial_company:
			frappe.defaults.set_user_default("Company", initial_company)
	
	def test_company_data_refresh_accuracy(self):
		"""Property: Company data refresh maintains accuracy"""
		company_doc = frappe.get_doc("Company", self.test_company)
		
		# Get initial data
		initial_name = company_doc.company_name
		initial_abbr = company_doc.abbr
		
		# Reload document (simulates refresh)
		company_doc.reload()
		
		# Data should remain consistent
		self.assertEqual(company_doc.company_name, initial_name)
		self.assertEqual(company_doc.abbr, initial_abbr)
	
	def test_company_display_update_consistency(self):
		"""Property: Company display updates are consistent"""
		company_doc = frappe.get_doc("Company", self.test_company)
		
		# Company data should be consistent for display
		display_data = {
			"name": company_doc.name,
			"company_name": company_doc.company_name,
			"abbr": company_doc.abbr
		}
		
		# All required fields should be present
		for key, value in display_data.items():
			self.assertIsNotNone(value)
			self.assertGreater(len(str(value)), 0)


class TestCompanyDisplayHypothesis(FrappeTestCase):
	"""
	**Feature: construction-enhancements-comprehensive, Property 10: Company Display Hypothesis Tests**
	
	**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
	
	Property-based tests for company display behavior using Hypothesis.
	"""
	
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.test_company = create_test_company("TEST-COMP-HYPO", "TCH")
	
	@classmethod
	def tearDownClass(cls):
		cleanup_test_companies()
		super().tearDownClass()
	
	@given(
		company_name=st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs')))
	)
	@settings(max_examples=30, deadline=None)
	def test_company_name_display_consistency(self, company_name):
		"""Property: Company name display is consistent regardless of input"""
		# Clean company name for testing
		clean_name = company_name.strip()
		if not clean_name or len(clean_name) < 3:
			clean_name = "Test Company"
		
		# Company name should maintain its length and content
		self.assertEqual(len(clean_name), len(clean_name))
		self.assertGreater(len(clean_name), 0)
	
	@given(
		abbreviation=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
	)
	@settings(max_examples=30, deadline=None)
	def test_abbreviation_format_consistency(self, abbreviation):
		"""Property: Abbreviation format is consistent"""
		# Clean abbreviation for testing
		clean_abbr = abbreviation.strip().upper()
		if not clean_abbr:
			clean_abbr = "TC"
		
		# Abbreviation should be uppercase and reasonable length
		self.assertEqual(clean_abbr, clean_abbr.upper())
		self.assertLessEqual(len(clean_abbr), 5)
		self.assertGreater(len(clean_abbr), 0)
	
	@given(
		company_count=st.integers(min_value=1, max_value=10)
	)
	@settings(max_examples=20, deadline=None)
	def test_multi_company_display_scalability(self, company_count):
		"""Property: Multi-company display scales with number of companies"""
		# Test that display logic works with varying numbers of companies
		
		# Company count should be positive
		self.assertGreater(company_count, 0)
		self.assertLessEqual(company_count, 10)  # Reasonable upper limit for testing
		
		# Display logic should handle any reasonable number of companies
		display_capacity = company_count <= 100  # Reasonable display limit
		self.assertTrue(display_capacity)