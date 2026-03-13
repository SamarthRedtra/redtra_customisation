(function () {
    var is_initialized = false;
    var observer_started = false;

    function setup_navbar_action() {
        if (is_initialized) return;
        if (!frappe || !frappe.ui || !frappe.ui.toolbar) {
            setTimeout(setup_navbar_action, 200);
            return;
        }

        // Legacy top navbar support (older Desk layout).
        insert_in_legacy_navbar();
        // New sidebar context-menu support (current layout in your screenshot).
        observe_and_insert_sidebar_menu_item();
        is_initialized = true;
    }

    function insert_in_legacy_navbar() {
        var menu = $("#navbar-user");
        if (!menu.length || menu.find(".date-session-menu-item").length) return;

        var item = $(
            '<li class="date-session-menu-item">' +
                '<a><i class="fa-fw fa fa-calendar"></i> ' +
                __("Set Date Session") +
                "</a>" +
            "</li>"
        );
        item.find("a").on("click", function () {
            open_date_session_dialog();
        });

        var inserted = false;
        menu.find("li > a").each(function () {
            var label = ($(this).text() || "").trim();
            if (label === __("Session Defaults")) {
                $(this).closest("li").after(item);
                inserted = true;
                return false;
            }
        });

        if (!inserted && frappe.ui.toolbar.add_dropdown_button) {
            frappe.ui.toolbar.add_dropdown_button(
                "user",
                __("Set Date Session"),
                function () {
                    open_date_session_dialog();
                },
                "fa fa-calendar"
            );
        }
    }

    function observe_and_insert_sidebar_menu_item() {
        if (observer_started || typeof MutationObserver === "undefined") return;
        observer_started = true;

        var observer = new MutationObserver(function () {
            $(".frappe-menu.context-menu:visible").each(function () {
                insert_in_sidebar_context_menu($(this));
            });
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    function insert_in_sidebar_context_menu($menu) {
        if (!$menu || !$menu.length) return;
        if ($menu.find(".date-session-menu-item").length) return;

        var $session_default_row = null;
        $menu.find(".dropdown-menu-item .menu-item-title").each(function () {
            var label = ($(this).text() || "").trim();
            if (label === __("Session Defaults")) {
                $session_default_row = $(this).closest(".dropdown-menu-item");
                return false;
            }
        });

        if (!$session_default_row || !$session_default_row.length) return;

        var $item = $(
            '<div class="dropdown-menu-item date-session-menu-item" style="cursor: pointer;">' +
                "<a>" +
                    '<div class="menu-item-icon">' +
                        frappe.utils.icon("calendar", "sm") +
                    "</div>" +
                    '<span class="menu-item-title">' + __("Set Date Session") + "</span>" +
                    '<div class="menu-item-icon" style="margin-left:auto"></div>' +
                "</a>" +
            "</div>"
        );

        $item.on("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            $(".context-menu:visible").hide();
            open_date_session_dialog();
            return false;
        });

        $session_default_row.after($item);
    }

    function open_date_session_dialog() {
        frappe.call({
            method:
                "redtra_customisation.redtra_customisation.doctype.date_session.date_session.get_active_date_session",
            callback: function (r) {
                var active = (r && r.message) || {};
                var default_date = active.session_date || frappe.datetime.get_today();

                frappe.prompt(
                    [
                        {
                            fieldname: "session_date",
                            fieldtype: "Date",
                            label: __("Session Date"),
                            reqd: 1,
                            default: default_date,
                        },
                    ],
                    function (values) {
                        frappe.call({
                            method:
                                "redtra_customisation.redtra_customisation.doctype.date_session.date_session.set_active_date_session",
                            args: {
                                session_date: values.session_date,
                            },
                            freeze: true,
                            freeze_message: __("Updating Date Session..."),
                            callback: function (res) {
                                if (res && res.message) {
                                    frappe.date_session = res.message;
                                }

                                frappe.show_alert({
                                    message: __("Date Session updated"),
                                    indicator: "green",
                                });

                                // Re-run refresh flow so new-doc overrides apply immediately.
                                if (window.cur_frm) {
                                    cur_frm.refresh();
                                }
                            },
                        });
                    },
                    __("Set Date Session"),
                    __("Save")
                );
            },
        });
    }

    if (frappe && frappe.ready) {
        frappe.ready(function () {
            setup_navbar_action();
        });
    } else {
        setup_navbar_action();
    }
})();
