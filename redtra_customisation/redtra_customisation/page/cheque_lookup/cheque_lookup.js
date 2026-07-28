// Copyright (c) 2026, Redtra Customisation contributors

frappe.pages['cheque-lookup'].on_page_load = (wrapper) => new ChequeLookup(wrapper);

class ChequeLookup {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		frappe.ui.make_app_page({ parent: wrapper, title: __('Cheque Lookup'), single_column: true });
		this.body = this.wrapper.find('.layout-main-section');
		this.render();
	}

	render() {
		this.body.html(`
		<style>
		.cheque-lookup{max-width:1180px;margin:auto;padding:10px 0 28px}.cheque-hero{padding:28px;border-radius:18px;background:linear-gradient(125deg,#1d3557,#087f75);color:#fff;box-shadow:0 14px 32px #0f172a30}.cheque-hero h2{margin:0 0 5px;color:inherit;font-weight:700}.cheque-hero p{margin:0 0 20px;color:#ffffffcf}.cheque-search{display:flex;gap:10px;max-width:700px}.cheque-search input{flex:1;border:0;border-radius:10px;padding:10px 14px;color:#111}.cheque-search .btn{border-radius:10px;font-weight:600}.cheque-results{margin-top:22px}.cheque-empty{border:1px dashed var(--border-color);border-radius:14px;padding:42px;text-align:center;color:var(--text-muted)}.cheque-card{margin-bottom:20px;border:1px solid var(--border-color);border-radius:16px;overflow:hidden;background:var(--card-bg);box-shadow:0 5px 20px #0f172a10}.cheque-head{display:flex;justify-content:space-between;gap:16px;padding:20px 22px;border-bottom:1px solid var(--border-color)}.cheque-head h3{margin:0 0 4px;font-size:18px}.cheque-amount{text-align:right;font-weight:700;font-size:22px}.cheque-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:20px 22px}.cheque-kv{padding:10px 12px;border-radius:10px;background:var(--fg-hover-color)}.cheque-kv label{display:block;margin-bottom:3px;color:var(--text-muted);font-size:11px;font-weight:600;text-transform:uppercase}.cheque-kv span{font-size:13px;overflow-wrap:anywhere}.cheque-section{padding:0 22px 22px}.cheque-section h4{margin:4px 0 12px;font-size:14px}.cheque-table{border:1px solid var(--border-color);border-radius:10px;overflow:hidden}.cheque-table th{background:var(--fg-hover-color);font-size:11px;text-transform:uppercase;color:var(--text-muted)}.cheque-table td,.cheque-table th{padding:11px 12px}.cheque-payment{display:flex;justify-content:space-between;gap:12px;padding:14px;border:1px solid var(--border-color);border-radius:10px;background:var(--fg-hover-color)}.cheque-action{display:inline-block;margin-top:5px;font-size:12px;font-weight:600;color:var(--primary)}.cheque-expense{font-size:12px;line-height:1.5}.cheque-pill{display:inline-block;padding:3px 9px;border-radius:999px;background:#e2e8f0;color:#334155;font-size:12px;font-weight:600}.cheque-pill.pending{background:#fef3c7;color:#92400e}.cheque-pill.converted,.cheque-pill.paid,.cheque-pill.collected{background:#dcfce7;color:#166534}.cheque-pill.cancelled,.cheque-pill.bounced{background:#fee2e2;color:#b91c1c}@media(max-width:768px){.cheque-search,.cheque-payment,.cheque-head{flex-direction:column}.cheque-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cheque-amount{text-align:left}}
		</style>
		<div class="cheque-lookup"><div class="cheque-hero"><h2>${__('Find a cheque')}</h2><p>${__('See the post-dated cheque, payment entry and all linked invoices in one place.')}</p><form class="cheque-search"><input placeholder="${__('Enter cheque or reference number')}" autocomplete="off"><button class="btn btn-primary" type="submit">${__('Search')}</button></form></div><div class="cheque-results"><div class="cheque-empty">${__('Enter a cheque number to begin.')}</div></div></div>`);
		this.body.find('.cheque-search').on('submit', (event) => { event.preventDefault(); this.search(); });
	}

	search() {
		const cheque_no = (this.body.find('.cheque-search input').val() || '').trim();
		if (!cheque_no) return frappe.show_alert({ message: __('Enter a cheque number'), indicator: 'orange' });
		const $button = this.body.find('.cheque-search button').prop('disabled', true).text(__('Searching…'));
		this.body.find('.cheque-results').html(`<div class="cheque-empty">${__('Looking up cheque details…')}</div>`);
		frappe.call({ method: 'redtra_customisation.redtra_customisation.page.cheque_lookup.cheque_lookup.get_cheque_details', args: { cheque_no }, callback: (r) => this.results(r.message || {}), always: () => $button.prop('disabled', false).text(__('Search')) });
	}

	results(data) {
		const matches = data.matches || [];
		if (!matches.length) return this.body.find('.cheque-results').html(`<div class="cheque-empty"><strong>${__('No cheque found')}</strong><br>${__('Try the exact cheque/reference number or part of it.')}</div>`);
		this.body.find('.cheque-results').html(`<h3 style="margin:0 0 12px">${matches.length === 1 ? __('Cheque details') : __('{0} cheque records found', [matches.length])}</h3>${matches.map((row) => this.card(row)).join('')}`);
		this.body.find('[data-route]').on('click', (e) => { e.preventDefault(); frappe.set_route(...$(e.currentTarget).data('route').split('|')); });
	}

	card(pdc) {
		const currency = pdc.currency || frappe.defaults.get_default('currency');
		const invoices = (pdc.invoices || []).map((i) => `<tr><td>${this.link(i.doctype,i.name,i.name,i.has_access)}<br>${this.action(i.doctype,i.name,__('Open invoice'),i.has_access)}</td><td>${this.e(i.doctype)}</td><td>${this.project(i.project)}</td><td>${this.e(i.invoice_reference_no || '—')}</td><td>${this.date(i.posting_date)}</td><td class="text-right">${this.money(i.grand_total ?? i.total_amount,i.currency || currency)}</td><td class="text-right">${this.money(i.outstanding_amount ?? i.pdc_outstanding_amount,i.currency || currency)}</td><td>${this.expense(i,currency)}</td><td class="text-right"><strong>${this.money(i.allocated_amount,i.currency || currency)}</strong></td><td>${this.pill(i.status || 'Linked')}</td></tr>`).join('');
		return `<div class="cheque-card"><div class="cheque-head"><div><h3>${this.link('Post Dated Cheques',pdc.name,pdc.reference_no || pdc.name,true)}</h3><div class="text-muted">${this.e(pdc.party_name || pdc.party || '—')} · ${this.e(pdc.payment_type || '—')}</div></div><div class="cheque-amount">${this.money(pdc.amount,currency)}<br>${this.pill(pdc.status || 'Pending')}</div></div><div class="cheque-grid">${this.kv(__('Cheque date'),this.date(pdc.reference_date))}${this.kv(__('Posting date'),this.date(pdc.posting_date))}${this.kv(__('Company'),pdc.company || '—')}${this.kvHtml(__('Project'),this.project(pdc.project))}${this.kv(__('Payment mode'),pdc.mode_of_payment || '—')}${this.kv(__('Bank account'),pdc.bank_account || '—')}${this.kv(__('Party type'),pdc.party_type || '—')}${this.kv(__('PDC reference'),pdc.name)}</div><div class="cheque-section">${this.payment(pdc.payment_entry,currency)}</div><div class="cheque-section"><h4>${__('Linked invoices')} (${(pdc.invoices || []).length})</h4>${invoices ? `<div class="table-responsive"><table class="table cheque-table"><thead><tr><th>${__('Invoice')}</th><th>${__('Type')}</th><th>${__('Project')}</th><th>${__('External Ref.')}</th><th>${__('Date')}</th><th class="text-right">${__('Total')}</th><th class="text-right">${__('Outstanding')}</th><th>${__('Expense')}</th><th class="text-right">${__('Allocated')}</th><th>${__('Status')}</th></tr></thead><tbody>${invoices}</tbody></table></div>` : `<div class="text-muted">${__('No invoices are linked to this cheque.')}</div>`}</div>${pdc.notes ? `<div class="cheque-section"><h4>${__('Notes')}</h4><div class="text-muted">${this.e(pdc.notes)}</div></div>` : ''}</div>`;
	}

	payment(p,currency) { if (!p) return `<h4>${__('Payment entry')}</h4><div class="text-muted">${__('This cheque has not been converted to a payment entry yet.')}</div>`; if (!p.has_access) return `<h4>${__('Payment entry')}</h4><div class="text-muted">${__('A payment entry exists, but you do not have permission to view it.')}</div>`; return `<h4>${__('Payment entry')}</h4><div class="cheque-payment"><div>${this.link('Payment Entry',p.name,p.name,true)}<br><span class="text-muted">${this.e(p.mode_of_payment || '—')} · ${this.date(p.posting_date)}</span></div><div class="text-right">${this.pill(p.status || '—')}<br><strong>${this.money(p.received_amount || p.paid_amount,currency)}</strong></div></div>`; }
	kv(label,value) { return `<div class="cheque-kv"><label>${this.e(label)}</label><span>${this.e(value)}</span></div>`; }
	kvHtml(label,value) { return `<div class="cheque-kv"><label>${this.e(label)}</label><span>${value || '—'}</span></div>`; }
	link(dt,name,label,can) { return can && name ? `<a href="#" data-route="Form|${this.a(dt)}|${this.a(name)}">${this.e(label)}</a>` : this.e(label || '—'); }
	action(dt,name,label,can) { return can && name ? `<a href="#" class="cheque-action" data-route="Form|${this.a(dt)}|${this.a(name)}">${this.e(label)} →</a>` : ''; }
	project(project) { return project ? `${this.link('Project',project,project,true)}<br>${this.action('Project',project,__('Open project'),true)}` : '—'; }
	expense(invoice,currency) { const lines=invoice.expense_lines || []; if (!lines.length) return '—'; return `<div class="cheque-expense">${lines.map((line) => `${this.e(line.expense_account || line.item_name || line.item_code || '—')}<br><strong>${this.money(line.amount,currency)}</strong>`).join('<hr style="margin:5px 0">')}</div>`; }
	pill(value) { const key=String(value || '').toLowerCase().replace(/\s+/g,'-'); return `<span class="cheque-pill ${this.a(key)}">${this.e(value || '—')}</span>`; }
	date(value) { return value ? frappe.datetime.str_to_user(value) : '—'; }
	money(value,currency) { return value === undefined || value === null || value === '' ? '—' : format_currency(value,currency); }
	e(value) { return frappe.utils.escape_html(String(value ?? '')); }
	a(value) { return this.e(value).replace(/&quot;/g,''); }
}
