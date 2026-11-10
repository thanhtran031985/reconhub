/**
 * ReconHub — Drag & Drop hỗ trợ sắp xếp động cho Tham số.
 * Chuẩn Fluent Compact theo Screen16 preview.html.
 *
 * Task 35: phần kéo-thả Cột đã bỏ — grid cột bước 4 dùng AG Grid
 * (rowDrag có sẵn), thứ tự cột lưu chung khi bấm "Lưu cột".
 */
(function () {
  'use strict';

  let draggedItem = null;
  let dragType = null; // 'param'
  let lastSentTs = 0;

  function sendDropEvent(payload) {
    if (!payload || !payload.from_id) return;
    const now = Date.now();
    if (now - lastSentTs < 250) return; // Tránh gửi đúp
    lastSentTs = now;
    payload._ts = now;

    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
      try {
        window.dash_clientside.set_props('admin-drag-drop-store', { data: payload });
      } catch (err) {
        console.error('sendDropEvent set_props error:', err);
      }
    }
  }

  function cleanup() {
    if (draggedItem) {
      draggedItem.classList.remove('rh-dragging');
      draggedItem = null;
    }
    dragType = null;
    document.querySelectorAll('.rh-drag-over').forEach(function (el) {
      el.classList.remove('rh-drag-over');
    });
  }

  // Bật thuộc tính draggable khi di chuột hoặc bấm chuột vào icon kéo thả
  function enableDraggable(e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const handle = e.target.closest('.rh-drag-handle, .grab');
    if (handle) {
      const parent = handle.closest('.rh-drag-param, .param-box');
      if (parent && parent.getAttribute('draggable') !== 'true') {
        parent.setAttribute('draggable', 'true');
      }
    }
  }

  document.addEventListener('mouseover', enableDraggable);
  document.addEventListener('mousedown', enableDraggable);

  document.addEventListener('dragstart', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    // Không kích hoạt kéo khi người dùng đang nhập vào input/select/button
    const targetTag = (e.target.tagName || '').toUpperCase();
    if (targetTag === 'INPUT' || targetTag === 'SELECT' || targetTag === 'TEXTAREA' || targetTag === 'BUTTON') {
      return;
    }
    const paramBox = e.target.closest('.rh-drag-param');

    if (paramBox) {
      draggedItem = paramBox;
      dragType = 'param';
      if (e.dataTransfer) {
        e.dataTransfer.setData('text/plain', paramBox.getAttribute('data-param-id') || '');
        e.dataTransfer.effectAllowed = 'move';
      }
      paramBox.classList.add('rh-dragging');
      return;
    }
  });

  document.addEventListener('dragover', function (e) {
    if (!draggedItem || !e.target || typeof e.target.closest !== 'function') return;
    const targetParam = e.target.closest('.rh-drag-param');
    const targetRow = e.target.closest('.param-row-layout');

    if (dragType === 'param' && (targetParam || targetRow)) {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
    }
  });

  document.addEventListener('dragenter', function (e) {
    if (!draggedItem || !e.target || typeof e.target.closest !== 'function') return;
    const target = e.target.closest('.rh-drag-param');
    if (target && target !== draggedItem) {
      target.classList.add('rh-drag-over');
    }
  });

  document.addEventListener('dragleave', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const target = e.target.closest('.rh-drag-param');
    if (target && e.relatedTarget && !target.contains(e.relatedTarget)) {
      target.classList.remove('rh-drag-over');
    }
  });

  document.addEventListener('drop', function (e) {
    if (!draggedItem || !e.target || typeof e.target.closest !== 'function') return;
    e.preventDefault();

    if (dragType === 'param') {
      const targetParam = e.target.closest('.rh-drag-param');
      const targetRow = e.target.closest('.param-row-layout');

      if (targetParam && targetParam !== draggedItem) {
        targetParam.classList.remove('rh-drag-over');
        const fromId = draggedItem.getAttribute('data-param-id');
        const rowEl = targetParam.closest('.param-row-layout');
        const toRow = rowEl ? rowEl.getAttribute('data-layout-row') : 1;
        const siblings = Array.from((targetParam.parentElement || targetParam).querySelectorAll('.rh-drag-param'));
        const toIdx = siblings.indexOf(targetParam);
        if (fromId) {
          sendDropEvent({ type: 'param', from_id: fromId, to_row: Number(toRow) || 1, to_index: toIdx >= 0 ? toIdx : 0 });
        }
      } else if (targetRow && !targetParam) {
        const fromId = draggedItem.getAttribute('data-param-id');
        const toRow = targetRow.getAttribute('data-layout-row') || 1;
        if (fromId) {
          sendDropEvent({ type: 'param', from_id: fromId, to_row: Number(toRow) || 1, to_index: 999 });
        }
      }
    }

    cleanup();
  });

  document.addEventListener('dragend', cleanup);
})();
