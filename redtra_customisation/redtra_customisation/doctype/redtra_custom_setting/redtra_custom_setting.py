# Copyright (c) 2025, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document


class RedtraCustomSetting(Document):
	def validate(self):
		self.ensure_default_project_commission_slabs()
		self.validate_project_commission_slabs()

	def ensure_default_project_commission_slabs(self):
		if self.get("project_commission_slabs"):
			return

		for slab in (
			{"minimum_value": 0, "maximum_value": 40000, "commission_percentage": 2},
			{"minimum_value": 40000, "maximum_value": 100000, "commission_percentage": 1.5},
			{"minimum_value": 100000, "commission_percentage": 1},
		):
			self.append("project_commission_slabs", slab)

	def validate_project_commission_slabs(self):
		if not self.get("project_commission_slabs"):
			return

		ordered_slabs = sorted(
			self.project_commission_slabs,
			key=lambda slab: (flt(slab.minimum_value), flt(slab.maximum_value or 0)),
		)
		last_maximum = None

		for slab in ordered_slabs:
			minimum_value = flt(slab.minimum_value)
			maximum_value = flt(slab.maximum_value) if slab.maximum_value not in (None, "") else None
			commission_percentage = flt(slab.commission_percentage)

			if minimum_value < 0:
				frappe.throw(_("Project commission slab minimum value cannot be negative"))

			if maximum_value is not None and maximum_value <= minimum_value:
				frappe.throw(_("Project commission slab To Value must be greater than From Value"))

			if commission_percentage < 0:
				frappe.throw(_("Project commission percentage cannot be negative"))

			if last_maximum is not None and minimum_value < last_maximum:
				frappe.throw(_("Project commission slabs cannot overlap"))

			if last_maximum is None and slab != ordered_slabs[0]:
				frappe.throw(_("Open-ended project commission slab must be the last row"))

			last_maximum = maximum_value
