"""Install managed Pampa Supplier Invoice and G/Received Note formats."""

from redtra_customisation.purchase_print_formats import ensure_pampa_purchase_print_formats


def execute():
	"""Replace only the two named custom buying print formats."""
	ensure_pampa_purchase_print_formats()
