__version__ = "0.0.1"


def _patch_general_ledger_report():
	from redtra_customisation.override.general_ledger_report import apply_general_ledger_report_patch

	apply_general_ledger_report_patch()


_patch_general_ledger_report()


def _patch_stock_ledger_entry_links():
	try:
		from erpnext.stock import stock_ledger

		# Avoid double patching
		if getattr(stock_ledger.make_entry, "_redtra_compat_patched", False):
			return

		def _patched_make_entry(args, allow_negative_stock=False, via_landed_cost_voucher=False):
			import frappe
			args["doctype"] = "Stock Ledger Entry"
			sle = frappe.get_doc(args)
			sle.flags.ignore_permissions = 1
			sle.flags.skip_docstatus_validation = True
			sle.flags.ignore_links = True  # Bypasses CancelledLinkError for cancelled vouchers
			sle.allow_negative_stock = allow_negative_stock
			sle.via_landed_cost_voucher = via_landed_cost_voucher
			sle.submit()

			if args.get("creation_time") and args.get("voucher_type") == "Stock Reconciliation":
				sle.db_set("creation", args.get("creation_time"))

			return sle

		_patched_make_entry._redtra_compat_patched = True
		_patched_make_entry._cm_patched = True  # Prevent construction_management from overriding this
		stock_ledger.make_entry = _patched_make_entry
	except ImportError:
		pass


_patch_stock_ledger_entry_links()

