/**
 * ReconHub — Data Model Explorer canvas (task 31 bước 4–5).
 * Dash không có sự kiện dblclick native nên bắt dblclick ở tầng document
 * rồi đẩy tên table vào store qua window.dash_clientside.set_props
 * (theo mẫu menu_search_keys.js). Server callback đọc store để chọn table,
 * center canvas và zoom đủ đọc columns.
 */
(function () {
  'use strict';

  var STORE_ID = 'data-model-dblclick-store';

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
})();
