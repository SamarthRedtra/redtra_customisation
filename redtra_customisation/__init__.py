__version__ = "0.0.1"


def _patch_general_ledger_report():
	from redtra_customisation.override.general_ledger_report import apply_general_ledger_report_patch

	apply_general_ledger_report_patch()


_patch_general_ledger_report()
