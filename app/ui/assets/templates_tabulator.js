/**
 * ReconHub - Tabulator Controller cho Màn hình Danh sách Template (/templates)
 * Phong cách Fluent Compact + Oracle APEX Interactive Grid
 */

window.templatesTabulator = {
    table: null,
    storageKey: "reconhub_templates_views",
    baseColumnDefs: null,
    activeViewId: null,
    resizeObserver: null,
    isAdmin: false,
    _container: null,
    _docClickBound: false,

    escapeHtml: function(str) {
        return String(str == null ? "" : str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    },

    getDefaultLayout: function() {
        return [
            { field: "actions", width: 110 },
            { field: "code", width: 155 },
            { field: "name", width: null },
            { field: "field_count", width: 105 },
            { field: "profiles_text", width: 170 },
            { field: "current_version", width: 100 },
            { field: "owner", width: 110 },
            { field: "status", width: 130 },
            { field: "last_run_text", width: 145 }
        ];
    },

    closeFloatingMenu: function() {
        var existing = document.getElementById("tmpl-floating-action-menu");
        if (existing && existing.parentNode) {
            existing.parentNode.removeChild(existing);
        }
    },

    triggerRowAction: function(action, rowId) {
        this.closeFloatingMenu();
        if (!action || rowId === undefined || rowId === null || rowId === "") return;
        if (window.dash_clientside && typeof window.dash_clientside.set_props === "function") {
            try {
                window.dash_clientside.set_props("tmpl-row-action-trigger", {
                    data: {
                        action: String(action),
                        id: rowId,
                        ts: Date.now()
                    }
                });
            } catch (err) {
                console.warn("[templatesTabulator] Lỗi triggerRowAction:", err);
            }
        }
    },

    openFloatingMenu: function(btnEl, rowId) {
        var self = this;
        var existing = document.getElementById("tmpl-floating-action-menu");
        if (existing && existing.getAttribute("data-row-id") === String(rowId)) {
            this.closeFloatingMenu();
            return;
        }
        this.closeFloatingMenu();

        var menu = document.createElement("div");
        menu.id = "tmpl-floating-action-menu";
        menu.className = "tab-floating-menu";
        menu.setAttribute("data-row-id", String(rowId));

        var items = [
            {
                action: "clone",
                label: "Nhân bản",
                icon: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>'
            },
            {
                action: "export",
                label: "Export JSON",
                icon: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>'
            },
            {
                action: "sample",
                label: "Tải file mẫu Excel",
                icon: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/></svg>'
            },
            { divider: true },
            {
                action: "archive",
                label: "Lưu trữ",
                tone: "warn",
                icon: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>'
            }
        ];

        if (this.isAdmin) {
            items.push({ divider: true });
            items.push({
                action: "delete",
                label: "Xóa template",
                tone: "danger",
                icon: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>'
            });
        }

        items.forEach(function(item) {
            if (item.divider) {
                var div = document.createElement("div");
                div.className = "tab-floating-menu-divider";
                menu.appendChild(div);
                return;
            }
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "tab-floating-menu-item" + (item.tone ? " is-" + item.tone : "");
            btn.innerHTML = item.icon + "<span>" + self.escapeHtml(item.label) + "</span>";
            btn.addEventListener("click", function(e) {
                e.stopPropagation();
                self.triggerRowAction(item.action, rowId);
            });
            menu.appendChild(btn);
        });

        document.body.appendChild(menu);

        var rect = btnEl.getBoundingClientRect();
        var menuRect = menu.getBoundingClientRect();
        var top = rect.bottom + 4;
        var left = rect.left;

        if (top + menuRect.height > window.innerHeight - 8) {
            top = Math.max(8, rect.top - menuRect.height - 4);
        }
        if (left + menuRect.width > window.innerWidth - 8) {
            left = Math.max(8, window.innerWidth - menuRect.width - 8);
        }

        menu.style.top = top + "px";
        menu.style.left = left + "px";
    },

    /**
     * Khởi tạo bảng Tabulator cho /templates
     */
    init: function(containerId, rowData, isAdmin) {
        var container = document.getElementById(containerId);
        if (!container) return;

        if (typeof Tabulator === "undefined") {
            console.error("[templatesTabulator] Thư viện Tabulator chưa sẵn sàng.");
            return;
        }

        var self = this;
        this.isAdmin = !!isAdmin;
        this._container = container;
        this.closeFloatingMenu();

        if (!this._docClickBound) {
            this._docClickBound = true;
            document.addEventListener("click", function(e) {
                var menu = document.getElementById("tmpl-floating-action-menu");
                if (!menu) return;
                if (menu.contains(e.target)) return;
                if (e.target && e.target.closest && e.target.closest("[data-tmpl-menu-btn]")) return;
                self.closeFloatingMenu();
            });
            document.addEventListener("keydown", function(e) {
                if (e.key === "Escape") {
                    self.closeFloatingMenu();
                }
            });
        }

        function createHeaderInputFilter(placeholder) {
            return function(cell, onRendered, success, cancel, editorParams) {
                var input = document.createElement("input");
                input.type = "text";
                input.placeholder = placeholder || "Tìm...";
                input.className = "tab-fluent-filter-input";

                input.addEventListener("mousedown", function(e) { e.stopPropagation(); });
                input.addEventListener("click", function(e) { e.stopPropagation(); });
                input.addEventListener("keydown", function(e) { e.stopPropagation(); });

                input.addEventListener("input", function() {
                    success(input.value);
                });
                return input;
            };
        }

        this.baseColumnDefs = [
            {
                title: "Thao tác",
                field: "actions",
                width: 110,
                minWidth: 85,
                hozAlign: "center",
                headerHozAlign: "center",
                headerSort: false,
                resizable: false,
                formatter: function(cell) {
                    var data = cell.getData() || {};
                    var tid = data.code || data.template_id || data.id || "";
                    var actionId = data.action_index || data.id || tid;
                    var editHref = "/templates/" + encodeURIComponent(String(tid)) + "/edit";

                    var html = '<div class="tab-actions-group">';
                    html += '<a href="' + editHref + '" class="tab-icon-btn" title="Sửa template" aria-label="Sửa template">' +
                        '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                        '<path d="M12 20h9"></path>' +
                        '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>' +
                        '</svg></a>';

                    if (self.isAdmin) {
                        html += '<button type="button" class="tab-icon-btn tab-icon-btn-danger" data-tmpl-action="delete" data-tmpl-id="' +
                            self.escapeHtml(actionId) + '" title="Xóa template" aria-label="Xóa template">' +
                            '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>' +
                            '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg></button>';
                    }

                    html += '<button type="button" class="tab-icon-btn" data-tmpl-menu-btn="1" data-tmpl-id="' +
                        self.escapeHtml(actionId) + '" title="Thao tác khác" aria-label="Thao tác khác">' +
                        '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                        '<circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle>' +
                        '</svg></button>';
                    html += '</div>';
                    return html;
                }
            },
            {
                title: "Mã template",
                field: "code",
                width: 155,
                minWidth: 80,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc mã..."),
                headerSort: true,
                formatter: function(cell) {
                    var data = cell.getData() || {};
                    var val = cell.getValue() || data.template_id || "";
                    var editHref = "/templates/" + encodeURIComponent(String(val)) + "/edit";
                    return '<a href="' + editHref + '" class="rh-code tab-cell-code">' + self.escapeHtml(val) + '</a>';
                }
            },
            {
                title: "Tên & Nhận diện file",
                field: "name",
                minWidth: 80,
                widthGrow: 3,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc tên / file..."),
                headerFilterFunc: function(headerValue, rowValue, rowData) {
                    if (!headerValue) return true;
                    var term = String(headerValue).trim().toLowerCase();
                    if (!term) return true;
                    var name = String((rowData && rowData.name) || rowValue || "").toLowerCase();
                    var pattern = String((rowData && rowData.file_pattern) || "").toLowerCase();
                    var sheet = String((rowData && rowData.sheet) || "").toLowerCase();
                    return name.indexOf(term) !== -1 || pattern.indexOf(term) !== -1 || sheet.indexOf(term) !== -1;
                },
                headerSort: true,
                formatter: function(cell) {
                    var data = cell.getData() || {};
                    var val = cell.getValue() || "";
                    var pattern = data.file_pattern || "—";
                    var fileSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>';
                    return '<div class="tab-cell-name-box">' +
                        '<div class="tab-cell-name">' + self.escapeHtml(val) + '</div>' +
                        '<div class="tab-cell-desc tab-cell-file">' + fileSvg + '<span class="rh-code">' + self.escapeHtml(pattern) + '</span></div>' +
                        '</div>';
                }
            },
            {
                title: "Số trường",
                field: "field_count",
                width: 105,
                minWidth: 70,
                hozAlign: "center",
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Số..."),
                headerSort: true,
                formatter: function(cell) {
                    var n = Number(cell.getValue() || 0);
                    var cls = n > 0 ? "tab-pill tab-pill-blue" : "tab-pill tab-pill-gray";
                    return '<span class="' + cls + '">' + n + ' trường</span>';
                }
            },
            {
                title: "Profiles",
                field: "profiles_text",
                width: 170,
                minWidth: 90,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc profile..."),
                headerSort: true,
                formatter: function(cell) {
                    var profiles = (cell.getData() && cell.getData().profiles) || [];
                    if (!profiles || profiles.length === 0) {
                        return '<span class="tab-cell-muted">—</span>';
                    }
                    var keySvg = '<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>';
                    var pills = profiles.map(function(p) {
                        var pname = p.name || p.profile_id || p.code || "";
                        if (p.is_default) {
                            return '<span class="tab-pill tab-pill-primary">' + keySvg + ' ' + self.escapeHtml(pname) + '</span>';
                        }
                        return '<span class="tab-pill tab-pill-gray">' + self.escapeHtml(pname) + '</span>';
                    });
                    return '<div class="tab-pills-wrap">' + pills.join("") + '</div>';
                }
            },
            {
                title: "Phiên bản",
                field: "current_version",
                width: 100,
                minWidth: 70,
                hozAlign: "center",
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Ver..."),
                headerSort: true,
                formatter: function(cell) {
                    var v = cell.getValue() || 1;
                    return '<span class="tab-pill tab-pill-outline">v' + self.escapeHtml(v) + '</span>';
                }
            },
            {
                title: "Chủ sở hữu",
                field: "owner",
                width: 110,
                minWidth: 75,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc user..."),
                headerSort: true,
                formatter: function(cell) {
                    var owner = cell.getValue() || "—";
                    return '<span class="tab-cell-muted">@' + self.escapeHtml(owner) + '</span>';
                }
            },
            {
                title: "Trạng thái",
                field: "status",
                width: 130,
                minWidth: 85,
                hozAlign: "center",
                headerHozAlign: "center",
                headerFilter: function(cell, onRendered, success, cancel, editorParams) {
                    var select = document.createElement("select");
                    select.className = "tab-fluent-filter-select";
                    select.innerHTML = '<option value="">Tất cả</option>' +
                        '<option value="ACTIVE">Hoạt động</option>' +
                        '<option value="DRAFT">Bản nháp</option>' +
                        '<option value="ARCHIVED">Đã lưu trữ</option>';

                    select.addEventListener("mousedown", function(e) { e.stopPropagation(); });
                    select.addEventListener("click", function(e) { e.stopPropagation(); });
                    select.addEventListener("change", function() {
                        success(select.value);
                    });
                    return select;
                },
                headerFilterFunc: function(headerValue, rowValue) {
                    if (!headerValue) return true;
                    return String(rowValue).toUpperCase() === String(headerValue).toUpperCase();
                },
                headerSort: true,
                formatter: function(cell) {
                    var val = String(cell.getValue() || "DRAFT").toUpperCase();
                    if (val === "ACTIVE") {
                        return '<span class="tab-status-chip tab-status-active">● Hoạt động</span>';
                    } else if (val === "ARCHIVED") {
                        return '<span class="tab-status-chip tab-status-archived">● Đã lưu trữ</span>';
                    } else {
                        return '<span class="tab-status-chip tab-status-draft">● Bản nháp</span>';
                    }
                }
            },
            {
                title: "Run gần nhất",
                field: "last_run_text",
                width: 145,
                minWidth: 90,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc run..."),
                headerSort: true,
                formatter: function(cell) {
                    var lr = cell.getData() && cell.getData().last_run;
                    if (!lr) {
                        return '<span class="tab-cell-muted">Chưa chạy</span>';
                    }
                    var st = String(lr.status || "");
                    var toneCls = st === "DONE" ? "tab-pill-teal" : (st === "FAILED" ? "tab-pill-red" : "tab-pill-blue");
                    var finishedAt = lr.finished_at || "";
                    return '<div class="tab-cell-name-box">' +
                        '<a href="/runs/' + encodeURIComponent(String(lr.id || 0)) + '" class="tab-pill ' + toneCls + '">#' +
                        self.escapeHtml(lr.id) + ' · ' + self.escapeHtml(st) + '</a>' +
                        '<div class="tab-cell-desc">' + self.escapeHtml(finishedAt) + '</div>' +
                        '</div>';
                }
            }
        ];

        if (this.table) {
            try {
                this.table.destroy();
            } catch (e) {}
            this.table = null;
        }
        container.innerHTML = "";

        if (!container._rh_actions_bound) {
            container._rh_actions_bound = true;
            container.addEventListener("click", function(e) {
                var delBtn = e.target && e.target.closest ? e.target.closest("[data-tmpl-action]") : null;
                if (delBtn) {
                    e.stopPropagation();
                    var action = delBtn.getAttribute("data-tmpl-action");
                    var rowId = delBtn.getAttribute("data-tmpl-id");
                    self.triggerRowAction(action, rowId);
                    return;
                }
                var menuBtn = e.target && e.target.closest ? e.target.closest("[data-tmpl-menu-btn]") : null;
                if (menuBtn) {
                    e.stopPropagation();
                    var id = menuBtn.getAttribute("data-tmpl-id");
                    self.openFloatingMenu(menuBtn, id);
                }
            });
        }

        var initialColumns = this.baseColumnDefs.slice();

        this.table = new Tabulator("#" + containerId, {
            data: rowData || [],
            columns: initialColumns,
            height: "100%",
            layout: "fitColumns",
            movableColumns: true,
            resizableColumnFit: true,
            resizableColumnGuide: true,
            headerFilterLiveFilter: true,
            placeholder: "Không có dữ liệu phù hợp",
            pagination: true,
            paginationSize: 20,
            paginationSizeSelector: [10, 20, 50, 100],
            persistence: false
        });

        this.table.on("tableBuilt", function() {
            try {
                var views = self.getViews();
                var targetView = null;
                if (self.activeViewId) {
                    targetView = views.find(function(v) { return v.id === self.activeViewId; });
                }
                if (!targetView) {
                    targetView = views.find(function(v) { return v.isDefault; }) || views[0];
                }
                if (targetView && targetView.layout) {
                    self.activeViewId = targetView.id;
                    self.applyLayoutDirectly(targetView.layout);
                }
                self.refreshToolbarUI(self.activeViewId);

                if (window.ResizeObserver) {
                    if (self.resizeObserver) {
                        self.resizeObserver.disconnect();
                    }
                    self.resizeObserver = new ResizeObserver(function() {
                        if (self.table) {
                            self.table.redraw(true);
                        }
                    });
                    self.resizeObserver.observe(container);
                }

                var toggleBtn = document.getElementById("app-sidebar-toggle-btn");
                if (toggleBtn && !toggleBtn._rh_tmpl_tab_bound) {
                    toggleBtn._rh_tmpl_tab_bound = true;
                    toggleBtn.addEventListener("click", function() {
                        setTimeout(function() { if (self.table) self.table.redraw(true); }, 50);
                        setTimeout(function() { if (self.table) self.table.redraw(true); }, 150);
                        setTimeout(function() { if (self.table) self.table.redraw(true); }, 350);
                    });
                }

                setTimeout(function() {
                    if (self.table) self.table.redraw(true);
                }, 100);
            } catch (err) {
                console.warn("[templatesTabulator] Lỗi tableBuilt:", err);
            }
        });

        this.table.on("dataFiltered", function(filters) {
            if (!window.dash_clientside || typeof window.dash_clientside.set_props !== "function") return;
            try {
                var searchVal = "";
                var statusVal = "";
                (filters || []).forEach(function(f) {
                    if (f.field === "status" && f.value) {
                        statusVal = String(f.value);
                    } else if ((f.field === "name" || f.field === "code") && f.value && !searchVal) {
                        searchVal = String(f.value);
                    }
                });
                window.dash_clientside.set_props("tmpl-filter-search", { value: searchVal });
                window.dash_clientside.set_props("tmpl-filter-status", { value: statusVal });
            } catch (e) {}
        });

        this.table.on("columnMoved", function(col, allColumns) {
            try {
                self.closeFloatingMenu();
                self.showStatusNotification("Đã đổi vị trí cột. Bấm 'Lưu vị trí cột' để cập nhật template.");
            } catch (err) {
                console.warn("[templatesTabulator] Lỗi columnMoved:", err);
            }
        });

        this.table.on("columnResized", function(col) {
            try {
                self.closeFloatingMenu();
                self.showStatusNotification("Đã chỉnh độ rộng cột. Bấm 'Lưu vị trí cột' để lưu.");
            } catch (err) {
                console.warn("[templatesTabulator] Lỗi columnResized:", err);
            }
        });
    },

    getCurrentColumnLayout: function() {
        if (!this.table) return null;
        try {
            var cols = this.table.getColumns();
            return cols.map(function(c) {
                return {
                    field: c.getField(),
                    width: Math.round(c.getWidth())
                };
            }).filter(function(item) {
                return !!item.field;
            });
        } catch (err) {
            return null;
        }
    },

    applyLayoutDirectly: function(layout) {
        if (!this.table || !layout || !this.baseColumnDefs) return;
        var self = this;

        try {
            var items = [];
            if (Array.isArray(layout)) {
                items = layout.map(function(item) {
                    if (typeof item === "string") {
                        return { field: item, width: null };
                    }
                    return item;
                }).filter(function(it) {
                    return it && it.field;
                });
            }

            if (items.length > 0) {
                var colMap = {};
                this.baseColumnDefs.forEach(function(c) {
                    if (c.field) {
                        colMap[c.field] = Object.assign({}, c);
                    }
                });

                var reordered = [];
                items.forEach(function(it) {
                    var f = it.field;
                    if (colMap[f]) {
                        var col = colMap[f];
                        if (f === "name") {
                            col.minWidth = 80;
                            delete col.width;
                            col.widthGrow = 3;
                        } else if (f !== "actions") {
                            if (it.width && it.width > 30) {
                                col.width = it.width;
                            }
                        }
                        reordered.push(col);
                        delete colMap[f];
                    }
                });

                for (var k in colMap) {
                    var remCol = colMap[k];
                    if (k === "name") {
                        remCol.minWidth = 80;
                        delete remCol.width;
                        remCol.widthGrow = 3;
                    }
                    reordered.push(remCol);
                }

                this.table.setColumns(reordered);
                setTimeout(function() {
                    if (self.table) self.table.redraw(true);
                }, 50);
                setTimeout(function() {
                    if (self.table) self.table.redraw(true);
                }, 150);
            }
        } catch (err) {
            console.warn("[templatesTabulator] Layout setColumns error:", err);
        }
    },

    getViews: function() {
        try {
            var raw = localStorage.getItem(this.storageKey);
            if (raw) {
                var parsed = JSON.parse(raw);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    return parsed;
                }
            }
        } catch (e) {}

        var initViews = [
            {
                id: "default",
                name: "Mặc định hệ thống",
                isDefault: true,
                layout: this.getDefaultLayout()
            }
        ];
        this.saveViews(initViews);
        return initViews;
    },

    saveViews: function(views) {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(views));
        } catch (e) {}
    },

    saveCurrentView: function() {
        if (!this.table) return;
        var layout = this.getCurrentColumnLayout();
        if (!layout || layout.length === 0) return;

        var views = this.getViews();
        var activeId = this.activeViewId || "default";

        var target = views.find(function(v) { return v.id === activeId; });
        if (target) {
            target.layout = layout;
            this.saveViews(views);
            this.showStatusNotification("Đã lưu vị trí và độ rộng cột vào View: '" + target.name + "'");
        } else {
            this.saveNewView("Template cá nhân", true);
        }
    },

    saveNewView: function(viewName, setAsDefault) {
        if (!this.table) return;
        var name = (viewName || "").trim();
        if (!name) return;

        var layout = this.getCurrentColumnLayout();
        var views = this.getViews();
        var newId = "view_" + Date.now();

        if (setAsDefault) {
            views.forEach(function(v) { v.isDefault = false; });
        }

        views.push({
            id: newId,
            name: name,
            isDefault: !!setAsDefault,
            layout: layout || this.getDefaultLayout()
        });

        this.saveViews(views);
        this.activeViewId = newId;
        this.refreshToolbarUI(newId);
        this.showStatusNotification("Đã tạo Template mới: '" + name + "'");
    },

    applyView: function(viewId) {
        if (!this.table || !viewId) return;
        if (viewId === this.activeViewId) return;

        this.activeViewId = viewId;
        var views = this.getViews();
        var target = views.find(function(v) { return v.id === viewId; });

        if (target && target.layout) {
            this.applyLayoutDirectly(target.layout);
            this.showStatusNotification("Đã chuyển sang View: '" + target.name + "'");
        }
    },

    setDefaultView: function(viewId) {
        var targetId = viewId || this.activeViewId || "default";
        var views = this.getViews();
        views.forEach(function(v) {
            v.isDefault = (v.id === targetId);
        });
        this.saveViews(views);
        this.refreshToolbarUI(targetId);
        this.showStatusNotification("Đã đặt View làm mặc định khi mở trang.");
    },

    deleteView: function(viewId) {
        if (!viewId || viewId === "default") {
            this.showStatusNotification("Không thể xóa View mặc định hệ thống.");
            return;
        }

        var views = this.getViews().filter(function(v) { return v.id !== viewId; });
        this.saveViews(views);
        this.activeViewId = "default";
        var defaultView = views.find(function(v) { return v.id === "default"; }) || views[0];
        if (defaultView && defaultView.layout) {
            this.activeViewId = defaultView.id;
            this.applyLayoutDirectly(defaultView.layout);
        }
        this.refreshToolbarUI(this.activeViewId);
        this.showStatusNotification("Đã xóa Template thành công.");
    },

    resetToDefault: function() {
        if (this.table && this.baseColumnDefs) {
            this.applyLayoutDirectly(this.getDefaultLayout());
            this.showStatusNotification("Đã khôi phục vị trí cột mặc định.");
        }
    },

    refreshToolbarUI: function(selectValue) {
        var views = this.getViews();
        var selectData = views.map(function(v) {
            return {
                label: v.name + (v.isDefault ? " (Mặc định)" : ""),
                value: v.id
            };
        });

        if (window.dash_clientside && typeof window.dash_clientside.set_props === "function") {
            try {
                var props = { data: selectData };
                if (selectValue) {
                    props.value = selectValue;
                }
                window.dash_clientside.set_props("tmpl-view-select", props);
            } catch (e) {}
        }
    },

    showStatusNotification: function(msg) {
        var notifyEl = document.getElementById("tmpl-grid-notification");
        if (!notifyEl) return;
        notifyEl.textContent = msg;
        notifyEl.style.opacity = "1";
        setTimeout(function() {
            if (notifyEl) {
                notifyEl.style.opacity = "0";
            }
        }, 3000);
    }
};
