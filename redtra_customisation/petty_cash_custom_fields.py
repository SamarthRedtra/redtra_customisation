"""Audit links for Payment Entries and GL Entries created from petty cash vouchers."""

PETTY_CASH_LINK_CUSTOM_FIELDS = {
	"Payment Entry": [
		{
			"fieldname": "custom_petty_cash_entry",
			"fieldtype": "Link",
			"label": "Petty Cash Entry",
			"options": "Petty Cash Entry",
			"insert_after": "custom_cash_bank_entry",
			"read_only": 1,
			"allow_on_submit": 1,
		},
	],
	"GL Entry": [
		{
			"fieldname": "custom_petty_cash_entry",
			"fieldtype": "Link",
			"label": "Petty Cash Entry",
			"options": "Petty Cash Entry",
			"insert_after": "voucher_no",
			"read_only": 1,
			"allow_on_submit": 1,
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
	],
}
