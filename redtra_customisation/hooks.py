app_name = "redtra_customisation"
app_title = "Redtra Customisation"
app_publisher = "samarth.upare@redtra.com"
app_description = "Redtra Customisation "
app_email = "samarth.upare@redtra.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext", "construction_management"]


# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "redtra_customisation",
# 		"logo": "/assets/redtra_customisation/logo.png",
# 		"title": "Redtra Customisation",
# 		"route": "/redtra_customisation",
# 		"has_permission": "redtra_customisation.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/redtra_customisation/css/redtra_customisation.css"
app_include_js = [
	"/assets/redtra_customisation/js/list_view_fix.js",
	"/assets/redtra_customisation/js/company_navbar_display.js",
	"/assets/redtra_customisation/js/date_session_override.js",
	"/assets/redtra_customisation/js/date_session_navbar.js",
	"/assets/redtra_customisation/js/general_ledger_extension.js",
	"/assets/redtra_customisation/js/item_quick_entry.js",
	"/assets/redtra_customisation/js/invoice_pdc_connections.js",
	"/assets/redtra_customisation/js/purchase_order_update_items.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/redtra_customisation/css/redtra_customisation.css"
# web_include_js = "/assets/redtra_customisation/js/redtra_customisation.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "redtra_customisation/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
	"Payment Entry": "public/js/payment_entry_pdc.js",
	"Customer": "public/js/customer_pdc_dashboard.js",
	"Sales Invoice": "public/js/sales_invoice_commission.js",
	"Sales Order": "public/js/sales_order_commission.js",
	"Supplier": "public/js/supplier_pdc_dashboard.js",
	"Shift Type": "rhr/doctype/shift_type/shift_type.js",
	"Post Dated Cheques Tool": "redtra_customisation/doctype/post_dated_cheques_tool/post_dated_cheques_tool.js",
	"Post Dated Cheques": "redtra_customisation/doctype/post_dated_cheques/post_dated_cheques.js",
	"Purchase Order": "public/js/purchase_order_nonstock.js",
	"Purchase Invoice": [
		"public/js/purchase_invoice_expense_account.js",
		"public/js/purchase_invoice_rounding.js",
	],
	"Stock Entry": "public/js/stock_entry_item_conversion.js",
	"Item": "public/js/item_expense_account.js",
	"Cash Bank Entry": "redtra_customisation/doctype/cash_bank_entry/cash_bank_entry.js",
}
doctype_list_js = {
	"Post Dated Cheques": "redtra_customisation/doctype/post_dated_cheques/post_dated_cheques_list.js",
	"Cash Bank Entry": "redtra_customisation/doctype/cash_bank_entry/cash_bank_entry_list.js",
}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}
doctype_tree_js = {"Account" : "public/js/account_tree.js",
                   }

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "redtra_customisation/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"redtra_customisation.purchase_print_formats.get_letter_head_html",
	],
}

# Installation
# ------------

# before_install = "redtra_customisation.install.before_install"
after_install = "redtra_customisation.pdc.install.after_install"
after_migrate = "redtra_customisation.pdc.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "redtra_customisation.uninstall.before_uninstall"
# after_uninstall = "redtra_customisation.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "redtra_customisation.utils.before_app_install"
# after_app_install = "redtra_customisation.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "redtra_customisation.utils.before_app_uninstall"
# after_app_uninstall = "redtra_customisation.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "redtra_customisation.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
permission_query_conditions = {
	"Purchase Order": "redtra_customisation.override.purchase_order_permissions.get_permission_query_conditions",
}

has_permission = {
	"Purchase Order": "redtra_customisation.override.purchase_order_permissions.has_permission",
}
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Bank Statement Import": "redtra_customisation.override.bank_statement_import.CustomBankStatementImport",
	"BOM Creator": "redtra_customisation.override.bom_creator.CustomBOMCreator",
	"Purchase Invoice": "redtra_customisation.override.purchase_invoice.CustomPurchaseInvoice",
	"Payment Entry": "redtra_customisation.pdc.payment_entry_override.CustomPaymentEntry",
	"Payroll Entry": "redtra_customisation.rpayroll.doctype.payroll_entry.payroll_entry.CustomPayrollEntry",
	"Salary Slip": "redtra_customisation.rpayroll.doctype.salary_slip.salary_slip_overtime.SalarySlipOvertime",
	"Shift Type": "redtra_customisation.rhr.doctype.shift_type.shift_type.ShiftType",
	"Stock Entry": "redtra_customisation.override.stock_entry.CustomStockEntry",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Attendance": {
		"before_save": "redtra_customisation.rhr.doctype.attendance.attendance_overtime.before_save_attendance",
		"on_submit": "redtra_customisation.rhr.doctype.attendance.attendance_overtime.on_submit_attendance",
		"on_cancel": "redtra_customisation.rhr.doctype.attendance.attendance_overtime.on_cancel_attendance",
	},
 "Purchase Order": {
    "before_insert": [
        "redtra_customisation.override.purchase_order_permissions.set_default_is_nonstock",
        "redtra_customisation.override.purchase_order_permissions.set_purchase_type_defaults",
        "redtra_customisation.override.provisional_purchase_order.set_default_provisional_po",
    ],
    "validate": "redtra_customisation.override.purchase_order_permissions.validate_non_stock_user_po",
    "on_update": "redtra_customisation.override.purchase_order.on_update_po"
 },
 "Purchase Order Item": {
    "before_save": "redtra_customisation.override.provisional_purchase_order.validate_purchase_order_item_rate",
 },
 "Sales Order": {
	"validate": "redtra_customisation.commission.apply_project_wise_commission"
 },
 "Item": {
    "validate": "redtra_customisation.redtra_customisation.service_item_validator.validate_item_accounts",
    "before_save": "redtra_customisation.redtra_customisation.service_item_validator.before_save_item_accounts"
},
"Work Order": {
    "on_submit": "redtra_customisation.override.work_order.auto_complete_job_cards",
    "on_update_after_submit": "redtra_customisation.override.work_order.auto_complete_job_cards",
 },
 "Stock Entry": {
	"before_validate": "redtra_customisation.override.item_conversion.prepare_item_conversion_entry",
	"validate": "redtra_customisation.override.item_conversion.validate_item_conversion_entry",
    "on_submit": "redtra_customisation.override.work_order.auto_complete_job_cards_from_stock_entry",
 },
	"Landed Cost Voucher": {
		"on_submit": "redtra_customisation.override.landed_cost_voucher.reconcile_landed_cost_links",
		"on_cancel": "redtra_customisation.override.landed_cost_voucher.reconcile_landed_cost_links",
	},
	"Sales Invoice": {
		"validate": "redtra_customisation.redtra_customisation.custom.sales_invoice.calculate_profit_and_commission"
	},
	"Sales Person": {
		"validate": "redtra_customisation.redtra_customisation.custom.sales_person.validate_slabs"
	},
	"Workflow Action": {
		"after_insert": "redtra_customisation.pdc.workflow_notifications.send_workflow_system_notification"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"redtra_customisation.pdc.notifications.send_pdc_reminders",
		"redtra_customisation.redtra_customisation.custom.customer_commission.update_customer_commissions"
	]
}

# Testing
# -------

# before_tests = "redtra_customisation.install.before_tests"

# Overriding Methods
# ------------------------------
override_whitelisted_methods = {
	# ERPNext v17+ routes payment schedule RPC via services module without @whitelist.
	"erpnext.accounts.services.payment_schedule.get_payment_terms": (
		"erpnext.controllers.accounts_controller.get_payment_terms"
	),
	"erpnext.accounts.services.payment_schedule.get_payment_term_details": (
		"erpnext.controllers.accounts_controller.get_payment_term_details"
	),
	# Print View sends frm.doc as dict; Frappe typed API expects JSON string.
	"frappe.www.printview.get_html_and_style": (
		"redtra_customisation.override.printview.get_html_and_style"
	),
	"frappe.www.printview.get_rendered_raw_commands": (
		"redtra_customisation.override.printview.get_rendered_raw_commands"
	),
	# ERPNext v17 moved PR -> PI mapper out of purchase_receipt.py.
	"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice": (
		"erpnext.stock.doctype.purchase_receipt.mapper.make_purchase_invoice"
	),
	# open_mapped_doc sends selected_children as {} when no child rows are checked.
	"frappe.model.mapper.make_mapped_doc": (
		"redtra_customisation.override.mapper.make_mapped_doc"
	),
	"frappe.model.mapper.map_docs": "redtra_customisation.override.mapper.map_docs",
}

# Whitelisted methods
# -------------------
# Methods that can be called from client-side

# User import method is available via redtra_customisation.pdc.user_import.import_users_from_file
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "redtra_customisation.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
before_request = [
	"redtra_customisation.rpayroll.install.patch_employee_checkin_for_overtime_once",
	"redtra_customisation.override.general_ledger_report.apply_general_ledger_report_patch",
]
# after_request = ["redtra_customisation.utils.after_request"]

# Job Events
# ----------
# before_job = ["redtra_customisation.utils.before_job"]
# after_job = ["redtra_customisation.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"redtra_customisation.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
