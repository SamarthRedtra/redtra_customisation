"""Controls for the standard-ledger item conversion Stock Entry type."""

import frappe
from frappe import _
from frappe.utils import flt


ITEM_CONVERSION_TYPE = "Item Conversion / Dismantling"
ITEM_CONVERSION_PURPOSE = "Material Transfer"
# Ignore small split/rounding gaps when dismantling one value into multiple items.
ITEM_CONVERSION_ROUNDING_TOLERANCE = 1.0


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
	source_value, output_value = get_item_conversion_totals(doc)
	difference = flt(output_value - source_value, precision)

	if abs(difference) > ITEM_CONVERSION_ROUNDING_TOLERANCE:
		frappe.throw(
			_(
				"Total output valuation must equal total source valuation. "
				"Source: {0}, Output: {1}, Difference: {2}. "
				"Distribute the source value across output item Basic Rate fields."
			).format(source_value, output_value, difference)
		)


def get_item_conversion_totals(doc):
	"""Return source and output valuation totals for an item-conversion entry."""
	source_value = 0.0
	output_value = 0.0

	for item in doc.get("items"):
		line_value = flt(item.basic_amount) or flt(item.amount)
		if item.s_warehouse and not item.t_warehouse:
			source_value += line_value
		elif item.t_warehouse and not item.s_warehouse:
			output_value += line_value

	return (
		flt(source_value, doc.precision("total_outgoing_value") or 2),
		flt(output_value, doc.precision("total_incoming_value") or 2),
	)
