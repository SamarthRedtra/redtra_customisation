# Copyright (c) 2026, redtra_customisation contributors

from redtra_customisation.redtra_customisation.report.month_wise_receivable_payable import (
	MonthWiseReceivablePayableReport,
)


def execute(filters=None):
	args = {
		"account_type": "Payable",
		"naming_by": ["Buying Settings", "supp_master_name"],
	}
	return MonthWiseReceivablePayableReport(filters).run(args)
