/**
 * ReconHub — Data Model Explorer canvas (task 31 bước 4–5, bổ sung sau review 2026-11-10).
 * Dash không có sự kiện dblclick native nên bắt dblclick ở tầng document
 * rồi đẩy tên table vào store qua window.dash_clientside.set_props
 * (theo mẫu menu_search_keys.js). Server callback đọc store để chọn table,
 * center canvas và zoom đủ đọc columns.
 *
 * Click vào vùng trống của canvas (trong #data-model-canvas-container nhưng
 * không trúng entity hay relationship line) thì xóa selection store để
 * canvas trở lại bình thường, Detail Panel về empty state.
 */
(function () {
  'use strict';

  var STORE_ID = 'data-model-dblclick-store';
  var SELECTION_STORE_ID = 'data-model-selection-store';

  document.addEventListener(
    'dblclick',
    function (e) {
      var target = e.target;
      if (!target || typeof target.closest !== 'function') return;
      var entity = target.closest('.dm-entity');
      if (!entity) return;
      var table = entity.getAttribute('data-table');
      if (!table) return;
      if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
        try {
          window.dash_clientside.set_props(STORE_ID, { data: { table: table, ts: Date.now() } });
        } catch (err) {
          console.error('data-model dblclick set_props error:', err);
        }
      }
    },
    true
  );

  document.addEventListener(
    'click',
    function (e) {
      var target = e.target;
      if (!target || typeof target.closest !== 'function') return;
      // Chỉ xử lý click trong khung cuộn của canvas (nút zoom/fit ở header
      // nằm ngoài container nên không bị ảnh hưởng).
      if (!target.closest('#data-model-canvas-container')) return;
      if (target.closest('.dm-entity') || target.closest('.dm-rel-line')) return;
      if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
        try {
          window.dash_clientside.set_props(SELECTION_STORE_ID, { data: null });
        } catch (err) {
          console.error('data-model click-outside set_props error:', err);
        }
      }
    },
    true
  );
})();
