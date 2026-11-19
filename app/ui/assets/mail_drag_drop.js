/**
 * ReconHub — Drag & Drop hỗ trợ sắp xếp component trong Mail Template Studio.
 * Sử dụng HTML5 Drag and Drop API và window.dash_clientside.set_props.
 */
(function () {
  'use strict';

  let draggedBlockId = null;
  let lastSentTs = 0;

  function sendReorderEvent(fromId, toId) {
    if (!fromId || !toId || fromId === toId) return;
    const now = Date.now();
    if (now - lastSentTs < 250) return; // Debounce
    lastSentTs = now;

    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
      try {
        window.dash_clientside.set_props('mail-studio-reorder-store', {
          data: {
            from_id: Number(fromId),
            to_id: Number(toId),
            _ts: now,
          },
        });
      } catch (err) {
        console.error('sendReorderEvent set_props error:', err);
      }
    }
  }

  function cleanup() {
    draggedBlockId = null;
    document.querySelectorAll('.mail-item-dragging').forEach(function (el) {
      el.classList.remove('mail-item-dragging');
    });
    document.querySelectorAll('.mail-item-drag-over-top, .mail-item-drag-over-bottom').forEach(function (el) {
      el.classList.remove('mail-item-drag-over-top', 'mail-item-drag-over-bottom');
    });
  }

  // Bật thuộc tính draggable trên item khi hover hoặc mousedown vào icon grip handle
  function enableDraggable(e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const handle = e.target.closest('.mail-drag-handle');
    if (handle) {
      const item = handle.closest('.mail-drag-item');
      if (item && item.getAttribute('draggable') !== 'true') {
        item.setAttribute('draggable', 'true');
      }
    }
  }

  document.addEventListener('mouseover', enableDraggable);
  document.addEventListener('mousedown', enableDraggable);

  document.addEventListener('dragstart', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const item = e.target.closest('.mail-drag-item');
    if (!item) return;

    draggedBlockId = item.getAttribute('data-block-id');
    if (e.dataTransfer) {
      e.dataTransfer.setData('text/plain', draggedBlockId || '');
      e.dataTransfer.effectAllowed = 'move';
    }
    item.classList.add('mail-item-dragging');
  });

  document.addEventListener('dragover', function (e) {
    if (!draggedBlockId || !e.target || typeof e.target.closest !== 'function') return;
    const targetItem = e.target.closest('.mail-drag-item');
    if (targetItem && targetItem.getAttribute('data-block-id') !== draggedBlockId) {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';

      // Tính vị trí chuột so với item để highlight viền trên/dưới
      const rect = targetItem.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      if (e.clientY < midY) {
        targetItem.classList.add('mail-item-drag-over-top');
        targetItem.classList.remove('mail-item-drag-over-bottom');
      } else {
        targetItem.classList.add('mail-item-drag-over-bottom');
        targetItem.classList.remove('mail-item-drag-over-top');
      }
    }
  });

  document.addEventListener('dragleave', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const targetItem = e.target.closest('.mail-drag-item');
    if (targetItem && e.relatedTarget && !targetItem.contains(e.relatedTarget)) {
      targetItem.classList.remove('mail-item-drag-over-top', 'mail-item-drag-over-bottom');
    }
  });

  document.addEventListener('drop', function (e) {
    if (!draggedBlockId || !e.target || typeof e.target.closest !== 'function') return;
    e.preventDefault();
    const targetItem = e.target.closest('.mail-drag-item');
    if (targetItem) {
      const targetBlockId = targetItem.getAttribute('data-block-id');
      if (targetBlockId && targetBlockId !== draggedBlockId) {
        sendReorderEvent(draggedBlockId, targetBlockId);
      }
    }
    cleanup();
  });

  document.addEventListener('dragend', cleanup);
})();
