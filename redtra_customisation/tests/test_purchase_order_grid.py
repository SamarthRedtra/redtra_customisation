"""Checks for the shared Purchase Order item-grid layout."""

from redtra_customisation.purchase_order_grid import get_purchase_order_item_columns


def test_purchase_order_item_grid_columns_match_approved_layout():
	assert get_purchase_order_item_columns() == [
		{"fieldname": "cost_center", "columns": 2, "sticky": 0},
		{"fieldname": "item_code", "columns": 3, "sticky": 0},
		{"fieldname": "item_name", "columns": 1, "sticky": 0},
		{"fieldname": "description", "columns": 5, "sticky": 0},
		{"fieldname": "qty", "columns": 1, "sticky": 0},
		{"fieldname": "uom", "columns": 1, "sticky": 0},
		{"fieldname": "rate", "columns": 2, "sticky": 0},
		{"fieldname": "amount", "columns": 2, "sticky": 0},
		{"fieldname": "custom_purchase_discount_amount", "columns": 2, "sticky": 0},
		{"fieldname": "custom_purchase_discount_account", "columns": 2, "sticky": 0},
	]
