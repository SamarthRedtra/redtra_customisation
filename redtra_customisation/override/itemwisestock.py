import frappe

def execute_report():
    report_name = "Your Report Name"
    filters = {
        "from_date": "2024-01-01",
        "to_date": "2024-01-31"
    }

    result = frappe.desk.query_report.run(report_name, filters)
    return result