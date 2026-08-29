"""Checks for the shared Purchase Invoice item-grid layout."""

from redtra_customisation.purchase_invoice_grid import get_purchase_invoice_item_columns


def test_purchase_invoice_item_grid_columns_match_approved_layout():
	assert get_purchase_invoice_item_columns() == [
		{"fieldname": "item_code", "columns": 3, "sticky": 1},
		{"fieldname": "item_name", "columns": 5, "sticky": 1},
		{"fieldname": "description", "columns": 2, "sticky": 0},
		{"fieldname": "uom", "columns": 2, "sticky": 0},
		{"fieldname": "cost_center", "columns": 2, "sticky": 0},
		{"fieldname": "qty", "columns": 2, "sticky": 0},
		{"fieldname": "rate", "columns": 3, "sticky": 0},
		{"fieldname": "amount", "columns": 2, "sticky": 0},
		{"fieldname": "custom_item_adjustment_amount", "columns": 2, "sticky": 0},
		{"fieldname": "custom_item_adjustment_account", "columns": 2, "sticky": 0},
		{"fieldname": "custom_purchase_discount_amount", "columns": 2, "sticky": 0},
		{"fieldname": "custom_purchase_discount_account", "columns": 2, "sticky": 0},
	]
