"""Controls for the standard-ledger item conversion Stock Entry type."""

import frappe
from frappe import _
from frappe.utils import flt


ITEM_CONVERSION_TYPE = "Item Conversion / Dismantling"
ITEM_CONVERSION_PURPOSE = "Material Transfer"


def is_item_conversion(doc):
	"""Return whether the entry uses Redtra's conversion stock-entry type."""
	return doc.stock_entry_type == ITEM_CONVERSION_TYPE


def prepare_item_conversion_entry(doc, method=None):
	"""Enable manual valuation without Repack's Finished Good behaviour."""
	if not is_item_conversion(doc):
		return

	doc.purpose = ITEM_CONVERSION_PURPOSE
	for item in doc.get("items"):
		item.is_finished_item = 0
		item.set_basic_rate_manually = 1


def validate_item_conversion_entry(doc, method=None):
	"""Keep the conversion's incoming and outgoing inventory values balanced."""
	if not is_item_conversion(doc):
		return

	precision = doc.precision("value_difference") or 2
	tolerance = 1 / (10**precision)
	if abs(flt(doc.value_difference, precision)) >= tolerance:
		frappe.throw(
			_(
				"Total output valuation must equal total source valuation. Distribute the conversion value across the output items."
			)
		)
