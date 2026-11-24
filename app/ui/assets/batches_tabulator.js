/**
 * ReconHub - Tabulator Controller cho Màn hình Bộ đối soát (/batches)
 * Phong cách Fluent Compact + Oracle APEX Interactive Grid
 */

window.batchesTabulator = {
    table: null,
    storageKey: "reconhub_batches_views",
    baseColumnDefs: null,
    activeViewId: "default",
    resizeObserver: null,

    /**
     * Khởi tạo bảng Tabulator
     */
    init: function(containerId, rowData, canWrite) {
        var container = document.getElementById(containerId);
        if (!container) return;

        if (typeof Tabulator === "undefined") {
            console.error("[batchesTabulator] Thư viện Tabulator chưa sẵn sàng.");
            return;
        }

        var self = this;

        // Dọn dẹp cache persistence cũ của Tabulator nếu có
        try {
            localStorage.removeItem("tabulator-reconhub_bdef_tbl-columns");
        } catch (e) {}

        // Hàm tiện ích tạo input text cho header filter (chống nổi bọt mousedown lên header)
        function createHeaderInputFilter(placeholder) {
            return function(cell, onRendered, success, cancel, editorParams) {
                var input = document.createElement("input");
                input.type = "text";
                input.placeholder = placeholder || "Tìm...";
                input.className = "tab-fluent-filter-input";
                
                // Ngăn nổi bọt để không kích hoạt kéo thả cột khi click gõ tìm kiếm
                input.addEventListener("mousedown", function(e) { e.stopPropagation(); });
                input.addEventListener("click", function(e) { e.stopPropagation(); });
                input.addEventListener("keydown", function(e) { e.stopPropagation(); });

                input.addEventListener("input", function() {
                    success(input.value);
                });
                return input;
            };
        }

        // Cấu hình các cột gốc (Base Column Definitions)
        // Lưu ý: minWidth để nhỏ (60px - 80px) để người dùng có thể tự do kéo giảm chiều rộng
        this.baseColumnDefs = [
            {
                title: "Mã bộ",
                field: "code",
                width: 160,
                minWidth: 80,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc mã..."),
                headerSort: true,
                formatter: function(cell) {
                    var val = cell.getValue() || "";
                    var data = cell.getData();
                    var id = data.id || "";
                    return '<a href="/batches/' + id + '" class="rh-code tab-cell-code">' + val + '</a>';
                }
            },
            {
                title: "Tên bộ đối soát",
                field: "name",
                minWidth: 80,               // 🟢 Không hardcode minWidth lớn, cho phép kéo giảm thoải mái
                widthGrow: 3,
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Lọc tên..."),
                headerSort: true,
                formatter: function(cell) {
                    var val = cell.getValue() || "";
                    var desc = cell.getData().description || "";
                    if (!desc) {
                        return '<span class="tab-cell-name">' + val + '</span>';
                    }
                    return '<div class="tab-cell-name-box"><div class="tab-cell-name">' + val + '</div><div class="tab-cell-desc">' + desc + '</div></div>';
                }
            },
            {
                title: "Trạng thái",
                field: "status",
                width: 130,
                minWidth: 80,
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
                    var val = cell.getValue() || "DRAFT";
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
                title: "Số mục",
                field: "cnt_items",
                width: 85,
                minWidth: 60,
                hozAlign: "center",
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Số..."),
                headerSort: true
            },
            {
                title: "Song song/DS",
                field: "max_parallel_per_ds",
                width: 110,
                minWidth: 70,
                hozAlign: "center",
                headerHozAlign: "center",
                headerFilter: createHeaderInputFilter("Số..."),
                headerSort: true
            },
            {
                title: "Thao tác",
                field: "actions",
                width: 80,
                minWidth: 80,
                hozAlign: "center",
                headerHozAlign: "center",
                headerSort: false,
                resizable: false,
                formatter: function(cell) {
                    var id = cell.getData().id || "";
                    return '<a href="/batches/' + id + '" class="tab-icon-btn" title="Mở chi tiết bộ đối soát" aria-label="Mở chi tiết">' +
                           '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                           '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>' +
                           '<polyline points="15 3 21 3 21 9"></polyline>' +
                           '<line x1="10" y1="14" x2="21" y2="3"></line>' +
                           '</svg>' +
                           '</a>';
                }
            }
        ];

        // Dọn dẹp DOM và instance cũ
        if (this.table) {
            try {
                this.table.destroy();
            } catch (e) {}
            this.table = null;
        }
        container.innerHTML = "";

        // Clone column definitions ban đầu
        var initialColumns = this.baseColumnDefs.slice();

        // Khởi tạo Tabulator instance mới (chuẩn Tabulator v6)
        this.table = new Tabulator("#" + containerId, {
            data: rowData || [],
            columns: initialColumns,
            layout: "fitColumns",
            movableColumns: true,            // Kéo thả thay đổi vị trí cột
            resizableColumnFit: true,        // 🟢 Cho phép resize cột co dãn tự nhiên lấp đầy 100%
            resizableColumnGuide: true,      // Đường chỉ dẫn khi kéo resize
            headerFilterLiveFilter: true,    // Lọc tức thì khi gõ vào header
            placeholder: "Không có dữ liệu phù hợp",
            pagination: true,
            paginationSize: 20,
            paginationSizeSelector: [10, 20, 50, 100],
            persistence: false
        });

        // Bắt sự kiện bảng đã render hoàn tất
        this.table.on("tableBuilt", function() {
            try {
                var views = self.getViews();
                var defaultView = views.find(function(v) { return v.isDefault; }) || views[0];
                if (defaultView && defaultView.layout) {
                    self.activeViewId = defaultView.id;
                    self.applyLayoutDirectly(defaultView.layout);
                }
                self.refreshToolbarUI(self.activeViewId);

                // Lắng nghe ResizeObserver trên container
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

                // Lắng nghe sự kiện click nút Toggle Sidebar (thu nhỏ / mở rộng menu)
                var toggleBtn = document.getElementById("app-sidebar-toggle-btn");
                if (toggleBtn && !toggleBtn._rh_tab_bound) {
                    toggleBtn._rh_tab_bound = true;
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
                console.warn("[batchesTabulator] Lỗi tableBuilt:", err);
            }
        });

        // Bắt sự kiện chuyển vị trí cột
        this.table.on("columnMoved", function(col, allColumns) {
            try {
                var fieldName = col && typeof col.getField === "function" ? col.getField() : "";
                console.log("[batchesTabulator] Đã chuyển vị trí cột:", fieldName);
                self.showStatusNotification("Đã đổi vị trí cột. Bấm 'Lưu vị trí cột' để cập nhật template.");
            } catch (err) {
                console.warn("[batchesTabulator] Lỗi columnMoved:", err);
            }
        });

        // Bắt sự kiện thay đổi độ rộng cột (resize)
        this.table.on("columnResized", function(col) {
            try {
                var fieldName = col && typeof col.getField === "function" ? col.getField() : "";
                var newWidth = Math.round(col.getWidth());
                console.log("[batchesTabulator] Đã chỉnh độ rộng cột " + fieldName + ": " + newWidth + "px");
                self.showStatusNotification("Đã chỉnh độ rộng cột. Bấm 'Lưu vị trí cột' để lưu.");
            } catch (err) {
                console.warn("[batchesTabulator] Lỗi columnResized:", err);
            }
        });
    },

    /**
     * Lấy layout hiện tại (cả thứ tự cột và độ rộng từng cột)
     */
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

    /**
     * Áp dụng layout: khôi phục đúng vị trí và độ rộng cột, đồng thời giữ cột 'name' tự do dãn 100%
     */
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
                            // 🟢 Cột 'name': giữ minWidth nhỏ (80px), TUYỆT ĐỐI không gán col.minWidth = it.width
                            // để người dùng có thể tự do kéo giảm chiều rộng bất kỳ lúc nào.
                            col.minWidth = 80;
                            delete col.width;
                            col.widthGrow = 3;
                        } else {
                            // Các cột khác: khôi phục đúng pixel độ rộng người dùng đã lưu
                            if (it.width && it.width > 30) {
                                col.width = it.width;
                            }
                        }
                        reordered.push(col);
                        delete colMap[f];
                    }
                });

                // Thêm các cột còn lại nếu chưa có
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
            console.warn("[batchesTabulator] Layout setColumns error:", err);
        }
    },

    /**
     * Lấy danh sách Views / Templates từ localStorage
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
                layout: [
                    { field: "code", width: 160 },
                    { field: "name", width: null },
                    { field: "status", width: 130 },
                    { field: "cnt_items", width: 85 },
                    { field: "max_parallel_per_ds", width: 110 },
                    { field: "actions", width: 80 }
                ]
            }
        ];
        this.saveViews(initViews);
        return initViews;
    },

    /**
     * Lưu danh sách Views vào localStorage
     */
    saveViews: function(views) {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(views));
        } catch (e) {}
    },

    /**
     * Lưu vị trí và độ rộng cột hiện tại vào View đang chọn
     */
    saveCurrentView: function() {
        if (!this.table) return;
        var layout = this.getCurrentColumnLayout();
        if (!layout || layout.length === 0) return;

        var views = this.getViews();
        var activeId = this.activeViewId;

        var target = views.find(function(v) { return v.id === activeId; });
        if (target) {
            target.layout = layout;
            this.saveViews(views);
            this.showStatusNotification("Đã lưu vị trí và độ rộng cột vào View: '" + target.name + "'");
        } else {
            this.saveNewView("Template cá nhân", true);
        }
    },

    /**
     * Lưu cấu hình hiện tại thành một View / Template mới (được gọi từ Modal Mantine)
     */
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
            layout: layout || [
                { field: "code", width: 160 },
                { field: "name", width: null },
                { field: "status", width: 130 },
                { field: "cnt_items", width: 85 },
                { field: "max_parallel_per_ds", width: 110 },
                { field: "actions", width: 80 }
            ]
        });

        this.saveViews(views);
        this.activeViewId = newId;
        this.refreshToolbarUI(newId);
        this.showStatusNotification("Đã tạo Template mới: '" + name + "'");
    },

    /**
     * Nạp một View theo ID
     */
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

    /**
     * Đặt View hiện tại làm mặc định
     */
    setDefaultView: function(viewId) {
        var views = this.getViews();
        views.forEach(function(v) {
            v.isDefault = (v.id === viewId);
        });
        this.saveViews(views);
        this.refreshToolbarUI(viewId);
        this.showStatusNotification("Đã đặt View làm mặc định khi mở trang.");
    },

    /**
     * Xóa một View (gọi trực tiếp sau khi xác nhận trên Modal Mantine, không dùng confirm/alert JS)
     */
    deleteView: function(viewId) {
        if (!viewId || viewId === "default") {
            this.showStatusNotification("Không thể xóa View mặc định hệ thống.");
            return;
        }

        var views = this.getViews().filter(function(v) { return v.id !== viewId; });
        this.saveViews(views);
        this.activeViewId = "default";
        var defaultView = views.find(function(v) { return v.id === "default"; });
        if (defaultView && defaultView.layout) {
            this.applyLayoutDirectly(defaultView.layout);
        }
        this.refreshToolbarUI("default");
        this.showStatusNotification("Đã xóa Template thành công.");
    },

    /**
     * Khôi phục layout mặc định ban đầu
     */
    resetToDefault: function() {
        if (this.table && this.baseColumnDefs) {
            var defaultLayout = [
                { field: "code", width: 160 },
                { field: "name", width: null },
                { field: "status", width: 130 },
                { field: "cnt_items", width: 85 },
                { field: "max_parallel_per_ds", width: 110 },
                { field: "actions", width: 80 }
            ];
            this.applyLayoutDirectly(defaultLayout);
            this.showStatusNotification("Đã khôi phục vị trí cột mặc định.");
        }
    },

    /**
     * Cập nhật danh sách options lên thanh Toolbar
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
                window.dash_clientside.set_props("batches-view-select", props);
            } catch (e) {}
        }
    },

    /**
     * Hiển thị thông báo nhỏ trên toolbar
     */
    showStatusNotification: function(msg) {
        var notifyEl = document.getElementById("batches-grid-notification");
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
