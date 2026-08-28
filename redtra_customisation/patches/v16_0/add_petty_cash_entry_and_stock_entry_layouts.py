"""Install the Petty Cash Entry print format and Stock Entry layout overrides."""

from redtra_customisation.petty_cash_print_format import ensure_petty_cash_print_format
from redtra_customisation.stock_entry_print_formats import ensure_stock_entry_print_formats


def execute():
	ensure_petty_cash_print_format()
	ensure_stock_entry_print_formats()
