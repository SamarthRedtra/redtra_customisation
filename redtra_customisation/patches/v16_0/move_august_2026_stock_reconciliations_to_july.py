import frappe
from frappe.utils import flt

from erpnext.stock.serial_batch_bundle import SerialBatchCreation


TARGET_POSTING_DATE = "2026-07-31"
CANCELLED_DOCUMENT = "MAT-RECO-2026-00026"
CANCELLED_AMENDMENT = "MAT-RECO-2026-00026-1"
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

# Fill this from the physical batch count before running the production migration.
# The key is the row number in MAT-RECO-2026-00026-1 and values are
# {batch_no: quantity}. Each split must equal the row's reconciliation quantity.
BATCH_ALLOCATIONS = {
	# 1: {"LLT2122022-Desmodur E 23": 10.0},
}


def execute():
	"""Move the August opening-stock reconciliations to 31 July 2026."""
	submitted_documents, cancelled_amendment = _validate_documents()
	_apply_batch_allocations(cancelled_amendment)

	for document in reversed(submitted_documents):
		document.cancel()

	cancelled_amendment.posting_date = TARGET_POSTING_DATE
	cancelled_amendment.save()
	cancelled_amendment.submit()

	for document in submitted_documents:
		amendment = frappe.copy_doc(document)
		amendment.amended_from = document.name
		amendment.posting_date = TARGET_POSTING_DATE
		amendment.insert()
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


def _apply_batch_allocations(document):
	missing_allocations = []
	for row in document.items:
		item = frappe.get_cached_value("Item", row.item_code, ["has_batch_no", "has_serial_no"], as_dict=True)
		if row.serial_and_batch_bundle or row.batch_no or not (item.has_batch_no or item.has_serial_no):
			continue

		if item.has_serial_no:
			frappe.throw(f"Row {row.idx} ({row.item_code}) requires serial-number allocation before this patch can run.")

		allocation = BATCH_ALLOCATIONS.get(row.idx)
		if not allocation:
			missing_allocations.append(f"{row.idx}: {row.item_code} ({flt(row.qty)})")
			continue

		_validate_batch_allocation(row, allocation)
		_create_batch_bundle(document, row, allocation)

	if missing_allocations:
		frappe.throw(
			"Add batch allocations for these rows in BATCH_ALLOCATIONS before running the patch:\n"
			+ "\n".join(missing_allocations)
		)


def _validate_batch_allocation(row, allocation):
	if flt(sum(allocation.values())) != flt(row.qty):
		frappe.throw(f"Batch allocation for row {row.idx} ({row.item_code}) must total {flt(row.qty)}.")

	valid_batches = frappe.get_all(
		"Batch",
		filters={"name": ("in", list(allocation)), "item": row.item_code, "disabled": 0},
		pluck="name",
	)
	missing_batches = set(allocation) - set(valid_batches)
	if missing_batches:
		frappe.throw(
			f"Invalid or disabled batch(es) for row {row.idx} ({row.item_code}): "
			+ ", ".join(sorted(missing_batches))
		)


def _create_batch_bundle(document, row, allocation):
	bundle = SerialBatchCreation(
		{
			"item_code": row.item_code,
			"warehouse": row.warehouse,
			"posting_date": TARGET_POSTING_DATE,
			"posting_time": document.posting_time,
			"voucher_type": document.doctype,
			"voucher_no": document.name,
			"voucher_detail_no": row.name,
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
