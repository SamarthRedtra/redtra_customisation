import frappe
from frappe.utils import flt
from redtra_customisation.commission import (
	apply_sales_partner_commission_from_team,
	_set_sales_partner_commission_fields,
	get_project_commission_rate,
	get_sales_invoice_commission_base_amount,
)
from redtra_customisation.paid_invoice_commission import should_defer_commission_to_payment

# Module-level caches (per-request, cleared on bench restart)
_NON_STOCK_ITEMS_CACHE = None
_CURRENCY_PRECISION = None


def calculate_profit_and_commission(doc, method):
	"""
	Calculate Profit Percentage and Commission for Sales Person on Sales Invoice Validate.
	Uses ERPNext Gross Profit report logic for consistency with the report.
	"""
	calculate_profit_percentage(doc)
	# Skip automatic commission override on submitted invoices so that
	# manually edited commission_rate / incentives values are preserved
	# when updating after submit.
	if doc.docstatus == 1:
		return
	# Project-wise commission is recorded when the invoice is fully paid.
	if should_defer_commission_to_payment(doc):
		return
	calculate_commission(doc)


def calculate_profit_percentage(doc):
	"""
	Calculates Profit Percentage using ERPNext Gross Profit report logic.
	Ensures consistency between Sales Invoice profit and Gross Profit report.
	"""
	total_base_amount = flt(doc.base_net_total)
	total_buying_amount = 0.0

	try:
		gross_profit_data = _get_gross_profit_for_invoice(doc)
		if gross_profit_data:
			total_base_amount, total_buying_amount = gross_profit_data
	except Exception as e:
		frappe.log_error(f"Profit calculation failed: {e}", "Redtra Customisation")
		pass # Proceed with defaults (0)



	if total_base_amount > 0:
		profit_amount = total_base_amount - total_buying_amount
		doc.custom_profit_percentage = flt(
			(profit_amount / total_base_amount) * 100.0,
			_get_currency_precision(),
		)
		if total_buying_amount > 0:
			doc.custom_profit_markup_percentage_ = flt(
				(profit_amount / total_buying_amount) * 100.0,
				_get_currency_precision(),
			)
		else:
			doc.custom_profit_markup_percentage_ = 100.0
	else:
		doc.custom_profit_percentage = 0.0
		doc.custom_profit_markup_percentage_ = 0.0


def _get_currency_precision():
	global _CURRENCY_PRECISION
	if _CURRENCY_PRECISION is None:
		_CURRENCY_PRECISION = frappe.db.get_default("currency_precision") or 3
	return _CURRENCY_PRECISION


def _get_gross_profit_for_invoice(doc):
	"""
	Fetch gross profit data using same logic as ERPNext Gross Profit report.
	Always uses current doc (form) data so profit reflects unsaved changes.
	Returns (total_base_amount, total_buying_amount) or None.
	"""
	filters = {
		"company": doc.company,
		"from_date": doc.posting_date,
		"to_date": doc.posting_date,
		"group_by": "Invoice",
		"include_returned_invoices": False,
	}
	generator = _DocGrossProfitGenerator(doc, filters)

	total_base_amount = 0.0
	total_buying_amount = 0.0
	precision = generator.currency_precision

	for row in generator.si_list:
		if getattr(row, "indent", 0) == 1:
			total_base_amount += flt(row.base_amount, precision)
			total_buying_amount += flt(row.buying_amount, precision)

	if total_base_amount == 0 and total_buying_amount == 0:
		return None

	return (total_base_amount, total_buying_amount)


class _DocGrossProfitGenerator:
	"""
	GrossProfitGenerator adapter that builds si_list from doc for new/unsaved invoices.
	Uses same buying amount logic as the report for consistency.
	"""

	def __init__(self, doc, filters):
		from erpnext.accounts.report.gross_profit.gross_profit import GrossProfitGenerator

		self.doc = doc
		self.filters = frappe._dict(filters)
		self.sle = {}
		self.average_buying_rate = {}
		self.currency_precision = frappe.db.get_default("currency_precision") or 3
		self.float_precision = frappe.db.get_default("float_precision") or 2

		self._build_si_list_from_doc()
		self._load_delivery_notes()
		self._load_product_bundle()
		self._load_non_stock_items()
		self.returned_invoices = frappe._dict()
		self._process()

	def _build_si_list_from_doc(self):
		parent = self.doc.name or "_new_"
		self.si_list = []

		for idx, item in enumerate(self.doc.items):
			row = frappe._dict(
				{
					"parenttype": "Sales Invoice",
					"parent": parent,
					"invoice": parent,
					"posting_date": self.doc.posting_date,
					"posting_time": getattr(self.doc, "posting_time", None),
					"project": self.doc.project,
					"update_stock": self.doc.update_stock,
					"customer": self.doc.customer,
					"customer_group": self.doc.customer_group,
					"customer_name": self.doc.customer_name,
					"territory": getattr(self.doc, "territory", None),
					"item_code": item.item_code,
					"invoice_base_net_total": self.doc.base_net_total,
					"item_name": item.item_name,
					"description": item.description,
					"warehouse": item.warehouse,
					"item_group": item.item_group,
					"brand": item.brand,
					"so_detail": item.so_detail,
					"sales_order": item.sales_order,
					"dn_detail": item.dn_detail,
					"delivery_note": item.delivery_note,
					"qty": item.stock_qty,
					"base_net_rate": item.base_net_rate,
					"base_net_amount": item.base_net_amount,
					"item_row": item.name or f"_item_{idx}",
					"is_return": self.doc.is_return,
					"cost_center": item.cost_center,
					"serial_and_batch_bundle": item.serial_and_batch_bundle,
				}
			)
			self.si_list.append(row)

	def _load_delivery_notes(self):
		from frappe.query_builder import Order
		from frappe import qb

		self.delivery_notes = frappe._dict()
		if not self.si_list:
			return

		invoices = list({r.parent for r in self.si_list if r.parent and r.parent != "_new_"})
		if not invoices:
			return

		dni = qb.DocType("Delivery Note Item")
		delivery_notes = (
			qb.from_(dni)
			.select(
				dni.against_sales_invoice.as_("sales_invoice"),
				dni.item_code,
				dni.warehouse,
				dni.parent.as_("delivery_note"),
				dni.name.as_("item_row"),
			)
			.where((dni.docstatus == 1) & (dni.against_sales_invoice.isin(invoices)))
			.groupby(dni.against_sales_invoice, dni.item_code)
			.orderby(dni.creation, order=Order.desc)
			.run(as_dict=True)
		)
		for entry in delivery_notes:
			self.delivery_notes[(entry.sales_invoice, entry.item_code)] = entry

	def _load_product_bundle(self):
		from frappe import qb

		self.product_bundles = {}
		parent = self.doc.name or "_new_"

		# Build from doc.packed_items for new/unsaved invoices
		if parent == "_new_" or not frappe.db.exists("Sales Invoice", parent):
			for pi in self.doc.get("packed_items") or []:
				packed = frappe._dict(
					{
						"parent_detail_docname": pi.parent_detail_docname,
						"item_code": pi.item_code,
						"warehouse": pi.warehouse,
						"total_qty": -1 * flt(pi.qty),
						"base_amount": flt(pi.rate) * flt(pi.qty),
						"serial_and_batch_bundle": pi.serial_and_batch_bundle,
					}
				)
				self.product_bundles.setdefault("Sales Invoice", frappe._dict()).setdefault(
					parent, frappe._dict()
				).setdefault(pi.parent_item, []).append(packed)
			return

		# Load only packed items for this invoice + linked delivery notes
		dn_list = list({r.delivery_note for r in self.si_list if r.delivery_note})
		parents = [parent] + dn_list

		pki = qb.DocType("Packed Item")
		pki_query = (
			frappe.qb.from_(pki)
			.select(
				pki.parenttype,
				pki.parent,
				pki.parent_item,
				pki.item_code,
				pki.warehouse,
				(-1 * pki.qty).as_("total_qty"),
				pki.rate,
				(pki.rate * pki.qty).as_("base_amount"),
				pki.parent_detail_docname,
				pki.serial_and_batch_bundle,
			)
			.where((pki.docstatus == 1) & (pki.parent.isin(parents)))
		)
		for d in pki_query.run(as_dict=True):
			self.product_bundles.setdefault(d.parenttype, frappe._dict()).setdefault(
				d.parent, frappe._dict()
			).setdefault(d.parent_item, []).append(d)

	def _load_non_stock_items(self):
		global _NON_STOCK_ITEMS_CACHE
		if _NON_STOCK_ITEMS_CACHE is None:
			_NON_STOCK_ITEMS_CACHE = set(
				frappe.db.sql_list("select name from tabItem where is_stock_item=0")
			)
		self.non_stock_items = _NON_STOCK_ITEMS_CACHE

	def _process(self):
		from erpnext.accounts.report.gross_profit.gross_profit import GrossProfitGenerator

		# Use GrossProfitGenerator's get_buying_amount logic
		generator = GrossProfitGenerator.__new__(GrossProfitGenerator)
		generator.sle = self.sle
		generator.average_buying_rate = self.average_buying_rate
		generator.filters = self.filters
		generator.currency_precision = self.currency_precision
		generator.float_precision = self.float_precision
		generator.delivery_notes = self.delivery_notes
		generator.product_bundles = self.product_bundles
		generator.non_stock_items = self.non_stock_items
		generator.returned_invoices = self.returned_invoices

		for row in self.si_list:
			row.base_amount = flt(row.base_net_amount, self.currency_precision)
			product_bundles = self.product_bundles.get("Sales Invoice", {}).get(
				row.parent, frappe._dict()
			)
			if not product_bundles and row.dn_detail:
				product_bundles = self.product_bundles.get("Delivery Note", {}).get(
					row.delivery_note, frappe._dict()
				)

			if row.item_code in product_bundles:
				row.buying_amount = flt(
					generator.get_buying_amount_from_product_bundle(
						row, product_bundles[row.item_code]
					),
					self.currency_precision,
				)
			else:
				row.buying_amount = flt(
					generator.get_buying_amount(row, row.item_code),
					self.currency_precision,
				)

			row.gross_profit = flt(
				row.base_amount - row.buying_amount, self.currency_precision
			)
			row.gross_profit_percent = (
				flt((row.gross_profit / row.base_amount) * 100.0, self.currency_precision)
				if row.base_amount
				else 0.0
			)

		# Add header rows for group_by Invoice structure (indent 0 = header, indent 1 = item)
		grouped = {}
		for row in self.si_list:
			grouped.setdefault(row.parent, []).append(row)
			row.indent = 1.0
			row.parent_invoice = row.parent
			row.invoice_or_item = row.item_code

		# Rebuild si_list with header rows
		new_list = []
		for parent, rows in grouped.items():
			header = frappe._dict(
				{
					"parent_invoice": "",
					"indent": 0.0,
					"invoice_or_item": parent,
					"parent": None,
					"base_amount": sum(flt(r.base_amount) for r in rows),
					"buying_amount": sum(flt(r.buying_amount) for r in rows),
				}
			)
			new_list.append(header)
			new_list.extend(rows)
		self.si_list = new_list


def _normalize_commission_doc(doc):
	as_dict_method = getattr(doc, "as_dict", None)
	if callable(as_dict_method):
		doc = as_dict_method()

	doc = frappe._dict(doc or {})
	doc.sales_team = [frappe._dict(row) for row in (doc.get("sales_team") or [])]
	return doc


def _build_commission_preview(doc, settings=None):
	doc = _normalize_commission_doc(doc)
	settings = settings or frappe.get_cached_doc("Redtra Custom Setting")

	use_markup_for_slabs = getattr(settings, "use_markup_percentage_for_commission", 0)
	profit_percentage = flt(doc.get("custom_profit_percentage"))
	markup_percentage = flt(doc.get("custom_profit_markup_percentage_"))
	comparison_percentage = markup_percentage if use_markup_for_slabs else profit_percentage

	is_sales_based = flt(doc.get("custom_enable_sales_based"))
	customer_commission = 0.0
	if is_sales_based and doc.get("customer"):
		customer_commission = flt(
			frappe.db.get_value("Customer", doc.get("customer"), "custom_comission")
		)

	project_commission_rate = None
	if not is_sales_based:
		project_commission_rate = get_project_commission_rate(
			doc.get("project"), settings=settings
		)
	# Commission is always calculated from the invoice business total before
	# retention and advance deductions; never from Sales Invoice Net Total.
	use_total_for_commission = True
	use_net_total_for_commission = False

	sales_person_cache = {}
	rows = []

	for row in doc.sales_team:
		manual_commission_rate = flt(row.get("commission_rate"))
		if manual_commission_rate > 0:
			commission_rate = manual_commission_rate
		elif is_sales_based:
			commission_rate = customer_commission
		elif project_commission_rate is not None:
			commission_rate = project_commission_rate
		else:
			commission_rate = 0.0
			if row.get("sales_person"):
				if row.sales_person not in sales_person_cache:
					sales_person_cache[row.sales_person] = frappe.get_cached_doc(
						"Sales Person", row.sales_person
					)
				sales_person_doc = sales_person_cache[row.sales_person]

				if sales_person_doc.custom_enable_slab and sales_person_doc.custom_slabs:
					for slab in sales_person_doc.custom_slabs:
						if flt(slab.get("from")) <= comparison_percentage <= flt(slab.get("to")):
							commission_rate = flt(slab.get("value"))
							break

		base_amount = get_sales_invoice_commission_base_amount(
			doc,
			row,
			force_net_total=use_net_total_for_commission,
			force_total=use_total_for_commission,
		)
		rows.append(
			{
				"name": row.get("name"),
				"sales_person": row.get("sales_person"),
				"commission_rate": commission_rate,
				"incentives": base_amount * (commission_rate / 100.0),
			}
		)

	header_commission_rate = flt(doc.get("commission_rate"))
	if project_commission_rate is not None:
		header_commission_rate = project_commission_rate
	elif is_sales_based:
		header_commission_rate = customer_commission

	amount_eligible_for_commission = get_sales_invoice_commission_base_amount(
		doc,
		force_net_total=use_net_total_for_commission,
		force_total=use_total_for_commission,
	)
	total_commission = amount_eligible_for_commission * (header_commission_rate / 100.0)

	preview = {
		"project_commission_rate": project_commission_rate,
		"commission_rate": header_commission_rate,
		"amount_eligible_for_commission": amount_eligible_for_commission,
		"total_commission": total_commission,
		"rows": rows,
	}
	return apply_sales_partner_commission_from_team(doc, preview, settings=settings)


def calculate_commission(doc):
	"""
	Calculate commission for Sales Persons based on slabs.
	"""
	preview = _build_commission_preview(doc)

	doc.amount_eligible_for_commission = preview.get("amount_eligible_for_commission")
	doc.commission_rate = preview.get("commission_rate")
	doc.total_commission = preview.get("total_commission")
	_set_sales_partner_commission_fields(doc, preview)

	row_by_name = {row.get("name"): row for row in preview.get("rows", []) if row.get("name")}
	for row in doc.get("sales_team") or []:
		updated_row = row_by_name.get(row.name)
		if not updated_row:
			continue
		row.commission_rate = updated_row.get("commission_rate")
		row.incentives = updated_row.get("incentives")


@frappe.whitelist()
def get_commission_preview(doc):
	doc = frappe.parse_json(doc) if isinstance(doc, str) else doc
	return _build_commission_preview(doc)
