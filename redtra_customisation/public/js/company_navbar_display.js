// Copyright (c) 2024, Redtra Customisation
// License: MIT

/**
 * Company Display in Navbar
 * Shows current company in the navigation bar for multi-company environments
 * Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
 */

class CompanyNavbarDisplay {
	constructor() {
		this.currentCompany = null;
		this.displayElement = null;
		this.isInitialized = false;

		// Bind methods
		this.updateDisplay = this.updateDisplay.bind(this);
		this.handleCompanyChange = this.handleCompanyChange.bind(this);

		// Initialize when DOM is ready
		if (document.readyState === 'loading') {
			document.addEventListener('DOMContentLoaded', () => this.initialize());
		} else {
			this.initialize();
		}
	}

	/**
	 * Initialize the company navbar display
	 * Requirements: 12.1, 12.3
	 */
	initialize() {
		if (this.isInitialized) return;

		// Wait for Frappe to be ready
		if (typeof frappe === 'undefined' || !frappe.session) {
			setTimeout(() => this.initialize(), 100);
			return;
		}

		// Create display element
		this.createDisplayElement();

		// Get initial company
		this.getCurrentCompany();

		// Setup company change detection
		this.setupCompanyChangeDetection();

		this.isInitialized = true;
		console.log('Company Navbar Display initialized');
	}

	/**
	 * Create the company display element in the navbar
	 * Requirements: 12.1, 12.3
	 */
	createDisplayElement() {
		// Find the navbar
		const navbar = document.querySelector('.navbar-nav') || document.querySelector('.navbar');
		if (!navbar) {
			
			setTimeout(() => this.createDisplayElement(), 500);
			return;
		}

		// Check if display already exists
		if (document.getElementById('company-navbar-display')) {
			this.displayElement = document.getElementById('company-navbar-display');
			return;
		}

		// Create company display element
		const companyDisplay = document.createElement('li');
		companyDisplay.id = 'company-navbar-display';
		companyDisplay.className = 'nav-item company-display';

		companyDisplay.innerHTML = `
			<div class="nav-link company-info">
				<span class="company-icon">🏢</span>
				<span class="company-name" id="current-company-name">Loading...</span>
			</div>
		`;

		// Insert before the user menu (usually the last item)
		const userMenu = navbar.querySelector('.dropdown') || navbar.lastElementChild;
		if (userMenu) {
			navbar.insertBefore(companyDisplay, userMenu);
		} else {
			navbar.appendChild(companyDisplay);
		}

		this.displayElement = companyDisplay;

		// Add styles
		this.addStyles();
	}

	/**
	 * Add CSS styles for the company display
	 * Requirements: 12.3
	 */
	addStyles() {
		if (document.getElementById('company-navbar-styles')) return;

		const styles = document.createElement('style');
		styles.id = 'company-navbar-styles';
		styles.textContent = `
			.company-display {
				margin-right: 15px;
			}
			
			.company-info {
				display: flex;
				align-items: center;
				padding: 8px 12px !important;
				background: rgba(255, 255, 255, 0.1);
				border-radius: 6px;
				color: #fff !important;
				text-decoration: none !important;
				font-size: 13px;
				font-weight: 500;
				transition: all 0.2s ease;
				cursor: default;
			}
			
			.company-info:hover {
				background: rgba(255, 255, 255, 0.15);
				color: #fff !important;
			}
			
			.company-icon {
				margin-right: 6px;
				font-size: 14px;
			}
			
			.company-name {
				max-width: 150px;
				overflow: hidden;
				text-overflow: ellipsis;
				white-space: nowrap;
			}
			
			/* Dark theme support */
			.dark .company-info {
				background: rgba(0, 0, 0, 0.2);
				color: #e0e0e0 !important;
			}
			
			.dark .company-info:hover {
				background: rgba(0, 0, 0, 0.3);
				color: #fff !important;
			}
			
			/* Mobile responsive */
			@media (max-width: 768px) {
				.company-display {
					margin-right: 8px;
				}
				
				.company-name {
					max-width: 100px;
				}
				
				.company-info {
					padding: 6px 8px !important;
					font-size: 12px;
				}
			}
		`;

		document.head.appendChild(styles);
	}

	/**
	 * Get the current company from Frappe session or defaults
	 * Requirements: 12.2, 12.5
	 */
	getCurrentCompany() {
		// Try to get company from various sources
		let company = null;

		// 1. From frappe.defaults (most reliable)
		if (frappe.defaults && frappe.defaults.get_default) {
			company = frappe.defaults.get_default('Company');
		}

		// 2. From frappe.boot (fallback)
		if (!company && frappe.boot && frappe.boot.default_company) {
			company = frappe.boot.default_company;
		}

		// 3. From user defaults (another fallback)
		if (!company && frappe.user_defaults && frappe.user_defaults.Company) {
			company = frappe.user_defaults.Company;
		}

		// 4. From session user (last resort)
		if (!company && frappe.session && frappe.session.user_defaults) {
			company = frappe.session.user_defaults.Company;
		}

		if (company && company !== this.currentCompany) {
			this.currentCompany = company;
			this.updateDisplay();
		} else if (!company) {
			// If no company found, try to get the first available company
			this.getFirstAvailableCompany();
		}
	}

	/**
	 * Get the first available company if no default is set
	 */
	getFirstAvailableCompany() {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Company',
				fields: ['name', 'company_name'],
				limit: 1,
				order_by: 'creation'
			},
			callback: (r) => {
				if (r.message && r.message.length > 0) {
					this.currentCompany = r.message[0].name;
					this.updateDisplay();
				}
			}
		});
	}

	/**
	 * Update the display with current company information
	 * Requirements: 12.1, 12.2, 12.5
	 */
	updateDisplay() {
		if (!this.displayElement || !this.currentCompany) return;

		const companyNameElement = this.displayElement.querySelector('#current-company-name');
		if (!companyNameElement) return;

		// Get company display name (abbreviation or full name)
		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Company',
				fieldname: ['company_name', 'abbr'],
				filters: { name: this.currentCompany }
			},
			callback: (r) => {
				if (r.message) {
					const displayName = this.getCompanyDisplayName(r.message);
					companyNameElement.textContent = displayName;
					companyNameElement.title = `Current Company: ${r.message.company_name}`;
				}
			}
		});
	}

	/**
	 * Get appropriate display name for company
	 * Requirements: 12.3, 12.4
	 */
	getCompanyDisplayName(companyData) {
		const { company_name, abbr } = companyData;

		// Use abbreviation if available and short
		if (abbr && abbr.length <= 6) {
			return abbr;
		}

		// Use first word of company name if it's reasonable length
		const firstWord = company_name.split(' ')[0];
		if (firstWord.length <= 12) {
			return firstWord;
		}

		// Truncate company name if too long
		return company_name.length > 15 ?
			company_name.substring(0, 12) + '...' :
			company_name;
	}

	/**
	 * Setup detection for company changes
	 * Requirements: 12.2, 12.5
	 */
	setupCompanyChangeDetection() {
		// Monitor frappe.defaults changes
		if (frappe.defaults && frappe.defaults.get_default) {
			// Override the set_default method to detect changes
			const originalSetDefault = frappe.defaults.set_default;
			frappe.defaults.set_default = (...args) => {
				const result = originalSetDefault.apply(frappe.defaults, args);
				if (args[0] === 'Company') {
					this.handleCompanyChange(args[1]);
				}
				return result;
			};
		}

		// Monitor route changes that might indicate company context changes
		$(document).on('page-change', () => {
			setTimeout(() => this.getCurrentCompany(), 100);
		});

		// Monitor form loads that might have company context
		frappe.ui.form && frappe.ui.form.on && frappe.ui.form.on('refresh', () => {
			setTimeout(() => this.getCurrentCompany(), 100);
		});

		// Periodic check for company changes (fallback)
		setInterval(() => {
			this.getCurrentCompany();
		}, 5000);
	}

	/**
	 * Handle company change events
	 * Requirements: 12.2, 12.5
	 */
	handleCompanyChange(newCompany) {
		if (newCompany && newCompany !== this.currentCompany) {
			this.currentCompany = newCompany;
			this.updateDisplay();

			// Trigger custom event for other components
			const event = new CustomEvent('company-changed', {
				detail: { company: newCompany }
			});
			document.dispatchEvent(event);
		}
	}

	/**
	 * Get current company (public method)
	 * Requirements: 12.1
	 */
	getCurrentCompanyName() {
		return this.currentCompany;
	}

	/**
	 * Manually refresh the display
	 * Requirements: 12.5
	 */
	refresh() {
		this.getCurrentCompany();
	}

	/**
	 * Destroy the company display (cleanup)
	 */
	destroy() {
		if (this.displayElement) {
			this.displayElement.remove();
		}

		const styles = document.getElementById('company-navbar-styles');
		if (styles) {
			styles.remove();
		}

		this.isInitialized = false;
	}
}

// Initialize company navbar display when script loads
let companyNavbarDisplay = null;

// Wait for frappe to be available
function initializeCompanyDisplay() {
	if (typeof frappe !== 'undefined' && frappe.session) {
		if (!companyNavbarDisplay) {
			companyNavbarDisplay = new CompanyNavbarDisplay();
		}
	} else {
		setTimeout(initializeCompanyDisplay, 100);
	}
}

// Start initialization
initializeCompanyDisplay();

// Export for global access
window.CompanyNavbarDisplay = CompanyNavbarDisplay;
window.companyNavbarDisplay = companyNavbarDisplay;

// Frappe integration
// Frappe integration
if (window.frappe && frappe.ready) {
	frappe.ready(() => {
		if (!companyNavbarDisplay) {
			companyNavbarDisplay = new CompanyNavbarDisplay();
			window.companyNavbarDisplay = companyNavbarDisplay;
		}
	});
}