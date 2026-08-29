"""Default Purchase Order item-grid layout."""

from redtra_customisation.grid_defaults import apply_grid_default_to_users


PARENT_DOCTYPE = "Purchase Order"
CHILD_DOCTYPE = "Purchase Order Item"
PURCHASE_ORDER_ITEM_COLUMNS = (
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
)


def apply_purchase_order_item_grid_defaults_to_users():
	"""Set the approved grid layout for every active Desk user."""
	apply_grid_default_to_users(PARENT_DOCTYPE, CHILD_DOCTYPE, PURCHASE_ORDER_ITEM_COLUMNS)


def get_purchase_order_item_columns():
	return [dict(column) for column in PURCHASE_ORDER_ITEM_COLUMNS]
