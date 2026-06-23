# Copyright (c) 2026, redtra_customisation contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PostDatedCheques(Document):
	def validate(self):
		self.set_invoice_links()
		self.validate_pdc_amount_vs_allocations()
		self.validate_invoice_references_not_reused()

	def validate_pdc_amount_vs_allocations(self):
		"""Cheque amount must cover invoice allocations; warn when rows exceed cheque."""
		total_allocated = sum(flt(row.allocated_amount) for row in self.get("invoice_references") or [])
		if not total_allocated:
			return
		if flt(self.amount) <= 0:
			frappe.throw(_("PDC Amount must be greater than zero when invoices are linked."))
		if total_allocated > flt(self.amount) + 0.01:
			frappe.msgprint(
				_(
					"Total allocated on invoices ({0}) exceeds cheque amount ({1}). "
					"Only the cheque amount is reserved until conversion; adjust allocated amounts."
				).format(total_allocated, self.amount),
				indicator="orange",
				title=_("Allocation Exceeds Cheque Amount"),
			)

	def before_cancel(self):
		"""Cancel submitted Payment Entries linked to this PDC."""
		self._clear_payment_entry_link()
		for payment_entry_name in self._get_linked_payment_entries():
			if not frappe.db.exists("Payment Entry", payment_entry_name):
				continue
			pe = frappe.get_doc("Payment Entry", payment_entry_name)
			if pe.docstatus != 1:
				continue
			# PDC still points to this PE until cancel completes; skip that back-link check.
			pe.flags.ignore_links = True
			pe.cancel()

	def on_cancel(self):
		self._clear_payment_entry_link()
		self.status = "Cancelled"
		self.db_update()

	def before_insert(self):
		self.status = "Pending"

	def set_invoice_links(self):
		"""Store linked invoice IDs on the parent so they are visible/searchable in list view."""
		references = []
		seen = set()
		for row in self.get("invoice_references") or []:
			if not row.reference_doctype or not row.reference_name:
				continue
			key = (row.reference_doctype, row.reference_name)
			if key in seen:
				continue
			seen.add(key)
			references.append(row.reference_name)
		self.invoice_links = ", ".join(references)
		summary = references[:3]
		if len(references) > 3:
			summary.append(_("+{0} more").format(len(references) - 3))
		self.invoice_links_list = ", ".join(summary)

	def validate_invoice_references_not_reused(self):
		"""Ensure total PDC allocation per invoice does not exceed invoice outstanding."""
		allocated_in_doc = {}
		for row in self.get("invoice_references") or []:
			if not row.reference_doctype or not row.reference_name:
				continue

			key = (row.reference_doctype, row.reference_name)
			allocated_in_doc[key] = allocated_in_doc.get(key, 0) + flt(row.allocated_amount)

			remaining = get_remaining_pdc_allocatable(
				row.reference_doctype,
				row.reference_name,
				exclude_pdc=self.name if not self.is_new() else None,
			)
			if flt(row.allocated_amount) > remaining + 0.01:
				existing_pdc = get_existing_pdc_for_invoice(
					row.reference_doctype,
					row.reference_name,
					exclude_pdc=self.name if not self.is_new() else None,
				)
				if existing_pdc and remaining <= 0:
					frappe.throw(
						_("{0} {1} is already fully allocated on active PDC {2}.").format(
							_(row.reference_doctype),
							frappe.bold(row.reference_name),
							frappe.bold(existing_pdc),
						),
						title=_("Invoice Already Used in PDC"),
					)
				frappe.throw(
					_(
						"Allocated amount {0} for {1} {2} exceeds remaining PDC allocatable amount {3}."
					).format(
						frappe.bold(flt(row.allocated_amount)),
						_(row.reference_doctype),
						frappe.bold(row.reference_name),
						frappe.bold(remaining),
					),
					title=_("PDC Allocation Exceeds Outstanding"),
				)

		for (reference_doctype, reference_name), total_allocated in allocated_in_doc.items():
			outstanding = flt(
				frappe.db.get_value(reference_doctype, reference_name, "outstanding_amount")
			)
			if total_allocated > outstanding + 0.01:
				frappe.throw(
					_(
						"Total allocated amount {0} for {1} {2} cannot exceed invoice outstanding {3}."
					).format(
						frappe.bold(total_allocated),
						_(reference_doctype),
						frappe.bold(reference_name),
						frappe.bold(outstanding),
					),
					title=_("PDC Allocation Exceeds Outstanding"),
				)

	def _clear_payment_entry_link(self):
		if not self.payment_entry:
			return
		frappe.db.set_value(
			"Post Dated Cheques",
			self.name,
			"payment_entry",
			None,
			update_modified=False,
		)
		self.payment_entry = None

	def _get_linked_payment_entries(self):
		linked = set()

		if self.payment_entry:
			linked.add(self.payment_entry)

		# Fallback: include any PDC-generated entries matching this cheque details.
		rows = frappe.get_all(
			"Payment Entry",
			filters={
				"docstatus": ["in", [0, 1]],
				"custom_is_pdc_entry": 1,
				"company": self.company,
				"party_type": self.party_type,
				"party": self.party,
				"reference_no": self.reference_no,
			},
			pluck="name",
		)
		linked.update(rows or [])
		return list(linked)


def get_existing_pdc_for_invoice(reference_doctype, reference_name, exclude_pdc=None):
	filters = {
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
	}
	if exclude_pdc:
		filters["parent"] = ["!=", exclude_pdc]

	rows = frappe.get_all(
		"PDC Invoice Reference",
		filters=filters,
		fields=["parent"],
		order_by="modified desc",
	)
	if not rows:
		return None

	parents = [row.parent for row in rows]
	active = frappe.get_all(
		"Post Dated Cheques",
		filters={
			"name": ["in", parents],
			"docstatus": 1,
			"status": ["!=", "Cancelled"],
		},
		pluck="name",
		limit=1,
	)
	return active[0] if active else None


def _effective_pdc_line_allocation(allocated_amount, parent_pdc_amount, parent_total_allocated):
	"""Reserve only what the cheque actually covers when row amounts exceed PDC amount."""
	allocated_amount = flt(allocated_amount)
	parent_pdc_amount = flt(parent_pdc_amount)
	parent_total_allocated = flt(parent_total_allocated)
	if parent_total_allocated <= 0:
		return 0.0
	if parent_total_allocated > parent_pdc_amount and parent_pdc_amount > 0:
		return allocated_amount * (parent_pdc_amount / parent_total_allocated)
	return allocated_amount


def get_active_pdc_allocated_amount(reference_doctype, reference_name, exclude_pdc=None):
	"""Effective amount reserved on active PDCs (capped by each PDC cheque amount)."""
	filters = {
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
	}
	if exclude_pdc:
		filters["parent"] = ["!=", exclude_pdc]

	rows = frappe.get_all(
		"PDC Invoice Reference",
		filters=filters,
		fields=["parent", "allocated_amount"],
	)
	if not rows:
		return 0.0

	parent_names = list({row.parent for row in rows})
	active_parents = set(
		frappe.get_all(
			"Post Dated Cheques",
			filters={
				"name": ["in", parent_names],
				"docstatus": 1,
				"status": ["!=", "Cancelled"],
			},
			pluck="name",
		)
		or []
	)
	if not active_parents:
		return 0.0

	parent_totals = {}
	for parent in active_parents:
		all_refs = frappe.get_all(
			"PDC Invoice Reference",
			filters={"parent": parent},
			fields=["allocated_amount"],
		)
		parent_totals[parent] = sum(flt(r.allocated_amount) for r in all_refs)

	pdc_amounts = {
		row.name: flt(row.amount)
		for row in frappe.get_all(
			"Post Dated Cheques",
			filters={"name": ["in", list(active_parents)]},
			fields=["name", "amount"],
		)
	}

	total_effective = 0.0
	for row in rows:
		if row.parent not in active_parents:
			continue
		total_effective += _effective_pdc_line_allocation(
			row.allocated_amount,
			pdc_amounts.get(row.parent, 0),
			parent_totals.get(row.parent, 0),
		)
	return total_effective


def get_remaining_pdc_allocatable(reference_doctype, reference_name, exclude_pdc=None):
	"""Outstanding invoice amount not yet reserved on other active PDCs."""
	outstanding = flt(
		frappe.db.get_value(reference_doctype, reference_name, "outstanding_amount")
	)
	already_allocated = get_active_pdc_allocated_amount(
		reference_doctype, reference_name, exclude_pdc=exclude_pdc
	)
	return max(0.0, outstanding - already_allocated)


def _active_pdc_allocation_subquery():
	"""SQL fragment: effective reserved amount on other active PDCs (prorated by cheque amount)."""
	return """
		COALESCE((
			SELECT SUM(
				CASE
					WHEN pdc_totals.total_alloc > IFNULL(pdc.amount, 0)
						AND pdc_totals.total_alloc > 0
						AND IFNULL(pdc.amount, 0) > 0
					THEN ref.allocated_amount * pdc.amount / pdc_totals.total_alloc
					ELSE ref.allocated_amount
				END
			)
			FROM `tabPDC Invoice Reference` ref
			INNER JOIN `tabPost Dated Cheques` pdc ON pdc.name = ref.parent
			INNER JOIN (
				SELECT parent, SUM(allocated_amount) AS total_alloc
				FROM `tabPDC Invoice Reference`
				GROUP BY parent
			) pdc_totals ON pdc_totals.parent = ref.parent
			WHERE ref.reference_doctype = %(reference_doctype)s
				AND ref.reference_name = inv.name
				AND pdc.docstatus = 1
				AND IFNULL(pdc.status, '') != 'Cancelled'
				AND (%(current_pdc)s = '' OR pdc.name != %(current_pdc)s)
		), 0)
	"""
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_purchase_invoice_for_pdc(doctype, txt, searchfield, start, page_len, filters):
	"""Search Purchase Invoice with Supplier Invoice No for PDC fetch dialog."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if not filters:
		filters = {}

	company = filters.get("company")
	supplier = filters.get("supplier")

	if not company or not supplier:
		return []

	page_len = int(page_len) if page_len else 20
	start = int(start) if start else 0
	search_txt = (txt or "").strip()

	query = """
		SELECT
			name,
			COALESCE(custom_supplier_invoice_no, '') AS custom_supplier_invoice_no,
			grand_total,
			outstanding_amount
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1
			AND company = %(company)s
			AND supplier = %(supplier)s
			AND outstanding_amount > 0
	"""
	values = {"company": company, "supplier": supplier}

	if search_txt:
		query += """
			AND (
				name LIKE %(txt)s
				OR custom_supplier_invoice_no LIKE %(txt)s
			)
		"""
		values["txt"] = f"%{search_txt}%"

	query += """
		ORDER BY posting_date DESC, name DESC
		LIMIT %(start)s, %(page_len)s
	"""
	values["start"] = start
	values["page_len"] = page_len

	return frappe.db.sql(query, values, as_dict=False)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_invoice_for_pdc(doctype, txt, searchfield, start, page_len, filters):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if not filters:
		filters = {}

	reference_doctype = filters.get("reference_doctype") or doctype
	company = filters.get("company")
	party = filters.get("party")
	current_pdc = filters.get("current_pdc")

	if reference_doctype not in ("Sales Invoice", "Purchase Invoice"):
		return []
	if not company or not party:
		return []

	party_field = "customer" if reference_doctype == "Sales Invoice" else "supplier"
	supplier_invoice_expr = "COALESCE(inv.custom_supplier_invoice_no, '')"
	customer_invoice_expr = "COALESCE(inv.bill_no, '')"
	search_txt = (txt or "").strip()
	start = int(start or 0)
	page_len = int(page_len or 20)

	values = {
		"company": company,
		"party": party,
		"current_pdc": current_pdc or "",
		"start": start,
		"page_len": page_len,
	}

	allocation_subquery = _active_pdc_allocation_subquery()

	query = f"""
		SELECT
			inv.name,
			{supplier_invoice_expr if reference_doctype == "Purchase Invoice" else "''"} AS custom_supplier_invoice_no,
			{customer_invoice_expr if reference_doctype == "Sales Invoice" else "''"} AS custom_customer_invoice_no,
			inv.grand_total,
			inv.outstanding_amount,
			(inv.outstanding_amount - {allocation_subquery}) AS remaining_allocatable
		FROM `tab{reference_doctype}` inv
		WHERE inv.docstatus = 1
			AND inv.company = %(company)s
			AND inv.{party_field} = %(party)s
			AND inv.outstanding_amount > 0
			AND (inv.outstanding_amount - {allocation_subquery}) > 0.009
	"""
	values["reference_doctype"] = reference_doctype

	if search_txt:
		if reference_doctype == "Purchase Invoice":
			query += """
				AND (
					inv.name LIKE %(txt)s
					OR inv.custom_supplier_invoice_no LIKE %(txt)s
				)
			"""
		else:
			query += """
				AND (
					inv.name LIKE %(txt)s
					OR inv.bill_no LIKE %(txt)s
				)
			"""
		values["txt"] = f"%{search_txt}%"

	query += """
		ORDER BY inv.posting_date DESC, inv.name DESC
		LIMIT %(start)s, %(page_len)s
	"""

	return frappe.db.sql(query, values, as_dict=False)


@frappe.whitelist()
def get_pdc_invoice_details(reference_doctype, invoices, current_pdc=None):
	if isinstance(invoices, str):
		invoices = frappe.parse_json(invoices)
	invoices = list(dict.fromkeys(invoices or []))

	if reference_doctype not in ("Sales Invoice", "Purchase Invoice") or not invoices:
		return []

	fields = ["name", "grand_total", "outstanding_amount"]
	if reference_doctype == "Purchase Invoice":
		fields.append("custom_supplier_invoice_no")
	elif reference_doctype == "Sales Invoice":
		fields.append("bill_no")

	rows = frappe.get_all(
		reference_doctype,
		filters={
			"name": ["in", invoices],
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=fields,
		order_by="posting_date desc, name desc",
	)

	result = []
	for row in rows:
		remaining = get_remaining_pdc_allocatable(
			reference_doctype,
			row.name,
			exclude_pdc=current_pdc,
		)
		if remaining <= 0:
			frappe.throw(
				_("{0} {1} has no remaining amount available for PDC allocation.").format(
					_(reference_doctype),
					frappe.bold(row.name),
				),
				title=_("Invoice Fully Allocated on PDC"),
			)
		row["remaining_allocatable"] = remaining
		if reference_doctype == "Sales Invoice":
			row["custom_customer_invoice_no"] = row.get("bill_no") or ""
		result.append(row)

	return result


@frappe.whitelist()
def get_pending_invoices(company, party_type, party, current_pdc=None):
	if party_type not in ("Customer", "Supplier"):
		return []
	reference_doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
	party_field = "customer" if party_type == "Customer" else "supplier"

	# Only lock based on SUBMITTED post dated cheques
	allocation_subquery = """
		COALESCE((
			SELECT SUM(
				CASE
					WHEN pdc_totals.total_alloc > IFNULL(pdc.amount, 0)
						AND pdc_totals.total_alloc > 0
						AND IFNULL(pdc.amount, 0) > 0
					THEN ref.allocated_amount * pdc.amount / pdc_totals.total_alloc
					ELSE ref.allocated_amount
				END
			)
			FROM `tabPDC Invoice Reference` ref
			INNER JOIN `tabPost Dated Cheques` pdc ON pdc.name = ref.parent
			INNER JOIN (
				SELECT parent, SUM(allocated_amount) AS total_alloc
				FROM `tabPDC Invoice Reference`
				GROUP BY parent
			) pdc_totals ON pdc_totals.parent = ref.parent
			WHERE ref.reference_doctype = %(reference_doctype)s
				AND ref.reference_name = inv.name
				AND pdc.docstatus = 1
				AND IFNULL(pdc.status, '') != 'Cancelled'
				AND (%(current_pdc)s = '' OR pdc.name != %(current_pdc)s)
		), 0)
	"""

	supplier_invoice_expr = "COALESCE(inv.custom_supplier_invoice_no, '')"
	customer_invoice_expr = "COALESCE(inv.bill_no, '')"

	query = f"""
		SELECT
			inv.name,
			{supplier_invoice_expr if reference_doctype == "Purchase Invoice" else "''"} AS custom_supplier_invoice_no,
			{customer_invoice_expr if reference_doctype == "Sales Invoice" else "''"} AS custom_customer_invoice_no,
			inv.grand_total,
			inv.outstanding_amount,
			(inv.outstanding_amount - {allocation_subquery}) AS remaining_allocatable
		FROM `tab{reference_doctype}` inv
		WHERE inv.docstatus = 1
			AND inv.company = %(company)s
			AND inv.{party_field} = %(party)s
			AND inv.outstanding_amount > 0
		ORDER BY inv.posting_date DESC, inv.name DESC
	"""

	values = {
		"company": company,
		"party": party,
		"reference_doctype": reference_doctype,
		"current_pdc": current_pdc or ""
	}

	rows = frappe.db.sql(query, values, as_dict=True)

	return [r for r in rows if r.remaining_allocatable > 0.009]


@frappe.whitelist()
def get_invoice_pdc_connections(reference_doctype, reference_name):
	"""Return active Post Dated Cheques linked to a Sales/Purchase Invoice."""
	if reference_doctype not in ("Sales Invoice", "Purchase Invoice"):
		frappe.throw(_("Invalid invoice doctype"))

	if not reference_name or not frappe.db.exists(reference_doctype, reference_name):
		return []

	rows = frappe.db.sql(
		"""
		SELECT
			pdc.name,
			pdc.status,
			pdc.reference_no,
			pdc.reference_date,
			pdc.amount,
			pdc.payment_entry,
			ref.allocated_amount,
			pe.pdc_cheque_status AS payment_entry_status
		FROM `tabPDC Invoice Reference` ref
		INNER JOIN `tabPost Dated Cheques` pdc ON pdc.name = ref.parent
		LEFT JOIN `tabPayment Entry` pe
			ON pe.name = pdc.payment_entry AND pe.docstatus = 1
		WHERE ref.reference_doctype = %(reference_doctype)s
			AND ref.reference_name = %(reference_name)s
			AND ref.parenttype = 'Post Dated Cheques'
			AND ref.parentfield = 'invoice_references'
			AND pdc.docstatus = 1
			AND IFNULL(pdc.status, '') != 'Cancelled'
		ORDER BY pdc.reference_date DESC, pdc.name DESC
		""",
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		},
		as_dict=True,
	)

	for row in rows:
		row["display_status"] = _get_pdc_display_status(row.status, row.payment_entry_status)

	return rows


def _get_pdc_display_status(pdc_status, payment_entry_status=None):
	status = (pdc_status or "").strip()
	pe_status = (payment_entry_status or "").strip()

	if status == "Converted":
		if pe_status:
			return _("Converted / {0}").format(pe_status)
		return _("Converted")

	if status:
		return _(status)

	return _("Pending")

