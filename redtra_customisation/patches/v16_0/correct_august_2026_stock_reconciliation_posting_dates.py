from redtra_customisation.patches.v16_0.move_august_2026_stock_reconciliations_to_july import (
	correct_posting_dates,
)


def execute():
	correct_posting_dates()
