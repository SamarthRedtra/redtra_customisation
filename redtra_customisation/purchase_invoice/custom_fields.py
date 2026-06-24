"""Custom fields for Purchase Invoice point-level adjustments."""

PURCHASE_INVOICE_POINT_ADJUSTMENT_CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "point_adjustments_section",
			"fieldtype": "Section Break",
			"label": "Point Adjustments",
			"insert_after": "items",
			"collapsible": 1,
		},
		{
			"fieldname": "point_adjustments",
			"fieldtype": "Table",
			"label": "Point Adjustments",
			"options": "Purchase Invoice Point Adjustment",
			"insert_after": "point_adjustments_section",
		},
		{
			"fieldname": "custom_total_point_adjustment",
			"fieldtype": "Currency",
			"label": "Total Point Adjustment",
			"insert_after": "point_adjustments",
			"read_only": 1,
		},
	],
	"Purchase Invoice Item": [
		{
			"fieldname": "custom_point_adjustment_total",
			"fieldtype": "Currency",
			"label": "Point Adjustment",
			"insert_after": "amount",
			"read_only": 1,
			"in_list_view": 1,
		},
		{
			"fieldname": "custom_adjusted_net_amount",
			"fieldtype": "Currency",
			"label": "Adjusted Net Amount",
			"insert_after": "custom_point_adjustment_total",
			"read_only": 1,
		},
	],
}
