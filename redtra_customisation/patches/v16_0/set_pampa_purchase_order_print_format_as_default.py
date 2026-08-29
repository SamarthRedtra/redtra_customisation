"""Set the approved managed Purchase Order format as the default."""

from redtra_customisation.purchase_order_print_format import (
	ensure_pampa_purchase_order_default_print_format,
)


def execute():
	ensure_pampa_purchase_order_default_print_format()
