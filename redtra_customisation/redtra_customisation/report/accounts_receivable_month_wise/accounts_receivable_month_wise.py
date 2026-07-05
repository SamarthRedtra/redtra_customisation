# Copyright (c) 2026, redtra_customisation contributors

from redtra_customisation.redtra_customisation.report.month_wise_receivable_payable import (
	MonthWiseReceivablePayableReport,
)


def execute(filters=None):
	args = {
		"account_type": "Receivable",
		"naming_by": ["Selling Settings", "cust_master_name"],
	}
	return MonthWiseReceivablePayableReport(filters).run(args)
