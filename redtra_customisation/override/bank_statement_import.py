# Copyright (c) 2026, redtra_customisation contributors

import json

import frappe
from erpnext.accounts.doctype.bank_statement_import.bank_statement_import import (
	BankStatementImport as ERPNextBankStatementImport,
)
class CustomBankStatementImport(ERPNextBankStatementImport):
	"""Ensure bank statement import validation works when parent helpers are unavailable."""

	def validate(self):
		doc_before_save = self.get_doc_before_save()
		if (
			not (self.import_file or self.google_sheets_url)
			or (doc_before_save and doc_before_save.import_file != self.import_file)
			or (doc_before_save and doc_before_save.google_sheets_url != self.google_sheets_url)
		):
			template_options_dict = {}
			column_to_field_map = {}
			bank = frappe.get_doc("Bank", self.bank)
			for row in bank.bank_transaction_mapping:
				column_to_field_map[row.file_field] = row.bank_transaction_field
			template_options_dict["column_to_field_map"] = column_to_field_map
			self.template_options = json.dumps(template_options_dict)
			self.template_warnings = ""

		self.set_delimiters_flag()
		self.validate_doctype()

		if self.import_file and not self.import_file.lower().endswith(".txt"):
			self._validate_import_file()
			self.validate_google_sheets_url()
			self.set_payload_count()

	def _validate_import_file(self):
		"""Mirror DataImport.validate_import_file without relying on inherited lookup."""
		if self.import_file:
			self.get_importer()
