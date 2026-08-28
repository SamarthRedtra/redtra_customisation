"""Install the managed portrait Pampa Purchase Order print format."""

from redtra_customisation.purchase_order_print_format import ensure_pampa_purchase_order_print_format


def execute():
	"""Create optional PO print fields and replace the legacy landscape layout."""
	ensure_pampa_purchase_order_print_format()
