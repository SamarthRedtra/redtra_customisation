import frappe
from frappe.utils import flt

from erpnext.stock.serial_batch_bundle import SerialBatchCreation


TARGET_POSTING_DATE = "2026-07-31"
OPENING_BATCH_PREFIX = "OPEN-20260731-MAT-RECO-2026-00026-1"
CANCELLED_DOCUMENT = "MAT-RECO-2026-00026"
CANCELLED_AMENDMENT = "MAT-RECO-2026-00026-1"
CANCELLED_AMENDMENT_POSTING_TIME = "18:23:07.450570"
SUBMITTED_DOCUMENTS = (
	"MAT-RECO-2026-00009",
	"MAT-RECO-2026-00010",
	"MAT-RECO-2026-00011",
	"MAT-RECO-2026-00012",
	"MAT-RECO-2026-00013",
	"MAT-RECO-2026-00014",
	"MAT-RECO-2026-00015",
	"MAT-RECO-2026-00016",
	"MAT-RECO-2026-00017",
	"MAT-RECO-2026-00018",
	"MAT-RECO-2026-00019",
	"MAT-RECO-2026-00020",
	"MAT-RECO-2026-00021",
	"MAT-RECO-2026-00022",
	"MAT-RECO-2026-00023",
	"MAT-RECO-2026-00024",
	"MAT-RECO-2026-00025",
	"MAT-RECO-2026-00027",
	"MAT-RECO-2026-00028",
	"MAT-RECO-2026-00029",
)


def execute():
	"""Move the August opening-stock reconciliations to 31 July 2026."""
	if not _target_documents_exist():
		return

	submitted_documents, cancelled_amendment = _validate_documents()
	source_batch_allocations = _capture_source_batch_allocations(submitted_documents)
	_create_missing_opening_batches(cancelled_amendment)

	for document in reversed(submitted_documents):
		document.cancel()

	cancelled_amendment.posting_date = TARGET_POSTING_DATE
	cancelled_amendment.set_posting_time = 1
	cancelled_amendment.save()
	cancelled_amendment.submit()

	for document in submitted_documents:
		_create_and_submit_amendment(document, source_batch_allocations[document.name])


def correct_posting_dates():
	"""Correct amendments created without Set Posting Time enabled."""
	if not _target_documents_exist():
		return

	documents = _get_incorrectly_dated_amendments()
	if not documents:
		return
	if len(documents) != len(SUBMITTED_DOCUMENTS) + 1:
		frappe.throw("Unexpected stock reconciliation amendments found for posting-date correction.")

	source_batch_allocations = _capture_source_batch_allocations(documents)
	posting_times = {document.name: _get_correction_posting_time(document) for document in documents}

	for document in sorted(documents, key=lambda row: row.posting_time, reverse=True):
		document.cancel()

	for document in sorted(documents, key=lambda row: posting_times[row.name]):
		_create_and_submit_amendment(
			document,
			source_batch_allocations[document.name],
			posting_time=posting_times[document.name],
		)


def _target_documents_exist():
	"""Return whether this site contains the complete Delta correction data set.

	The patch is included in both local and production app deployments, but the
	August 2026 opening-stock import exists only on Delta.  An incomplete target
	set must be left untouched instead of attempting to load a missing document.
	"""
	target_names = [*SUBMITTED_DOCUMENTS, CANCELLED_DOCUMENT, CANCELLED_AMENDMENT]
	existing_names = frappe.get_all(
		"Stock Reconciliation",
		filters={"name": ("in", target_names)},
		pluck="name",
	)
	return len(existing_names) == len(target_names)


def _create_and_submit_amendment(source, source_batch_allocations, posting_time=None):
	amendment = frappe.copy_doc(source)
	amendment.amended_from = source.name
	amendment.posting_date = TARGET_POSTING_DATE
	amendment.set_posting_time = 1
	if posting_time:
		amendment.posting_time = posting_time
	amendment.set_new_name()
	amendment.set_parent_in_children()
	_rebuild_batch_bundles(source, amendment, source_batch_allocations)
	amendment.insert(set_child_names=False)
	_link_batch_bundles(amendment)
	amendment.submit()


def _validate_documents():
	submitted_documents = [frappe.get_doc("Stock Reconciliation", name) for name in SUBMITTED_DOCUMENTS]
	for document in submitted_documents:
		if document.docstatus != 1:
			frappe.throw(f"{document.name} must be submitted before this patch is run.")
		if str(document.posting_date)[:10] != "2026-08-16":
			frappe.throw(f"{document.name} must have posting date 2026-08-16 before this patch is run.")

	cancelled_document = frappe.get_doc("Stock Reconciliation", CANCELLED_DOCUMENT)
	if cancelled_document.docstatus != 2:
		frappe.throw(f"{CANCELLED_DOCUMENT} must be cancelled before this patch is run.")

	cancelled_amendment = frappe.get_doc("Stock Reconciliation", CANCELLED_AMENDMENT)
	if cancelled_amendment.docstatus != 0 or cancelled_amendment.amended_from != CANCELLED_DOCUMENT:
		frappe.throw(f"{CANCELLED_AMENDMENT} must be the draft amendment of {CANCELLED_DOCUMENT}.")

	return submitted_documents, cancelled_amendment


def _get_incorrectly_dated_amendments():
	incorrect_names = frappe.get_all(
		"Stock Reconciliation",
		filters={
			"amended_from": ("in", [*SUBMITTED_DOCUMENTS, CANCELLED_DOCUMENT]),
			"docstatus": 1,
			"posting_date": ("!=", TARGET_POSTING_DATE),
		},
		pluck="name",
	)
	return [frappe.get_doc("Stock Reconciliation", name) for name in incorrect_names]


def _get_correction_posting_time(document):
	if document.amended_from == CANCELLED_DOCUMENT:
		return CANCELLED_AMENDMENT_POSTING_TIME

	return str(frappe.db.get_value("Stock Reconciliation", document.amended_from, "posting_time"))


def _create_missing_opening_batches(document):
	for row in document.items:
		item = frappe.get_cached_value("Item", row.item_code, ["has_batch_no", "has_serial_no"], as_dict=True)
		if row.serial_and_batch_bundle or row.batch_no or not (item.has_batch_no or item.has_serial_no):
			continue

		if item.has_serial_no:
			frappe.throw(f"Row {row.idx} ({row.item_code}) requires serial-number allocation before this patch can run.")

		batch_no = _get_or_create_opening_batch(document, row)
		_create_batch_bundle(document, row, {batch_no: row.qty})


def _get_or_create_opening_batch(document, row):
	batch_no = f"{OPENING_BATCH_PREFIX}-{row.idx:02d}"
	batch_item = frappe.db.get_value("Batch", batch_no, "item")
	if batch_item and batch_item != row.item_code:
		frappe.throw(f"Opening batch {batch_no} belongs to {batch_item}, not {row.item_code}.")

	if not batch_item:
		frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": batch_no,
				"item": row.item_code,
				"reference_doctype": document.doctype,
				"reference_name": document.name,
			}
		).insert()

	return batch_no


def _capture_source_batch_allocations(documents):
	allocations = {}
	for document in documents:
		allocations[document.name] = _capture_document_batch_allocations(document)

	return allocations


def _capture_document_batch_allocations(document):
	allocations = {}
	for row in document.items:
		item = frappe.get_cached_value(
			"Item", row.item_code, ["has_batch_no", "has_serial_no"], as_dict=True
		)
		if not (item.has_batch_no or item.has_serial_no):
			continue
		if item.has_serial_no:
			frappe.throw(f"{document.name}, row {row.idx} ({row.item_code}) requires serial-number allocation.")

		allocations[row.idx] = _get_batch_allocation_from_bundle(document, row)

	return allocations


def _rebuild_batch_bundles(source, amendment, source_batch_allocations):
	for source_row, amendment_row in zip(source.items, amendment.items, strict=True):
		item = frappe.get_cached_value(
			"Item", source_row.item_code, ["has_batch_no", "has_serial_no"], as_dict=True
		)
		if not (item.has_batch_no or item.has_serial_no):
			continue
		if item.has_serial_no:
			frappe.throw(f"{source.name}, row {source_row.idx} ({source_row.item_code}) requires serial-number allocation.")

		batch_allocation = source_batch_allocations[source_row.idx]
		_create_batch_bundle(amendment, amendment_row, batch_allocation)


def _link_batch_bundles(document):
	for row in document.items:
		if not row.serial_and_batch_bundle:
			continue

		bundle = frappe.get_doc("Serial and Batch Bundle", row.serial_and_batch_bundle)
		if bundle.voucher_no:
			continue

		bundle.voucher_no = document.name
		bundle.voucher_detail_no = row.name
		bundle.save()


def _get_batch_allocation_from_bundle(document, row):
	if not row.serial_and_batch_bundle:
		frappe.throw(f"{document.name}, row {row.idx} ({row.item_code}) has no batch bundle to rebuild.")

	entries = frappe.get_all(
		"Serial and Batch Entry",
		filters={"parent": row.serial_and_batch_bundle},
		fields=["batch_no", "qty"],
	)
	allocation = {}
	for entry in entries:
		if entry.batch_no:
			allocation[entry.batch_no] = allocation.get(entry.batch_no, 0) + abs(entry.qty)

	if not allocation:
		frappe.throw(f"{document.name}, row {row.idx} ({row.item_code}) has no batch entries to rebuild.")
	if flt(sum(allocation.values()), 6) != flt(row.qty, 6):
		frappe.throw(f"{document.name}, row {row.idx} ({row.item_code}) batch quantity does not match the row quantity.")

	return allocation


def _create_batch_bundle(document, row, allocation):
	voucher_exists = frappe.db.exists(document.doctype, document.name)
	bundle = SerialBatchCreation(
		{
			"item_code": row.item_code,
			"warehouse": row.warehouse,
			"posting_date": TARGET_POSTING_DATE,
			"posting_time": document.posting_time,
			"voucher_type": document.doctype,
			"voucher_no": document.name if voucher_exists else "",
			"voucher_detail_no": row.name if voucher_exists else "",
			"qty": row.qty,
			"avg_rate": row.valuation_rate,
			"type_of_transaction": "Inward",
			"company": document.company,
			"use_serial_batch_fields": 1,
			"do_not_submit": True,
			"batches": frappe._dict(allocation),
		}
	).make_serial_and_batch_bundle()

	if not bundle:
		frappe.throw(f"Could not create a batch bundle for row {row.idx} ({row.item_code}).")

	row.serial_and_batch_bundle = bundle.name
	row.use_serial_batch_fields = 1
