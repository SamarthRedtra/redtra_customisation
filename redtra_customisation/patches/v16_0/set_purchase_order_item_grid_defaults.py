"""Apply the approved Purchase Order item-grid layout to active users."""

from redtra_customisation.purchase_order_grid import (
	apply_purchase_order_item_grid_defaults_to_users,
)


def execute():
	apply_purchase_order_item_grid_defaults_to_users()
