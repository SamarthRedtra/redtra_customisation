app_name = "redtra_customisation"
app_title = "Redtra Customisation"
app_publisher = "samarth.upare@redtra.com"
app_description = "Redtra Customisation "
app_email = "samarth.upare@redtra.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

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
# app_include_js = "/assets/redtra_customisation/js/redtra_customisation.js"

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
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
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
# jinja = {
# 	"methods": "redtra_customisation.utils.jinja_methods",
# 	"filters": "redtra_customisation.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "redtra_customisation.install.before_install"
# after_install = "redtra_customisation.install.after_install"

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
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Purchase Order": "redtra_customisation.override.purchase_order.CustomPurchaseOrder"
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"redtra_customisation.tasks.all"
# 	],
# 	"daily": [
# 		"redtra_customisation.tasks.daily"
# 	],
# 	"hourly": [
# 		"redtra_customisation.tasks.hourly"
# 	],
# 	"weekly": [
# 		"redtra_customisation.tasks.weekly"
# 	],
# 	"monthly": [
# 		"redtra_customisation.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "redtra_customisation.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "redtra_customisation.event.get_events"
# }
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
# before_request = ["redtra_customisation.utils.before_request"]
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

