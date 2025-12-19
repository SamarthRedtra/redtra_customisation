import frappe
from erpnext.manufacturing.doctype.bom_creator.bom_creator import BOMCreator
from erpnext.manufacturing.doctype.bom.bom import get_bom_item_rate
from frappe.utils import flt


class CustomBOMCreator(BOMCreator):
	"""
	Custom BOM Creator class to fix TypeError: can't multiply sequence by non-int of type 'float'
	This ensures row.rate is always converted to float before multiplication.
	"""
	
	def get_raw_material_cost(self, fg_item=None):
		"""
		Override to ensure row.rate is converted to float before multiplication.
		This fixes the issue where row.rate might be a string instead of float.
		"""
		if not fg_item:
			fg_item = self.item_code

		amount = 0
		for row in self.items:
			if row.fg_item != fg_item:
				continue

			if not row.is_expandable:
				# get_bom_item_rate might return a string, ensure it's float
				row.rate = flt(get_bom_item_rate(
					{
						"company": self.company,
						"item_code": row.item_code,
						"bom_no": "",
						"qty": row.qty,
						"uom": row.uom,
						"stock_uom": row.stock_uom,
						"conversion_factor": row.conversion_factor,
						"sourced_by_supplier": row.sourced_by_supplier,
					},
					self,
				))
			else:
				row.rate = flt(self.get_raw_material_cost(row.item_code) * row.conversion_factor)

			# Ensure both rate and qty are floats before multiplication
			# This prevents TypeError when row.rate is a string
			row.amount = flt(flt(row.rate) * flt(row.qty))
			amount += flt(row.amount)

		return amount
