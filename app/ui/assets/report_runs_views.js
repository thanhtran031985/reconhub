/**
 * ReconHub - Saved Views / Template Controller cho Màn hình Lịch sử báo cáo (/report-runs)
 * Sử dụng AG Grid Column State API (giữ nguyên dag.AgGrid và command_bar search DB).
 */

window.reportRunsViews = {
    gridId: "report-runs-grid",
    storageKey: "reconhub_report_runs_views",
    selectId: "rruns-view-select",
    notifyId: "rruns-grid-notification",
    activeViewId: null,
    _api: null,
    _suppressEvents: false,
    _initPromise: null,

    /**
     * Chờ và lấy AG Grid API an toàn (dash-ag-grid 35.x)
     */
    getGridApi: function() {
        var self = this;
        if (window.dash_ag_grid && typeof window.dash_ag_grid.getApiAsync === "function") {
            return window.dash_ag_grid.getApiAsync(this.gridId).then(function(api) {
                self._api = api;
                return api;
            });
        }
        return new Promise(function(resolve) {
            var attempts = 0;
            function check() {
                attempts += 1;
                if (window.dash_ag_grid && typeof window.dash_ag_grid.getApi === "function") {
                    try {
                        var api = window.dash_ag_grid.getApi(self.gridId);
                        if (api) {
                            self._api = api;
                            resolve(api);
                            return;
                        }
                    } catch (e) {}
                }
                if (attempts < 60) {
                    setTimeout(check, 100);
                } else {
                    resolve(null);
                }
            }
            check();
        });
    },

    /**
     * Khởi tạo listener AG Grid và áp View mặc định khi mở trang
     */
    init: function() {
        var self = this;
        if (this._initPromise) {
            return this._initPromise;
        }
        this._initPromise = this.getGridApi().then(function(api) {
            self._initPromise = null;
            if (!api) return null;

            self.bindGridEvents(api);

            var views = self.getViews();
            var targetView = null;
            if (self.activeViewId) {
                targetView = views.find(function(v) { return v.id === self.activeViewId; });
            }
            if (!targetView) {
                targetView = views.find(function(v) { return v.isDefault; }) || views[0];
            }

            if (targetView) {
                self.activeViewId = targetView.id;
                if (Array.isArray(targetView.columnState) && targetView.columnState.length > 0) {
                    self.applyLayoutDirectly(targetView.columnState);
                }
            }
            self.refreshToolbarUI(self.activeViewId);
            return api;
        }).catch(function(err) {
            self._initPromise = null;
            console.warn("[reportRunsViews] Lỗi khởi tạo:", err);
            return null;
        });
        return this._initPromise;
    },

    /**
     * Gắn sự kiện kéo thả / resize cột trên AG Grid
     */
    bindGridEvents: function(api) {
        if (!api || api._rh_rruns_bound) return;
        api._rh_rruns_bound = true;
        var self = this;

        if (typeof api.addEventListener === "function") {
            api.addEventListener("columnMoved", function(e) {
                if (self._suppressEvents) return;
                if (e && e.finished === false) return;
                if (e && e.source && e.source !== "uiColumnMoved" && e.source !== "uiColumnDragged") {
                    return;
                }
                self.showStatusNotification("Đã đổi vị trí cột. Bấm 'Lưu vị trí cột' để cập nhật template.");
            });

            api.addEventListener("columnResized", function(e) {
                if (self._suppressEvents) return;
                if (e && e.finished && e.source === "uiColumnDragged") {
                    self.showStatusNotification("Đã chỉnh độ rộng cột. Bấm 'Lưu vị trí cột' để lưu.");
                }
            });
        }
    },

    /**
     * Đọc thứ tự và độ rộng cột hiện tại từ AG Grid Column State
     */
    getCurrentColumnLayout: function() {
        var api = this._api;
        if (!api && window.dash_ag_grid && typeof window.dash_ag_grid.getApi === "function") {
            try {
                api = window.dash_ag_grid.getApi(this.gridId);
            } catch (e) {}
        }
        if (!api || typeof api.getColumnState !== "function") return null;

        try {
            var state = api.getColumnState() || [];
            return state.map(function(col) {
                var entry = {
                    colId: col.colId,
                    hide: !!col.hide,
                    pinned: col.pinned || null
                };
                if (col.flex != null) {
                    entry.flex = col.flex;
                }
                if (col.width != null) {
                    entry.width = Math.round(col.width);
                }
                return entry;
            }).filter(function(item) {
                return !!item.colId;
            });
        } catch (err) {
            console.warn("[reportRunsViews] Lỗi đọc columnState:", err);
            return null;
        }
    },

    /**
     * Áp dụng columnState lên AG Grid (giữ nguyên rowData và renderers)
     */
    applyLayoutDirectly: function(columnState) {
        var self = this;
        return this.getGridApi().then(function(api) {
            if (!api) return;
            self._suppressEvents = true;
            try {
                if (Array.isArray(columnState) && columnState.length > 0) {
                    api.applyColumnState({
                        state: columnState,
                        applyOrder: true
                    });
                } else {
                    api.resetColumnState();
                }
            } catch (err) {
                console.warn("[reportRunsViews] Lỗi applyColumnState:", err);
            } finally {
                setTimeout(function() {
                    self._suppressEvents = false;
                }, 120);
            }
        });
    },

    /**
     * Lấy danh sách Views từ localStorage
     */
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
                columnState: null
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

    /**
     * Lưu vị trí và độ rộng cột hiện tại vào View đang chọn
     */
    saveCurrentView: function() {
        var layout = this.getCurrentColumnLayout();
        if (!layout || layout.length === 0) return;

        var views = this.getViews();
        var activeId = this.activeViewId || "default";
        var target = views.find(function(v) { return v.id === activeId; });

        if (target) {
            target.columnState = layout;
            this.saveViews(views);
            this.showStatusNotification("Đã lưu vị trí và độ rộng cột vào View: '" + target.name + "'");
        } else {
            this.saveNewView("Template cá nhân", true);
        }
    },

    /**
     * Lưu cấu hình hiện tại thành View mới
     */
    saveNewView: function(viewName, setAsDefault) {
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
            columnState: layout
        });

        this.saveViews(views);
        this.activeViewId = newId;
        this.refreshToolbarUI(newId);
        this.showStatusNotification("Đã tạo Template mới: '" + name + "'");
    },

    /**
     * Chuyển sang một View đã lưu
     */
    applyView: function(viewId) {
        if (!viewId || viewId === this.activeViewId) return;

        this.activeViewId = viewId;
        var views = this.getViews();
        var target = views.find(function(v) { return v.id === viewId; });

        if (target) {
            this.applyLayoutDirectly(target.columnState || null);
            this.showStatusNotification("Đã chuyển sang View: '" + target.name + "'");
        }
    },

    /**
     * Đặt View hiện tại làm mặc định
     */
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

    /**
     * Xóa View cá nhân
     */
    deleteView: function(viewId) {
        if (!viewId || viewId === "default") {
            this.showStatusNotification("Không thể xóa View mặc định hệ thống.");
            return;
        }

        var views = this.getViews().filter(function(v) { return v.id !== viewId; });
        if (views.length === 0) {
            views = [
                {
                    id: "default",
                    name: "Mặc định hệ thống",
                    isDefault: true,
                    columnState: null
                }
            ];
        }
        this.saveViews(views);

        var defaultView = views.find(function(v) { return v.id === "default"; }) || views[0];
        this.activeViewId = defaultView.id;
        this.applyLayoutDirectly(defaultView.columnState || null);
        this.refreshToolbarUI(this.activeViewId);
        this.showStatusNotification("Đã xóa Template thành công.");
    },

    /**
     * Khôi phục thứ tự và độ rộng cột gốc từ columnDefs
     */
    resetToDefault: function() {
        var self = this;
        return this.getGridApi().then(function(api) {
            if (!api) return;
            self._suppressEvents = true;
            try {
                api.resetColumnState();
                self.showStatusNotification("Đã khôi phục vị trí cột mặc định.");
            } finally {
                setTimeout(function() {
                    self._suppressEvents = false;
                }, 120);
            }
        });
    },

    /**
     * Đồng bộ danh sách View lên Dropdown toolbar
     */
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
                window.dash_clientside.set_props(this.selectId, props);
            } catch (e) {}
        }
    },

    showStatusNotification: function(msg) {
        var notifyEl = document.getElementById(this.notifyId);
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
