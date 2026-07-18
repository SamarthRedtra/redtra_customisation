# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt


def get_overtime_custom_fields():
	return {
		"Attendance": [
			{
				"fieldname": "overtime_section",
				"fieldtype": "Section Break",
				"label": "Overtime",
				"insert_after": "early_exit",
			},
			{
				"fieldname": "overtime_hours",
				"fieldtype": "Float",
				"label": "Overtime Hours",
				"precision": 2,
				"read_only": 1,
				"insert_after": "overtime_section",
			},
			{
				"fieldname": "overtime_request",
				"fieldtype": "Link",
				"label": "Overtime Request",
				"options": "Overtime Request",
				"read_only": 1,
				"insert_after": "overtime_hours",
			},
		],
		"Payroll Settings": [
			{
				"fieldname": "overtime_section",
				"fieldtype": "Section Break",
				"label": "Overtime",
				"insert_after": "column_break_zi9y",
			},
			{
				"default": "0",
				"fieldname": "auto_create_overtime_request",
				"fieldtype": "Check",
				"label": "Auto Create Overtime Request",
				"description": "Automatically create Overtime Request from Attendance when overtime hours exist",
				"insert_after": "overtime_section",
			},
			{
				"fieldname": "food_allowance_section",
				"fieldtype": "Section Break",
				"label": "Food Allowance",
				"insert_after": "auto_create_overtime_request",
			},
			{
				"default": "0",
				"fieldname": "enable_food_allowance",
				"fieldtype": "Check",
				"label": "Enable Food Allowance",
				"insert_after": "food_allowance_section",
			},
			{
				"default": "12",
				"fieldname": "food_allowance_normal_days_threshold",
				"fieldtype": "Float",
				"label": "Normal Days Threshold (Hours)",
				"insert_after": "enable_food_allowance",
			},
			{
				"default": "0",
				"fieldname": "food_allowance_holiday_weekend_threshold",
				"fieldtype": "Float",
				"label": "Holiday/Weekend Threshold (Hours)",
				"insert_after": "food_allowance_normal_days_threshold",
			},
			{
				"depends_on": "eval:doc.enable_food_allowance",
				"fieldname": "food_allowance_salary_component",
				"fieldtype": "Link",
				"label": "Food Allowance Salary Component",
				"options": "Salary Component",
				"insert_after": "food_allowance_holiday_weekend_threshold",
			},
			{
				"depends_on": "eval:doc.enable_food_allowance",
				"fieldname": "food_allowance_amount",
				"fieldtype": "Currency",
				"label": "Food Allowance Amount (Per Day)",
				"description": "Amount per qualifying day when threshold is crossed",
				"insert_after": "food_allowance_salary_component",
			},
		],
		"Salary Slip": [
			{
				"fieldname": "custom_avoid_absenteeism",
				"fieldtype": "Check",
				"label": "Avoid Absenteeism",
				"insert_after": "payment_days",
				"default": "0",
			},
			{
				"fieldname": "overtime_section",
				"fieldtype": "Section Break",
				"label": "Overtime",
				"insert_after": "custom_avoid_absenteeism",
			},
			{
				"fieldname": "overtime_requests",
				"fieldtype": "Table",
				"options": "Salary Slip Overtime Request",
				"read_only": 1,
				"insert_after": "overtime_section",
			},
			{
				"fieldname": "total_overtime_hours",
				"fieldtype": "Float",
				"label": "Total Overtime Hours",
				"precision": 2,
				"read_only": 1,
				"insert_after": "overtime_requests",
			},
			{
				"fieldname": "holidays_overtime_hours",
				"fieldtype": "Float",
				"label": "Holidays Overtime Hours",
				"read_only": 1,
				"insert_after": "total_overtime_hours",
			},
			{
				"fieldname": "food_allowance_counts",
				"fieldtype": "Int",
				"label": "Food Allowance Counts",
				"read_only": 1,
				"insert_after": "holidays_overtime_hours",
			},
		],
		"Employee Attendance Tool": [
			{
				"fieldname": "custom_from_date",
				"fieldtype": "Date",
				"label": "From Date",
				"insert_after": "date",
			},
			{
				"fieldname": "custom_to_date",
				"fieldtype": "Date",
				"label": "To Date",
				"insert_after": "custom_from_date",
			},
		],
	}


def get_work_order_custom_fields():
	return {
		"Work Order": [
			{
				"fieldname": "custom_customer",
				"fieldtype": "Link",
				"label": "Customer",
				"options": "Customer",
				"insert_after": "company",
			},
		],
	}


def get_sales_partner_commission_custom_fields():
	return {
		"Sales Order": [
			{
				"fieldname": "custom_sales_partner_commission_percentage",
				"fieldtype": "Percent",
				"label": "Sales Partner Commission %",
				"read_only": 1,
				"insert_after": "sales_partner",
			},
			{
				"fieldname": "custom_sales_partner_commission_amount",
				"fieldtype": "Currency",
				"label": "Sales Partner Commission Amount",
				"read_only": 1,
				"insert_after": "custom_sales_partner_commission_percentage",
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "custom_sales_partner_commission_percentage",
				"fieldtype": "Percent",
				"label": "Sales Partner Commission %",
				"read_only": 1,
				"insert_after": "sales_partner",
			},
			{
				"fieldname": "custom_sales_partner_commission_amount",
				"fieldtype": "Currency",
				"label": "Sales Partner Commission Amount",
				"read_only": 1,
				"insert_after": "custom_sales_partner_commission_percentage",
			},
			{
				"default": "0",
				"fieldname": "custom_commission_recorded",
				"fieldtype": "Check",
				"label": "Commission Recorded on Payment",
				"read_only": 1,
				"hidden": 1,
				"insert_after": "custom_sales_partner_commission_amount",
			},
		],
	}
