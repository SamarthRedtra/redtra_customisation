"""Apply the approved Purchase Invoice item-grid layout to active users."""

from redtra_customisation.purchase_invoice_grid import (
	apply_purchase_invoice_item_grid_defaults_to_users,
)


def execute():
	apply_purchase_invoice_item_grid_defaults_to_users()
