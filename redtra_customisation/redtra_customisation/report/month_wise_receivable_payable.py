# Copyright (c) 2026, redtra_customisation contributors

from frappe import _
from frappe.utils import add_months, flt, formatdate, getdate

from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport


class MonthWiseReceivablePayableReport(ReceivablePayableReport):
	"""Adds calendar month ageing columns alongside standard day-range buckets."""

	def set_defaults(self):
		super().set_defaults()
		self._build_month_column_meta()

	def _build_month_column_meta(self):
		report_date = getdate(self.filters.report_date)
		end_month = report_date.replace(day=1)
		self.month_columns = []

		for offset in range(11, -1, -1):
			month_start = add_months(end_month, -offset)
			self.month_columns.append(
				{
					"fieldname": f"month_{month_start.year}_{month_start.month:02d}",
					"label": formatdate(month_start, "MMM yyyy"),
					"month_start": month_start,
				}
			)

		self.month_column_fieldnames = [col["fieldname"] for col in self.month_columns] + ["month_older"]
		self.month_ageing_column_labels = [col["label"] for col in self.month_columns] + [_("Older")]

	def get_currency_fields(self):
		fields = super().get_currency_fields()
		fields.append("range0")
		if getattr(self, "month_column_fieldnames", None):
			fields.extend(self.month_column_fieldnames)
		return fields

	def setup_ageing_columns(self):
		super().setup_ageing_columns()
		self.setup_month_wise_columns()

	def setup_month_wise_columns(self):
		for col in self.month_columns:
			self.add_column(label=col["label"], fieldname=col["fieldname"], fieldtype="Currency")

		self.add_column(label=_("Older"), fieldname="month_older", fieldtype="Currency")

	def set_ageing(self, row):
		super().set_ageing(row)
		self.set_month_wise_ageing(row)

	def _get_ageing_entry_date(self, row):
		if self.filters.ageing_based_on == "Due Date":
			return row.due_date or row.posting_date
		if self.filters.ageing_based_on == "Supplier Invoice Date":
			return row.bill_date
		return row.posting_date

	def set_month_wise_ageing(self, row):
		for fieldname in self.month_column_fieldnames:
			row[fieldname] = 0.0

		entry_date = self._get_ageing_entry_date(row)
		outstanding = flt(row.outstanding)
		if not entry_date or not outstanding:
			return

		if getdate(entry_date) > getdate(self.age_as_on):
			return

		entry_month = getdate(entry_date).replace(day=1)
		for col in self.month_columns:
			if entry_month == col["month_start"]:
				row[col["fieldname"]] = outstanding
				return

		row["month_older"] = outstanding
