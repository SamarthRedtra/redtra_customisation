# Copyright (c) 2026, redtra_customisation contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PostDatedCheques(Document):
	def on_cancel(self):
		self.status = "Cancelled"
		self.db_update()
		
	def before_insert(self):
		self.status ="Pending"
						

