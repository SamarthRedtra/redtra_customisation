"""Custom fields owned by the Purchase Order access customisation."""

PURCHASE_ORDER_CUSTOM_FIELDS = {
	"Purchase Order": [
		{
			"fieldname": "custom_purchase_type",
			"fieldtype": "Select",
			"label": "Purchase Type",
			"options": "Domestic\nInternational\nAdmin",
			"insert_after": "supplier_name",
			"reqd": 1,
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "custom_store",
			"fieldtype": "Data",
			"label": "Store",
			"insert_after": "custom_purchase_type",
		},
		{
			"fieldname": "custom_cost_code",
			"fieldtype": "Data",
			"label": "Cost Code",
			"insert_after": "custom_store",
		},
		{
			"fieldname": "custom_boe_no",
			"fieldtype": "Data",
			"label": "BOE No.",
			"insert_after": "custom_cost_code",
		},
	],
}
