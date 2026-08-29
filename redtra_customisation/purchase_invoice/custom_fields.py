"""Custom fields for Purchase Invoice rounding."""

PURCHASE_INVOICE_ROUNDING_CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "custom_round_off_account",
			"fieldtype": "Link",
			"label": "Round Off Account",
			"options": "Account",
			"insert_after": "rounding_adjustment",
			"description": "Optional override for rounding GL posting. Defaults to Company Round Off Account.",
		},
	],
}

PURCHASE_INVOICE_ADJUSTMENT_CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": "custom_purchase_invoice_adjustment_account",
			"fieldtype": "Link",
			"label": "Purchase Invoice Adjustment Account",
			"options": "Account",
			"insert_after": "round_off_account",
		},
		{
			"fieldname": "custom_default_purchase_invoice_tax_template",
			"fieldtype": "Link",
			"label": "Default Purchase Invoice Tax Template",
			"options": "Purchase Taxes and Charges Template",
			"insert_after": "custom_purchase_invoice_adjustment_account",
		},
	],
	"Purchase Invoice": [
		{
			"fieldname": "custom_adjustment_total",
			"fieldtype": "Currency",
			"label": "Adjustment Total",
			"insert_after": "discount_amount",
			"read_only": 1,
			"no_copy": 1,
			"depends_on": "eval:doc.custom_adjustment_total",
		},
		{
			"fieldname": "custom_purchase_discount_total",
			"fieldtype": "Currency",
			"label": "Item Discount Total",
			"insert_after": "custom_adjustment_total",
			"read_only": 1,
			"no_copy": 1,
		},
	],
	"Purchase Taxes and Charges": [
		{
			"fieldname": "custom_is_purchase_invoice_adjustment",
			"fieldtype": "Check",
			"label": "Purchase Invoice Adjustment",
			"default": "0",
			"hidden": 1,
			"read_only": 1,
		},
		{
			"fieldname": "custom_is_purchase_invoice_item_adjustment",
			"fieldtype": "Check",
			"label": "Purchase Invoice Item Adjustment",
			"default": "0",
			"hidden": 1,
			"read_only": 1,
		},
		{
			"fieldname": "custom_uses_adjusted_tax_base",
			"fieldtype": "Check",
			"label": "Uses Adjusted Tax Base",
			"default": "0",
			"hidden": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_original_charge_type",
			"fieldtype": "Data",
			"label": "Original Charge Type",
			"hidden": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_original_row_id",
			"fieldtype": "Data",
			"label": "Original Row ID",
			"hidden": 1,
			"read_only": 1,
			"no_copy": 1,
		},
	],
	"Purchase Invoice Item": [
		{
			"fieldname": "custom_purchase_discount_amount",
			"fieldtype": "Currency",
			"label": "Discount / Unit",
			"insert_after": "amount",
			"in_list_view": 1,
		},
		{
			"fieldname": "custom_purchase_discount_account",
			"fieldtype": "Link",
			"label": "Discount Account",
			"options": "Account",
			"insert_after": "custom_purchase_discount_amount",
			"in_list_view": 1,
		},
		{
			"fieldname": "custom_item_adjustment_amount",
			"fieldtype": "Currency",
			"label": "Adjustment",
			"insert_after": "amount",
			"in_list_view": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_item_adjustment_account",
			"fieldtype": "Link",
			"label": "Adjustment Account",
			"options": "Account",
			"insert_after": "custom_item_adjustment_amount",
			"in_list_view": 1,
			"no_copy": 1,
		},
	],
}

# Legacy point-adjustment fields kept hidden for existing data compatibility.
PURCHASE_INVOICE_POINT_ADJUSTMENT_CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "point_adjustments_section",
			"fieldtype": "Section Break",
			"label": "Point Adjustments",
			"insert_after": "items",
			"collapsible": 1,
			"hidden": 1,
		},
		{
			"fieldname": "point_adjustments",
			"fieldtype": "Table",
			"label": "Point Adjustments",
			"options": "Purchase Invoice Point Adjustment",
			"insert_after": "point_adjustments_section",
			"hidden": 1,
		},
		{
			"fieldname": "custom_total_point_adjustment",
			"fieldtype": "Currency",
			"label": "Total Point Adjustment",
			"insert_after": "point_adjustments",
			"read_only": 1,
			"hidden": 1,
		},
	],
	"Purchase Invoice Item": [
		{
			"fieldname": "custom_point_adjustment_total",
			"fieldtype": "Currency",
			"label": "Point Adjustment",
			"insert_after": "amount",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "custom_adjusted_net_amount",
			"fieldtype": "Currency",
			"label": "Adjusted Net Amount",
			"insert_after": "custom_point_adjustment_total",
			"read_only": 1,
			"hidden": 1,
		},
	],
}
