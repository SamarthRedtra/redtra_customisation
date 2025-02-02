import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.desk.query_report import run

def get_default_filters():
    today = frappe.utils.today()
    fiscal_year_start = get_fiscal_year(today, as_dict=True)["year_start_date"]

    filters = {
        "from_date": fiscal_year_start,
        "to_date": today
    }
    return filters

def execute_report():
    report_name = "Itemwise Recommended Reorder Level"
    filters = get_default_filters()
    filters['item_group'] = 'All Item Groups'

    result = run(report_name, filters)
    res = {i['item']:i for i in result['result'] } if len(result['result']) > 0 else []
    return res
    