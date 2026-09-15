// Copyright (c) 2024, Redtra Customisation
// License: MIT

/**
 * Company chip for the legacy Desk navbar (`.navbar-nav`).
 * Frappe 17's desktop header is `.desktop-navbar.navbar` — do not mount there.
 */

function as_company_name(value) {
	if (Array.isArray(value)) {
		return value[0] || null;
	}
	return value || null;
}

function current_company() {
	if (!window.frappe) {
		return null;
	}
	return as_company_name(
		frappe.defaults?.get_user_default?.("Company") ||
			frappe.defaults?.get_default?.("Company") ||
			frappe.boot?.sysdefaults?.company ||
			frappe.user_defaults?.Company
	);
}

class CompanyNavbarDisplay {
	constructor() {
		this.currentCompany = null;
		this.displayElement = null;
		this.isInitialized = false;
		this.initialize();
	}

	initialize() {
		if (this.isInitialized) {
			return;
		}
		if (typeof frappe === "undefined" || !frappe.session) {
			setTimeout(() => this.initialize(), 100);
			return;
		}
		this.createDisplayElement();
		this.isInitialized = true;
	}

	createDisplayElement() {
		const navbar = document.querySelector(".navbar-nav");
		if (!navbar) {
			return;
		}
		if (navbar.closest(".desktop-navbar")) {
			return;
		}

		let el = document.getElementById("company-navbar-display");
		if (el) {
			this.displayElement = el;
			this.refresh();
			return;
		}

		el = document.createElement("li");
		el.id = "company-navbar-display";
		el.className = "nav-item company-display";
		el.hidden = true;
		el.innerHTML = `
			<div class="nav-link company-info">
				<span class="company-icon">🏢</span>
				<span class="company-name" id="current-company-name"></span>
			</div>
		`;

		const userMenu = navbar.querySelector(".dropdown") || navbar.lastElementChild;
		if (userMenu) {
			navbar.insertBefore(el, userMenu);
		} else {
			navbar.appendChild(el);
		}

		this.displayElement = el;
		this.addStyles();
		this.setupCompanyChangeDetection();
		this.refresh();
	}

	addStyles() {
		if (document.getElementById("company-navbar-styles")) {
			return;
		}
		const styles = document.createElement("style");
		styles.id = "company-navbar-styles";
		styles.textContent = `
			.company-display { margin-right: 15px; }
			.company-info {
				display: flex;
				align-items: center;
				padding: 8px 12px !important;
				background: var(--bg-color, rgba(0, 0, 0, 0.06));
				border-radius: 6px;
				color: var(--text-color, inherit) !important;
				font-size: 13px;
				font-weight: 500;
			}
			.company-icon { margin-right: 6px; font-size: 14px; }
			.company-name {
				max-width: 150px;
				overflow: hidden;
				text-overflow: ellipsis;
				white-space: nowrap;
			}
		`;
		document.head.appendChild(styles);
	}

	refresh() {
		const company = current_company();
		if (company && company !== this.currentCompany) {
			this.currentCompany = company;
		}
		this.updateDisplay();
		if (!this.currentCompany) {
			this.getFirstAvailableCompany();
		}
	}

	getFirstAvailableCompany() {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Company",
				fields: ["name", "company_name"],
				limit: 1,
				order_by: "creation",
			},
			callback: (r) => {
				if (r.message && r.message.length > 0) {
					this.currentCompany = r.message[0].name;
					this.updateDisplay();
				}
			},
		});
	}

	updateDisplay() {
		if (!this.displayElement || !this.currentCompany) {
			return;
		}
		const nameEl = this.displayElement.querySelector("#current-company-name");
		if (!nameEl) {
			return;
		}
		nameEl.textContent = this.currentCompany;
		this.displayElement.hidden = false;

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Company",
				fieldname: ["company_name", "abbr"],
				filters: { name: this.currentCompany },
			},
			callback: (r) => {
				if (!r.message) {
					return;
				}
				nameEl.textContent = this.getCompanyDisplayName(r.message);
				nameEl.title = `Current Company: ${r.message.company_name}`;
			},
		});
	}

	getCompanyDisplayName(companyData) {
		const { company_name, abbr } = companyData;
		if (abbr && abbr.length <= 6) {
			return abbr;
		}
		const firstWord = (company_name || "").split(" ")[0];
		if (firstWord.length && firstWord.length <= 12) {
			return firstWord;
		}
		if (!company_name) {
			return this.currentCompany;
		}
		return company_name.length > 15 ? company_name.substring(0, 12) + "..." : company_name;
	}

	setupCompanyChangeDetection() {
		$(document).on("page-change", () => {
			setTimeout(() => this.refresh(), 100);
		});
	}

	getCurrentCompanyName() {
		return this.currentCompany;
	}

	destroy() {
		this.displayElement?.remove();
		document.getElementById("company-navbar-styles")?.remove();
		this.isInitialized = false;
	}
}

function initializeCompanyDisplay() {
	if (typeof frappe === "undefined" || !frappe.session) {
		setTimeout(initializeCompanyDisplay, 100);
		return;
	}
	if (!window.companyNavbarDisplay) {
		window.companyNavbarDisplay = new CompanyNavbarDisplay();
	}
}

initializeCompanyDisplay();
window.CompanyNavbarDisplay = CompanyNavbarDisplay;
