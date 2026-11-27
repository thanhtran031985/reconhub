/**
 * ReconHub — Drag & Drop cho Report Studio Designer (Task 109 Bước 4).
 * Sử dụng HTML5 Drag and Drop API thuần và window.dash_clientside.set_props,
 * theo mẫu mail_drag_drop.js / drag_drop_reporting.js.
 *
 * - Kéo field/measure ở panel trái (.rs-field-row) thả vào Data Well
 *   (.rs-well-drop) -> gửi {kind: 'field-drop', ...} vào 'rs-dnd-store'.
 * - Kéo card visual trên canvas (.rs-visual-card, qua tay cầm
 *   .rs-drag-handle) thả lên card khác -> gửi {kind: 'visual-reorder', ...}.
 * - Theo dõi data-mantine-color-scheme (toggle sáng/tối của app) và ghi
 *   vào 'rs-dark-mode-store' để biểu đồ Plotly đổi palette kịp thời.
 */
(function () {
  'use strict';

  var draggedField = null; // {kind, id}
  var draggedVisual = null; // code
  var lastSentTs = 0;

  function sendDndEvent(payload) {
    if (!payload) return;
    var now = Date.now();
    if (now - lastSentTs < 250) return; // Debounce
    lastSentTs = now;
    payload._ts = now;

    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
      try {
        window.dash_clientside.set_props('rs-dnd-store', { data: payload });
      } catch (err) {
        console.error('studio_drag_drop set_props error:', err);
      }
    }
  }

  function sendDarkMode() {
    var scheme = 'light';
    try {
      scheme = document.documentElement.getAttribute('data-mantine-color-scheme') || 'light';
    } catch (err) {
      scheme = 'light';
    }
    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
      try {
        window.dash_clientside.set_props('rs-dark-mode-store', { data: scheme === 'dark' });
      } catch (err) {
        // Store chưa mount (không ở trang designer) -> bỏ qua.
      }
      // Task 109 Bước 5: Viewer dùng chung observer này để chart đổi
      // palette kịp thời khi đổi theme.
      try {
        window.dash_clientside.set_props('viewer-dark-mode-store', { data: scheme === 'dark' });
      } catch (err) {
        // Store chưa mount (không ở trang viewer) -> bỏ qua.
      }
    }
  }

  function cleanup() {
    draggedField = null;
    draggedVisual = null;
    document.querySelectorAll('.rs-dragging').forEach(function (el) {
      el.classList.remove('rs-dragging');
    });
    document.querySelectorAll('.rs-drag-over').forEach(function (el) {
      el.classList.remove('rs-drag-over');
    });
  }

  // Bật draggable khi di chuột/bấm vào tay cầm kéo.
  function enableDraggable(e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    var handle = e.target.closest('.rs-drag-handle');
    if (!handle) return;
    var fieldRow = handle.closest('.rs-field-row');
    if (fieldRow && fieldRow.getAttribute('draggable') !== 'true') {
      fieldRow.setAttribute('draggable', 'true');
    }
    var card = handle.closest('.rs-visual-card');
    if (card && card.getAttribute('draggable') !== 'true') {
      card.setAttribute('draggable', 'true');
    }
  }

  document.addEventListener('mouseover', enableDraggable);
  document.addEventListener('mousedown', enableDraggable);

  document.addEventListener('dragstart', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    var fieldRow = e.target.closest('.rs-field-row');
    if (fieldRow) {
      draggedField = {
        kind: fieldRow.getAttribute('data-kind') || 'field',
        id: fieldRow.getAttribute('data-field-id') || '',
      };
      if (e.dataTransfer) {
        e.dataTransfer.setData('text/plain', 'field:' + draggedField.kind + ':' + draggedField.id);
        e.dataTransfer.effectAllowed = 'copy';
      }
      fieldRow.classList.add('rs-dragging');
      return;
    }
    var card = e.target.closest('.rs-visual-card');
    if (card) {
      draggedVisual = card.getAttribute('data-visual-code') || '';
      if (e.dataTransfer) {
        e.dataTransfer.setData('text/plain', 'visual:' + draggedVisual);
        e.dataTransfer.effectAllowed = 'move';
      }
      card.classList.add('rs-dragging');
    }
  });

  document.addEventListener('dragover', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    var well = e.target.closest('.rs-well-drop');
    if (well && draggedField) {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
      well.classList.add('rs-drag-over');
      return;
    }
    var card = e.target.closest('.rs-visual-card');
    if (card && draggedVisual && card.getAttribute('data-visual-code') !== draggedVisual) {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
      card.classList.add('rs-drag-over');
    }
  });

  document.addEventListener('dragleave', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    var well = e.target.closest('.rs-well-drop');
    if (well) well.classList.remove('rs-drag-over');
    var card = e.target.closest('.rs-visual-card');
    if (card) card.classList.remove('rs-drag-over');
  });

  document.addEventListener('drop', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    var well = e.target.closest('.rs-well-drop');
    if (well && draggedField) {
      e.preventDefault();
      sendDndEvent({
        kind: 'field-drop',
        field_kind: draggedField.kind,
        field_id: Number(draggedField.id),
        visual_code: well.getAttribute('data-visual-code') || '',
        well_role: well.getAttribute('data-well-role') || '',
      });
      cleanup();
      return;
    }
    var card = e.target.closest('.rs-visual-card');
    if (card && draggedVisual) {
      e.preventDefault();
      sendDndEvent({
        kind: 'visual-reorder',
        from_code: draggedVisual,
        to_code: card.getAttribute('data-visual-code') || '',
      });
      cleanup();
    }
  });

  document.addEventListener('dragend', cleanup);

  // Đồng bộ chế độ sáng/tối cho biểu đồ Plotly.
  sendDarkMode();
  if (typeof MutationObserver !== 'undefined') {
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        if (mutations[i].attributeName === 'data-mantine-color-scheme') {
          sendDarkMode();
          break;
        }
      }
    });
    observer.observe(document.documentElement, { attributes: true });
  }
})();
