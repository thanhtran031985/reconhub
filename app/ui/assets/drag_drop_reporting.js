/**
 * ReconHub — Drag & Drop hỗ trợ sắp xếp động cho Tham số và Cột Báo cáo.
 * Chuẩn Fluent Compact theo Screen16 preview.html.
 */
(function () {
  'use strict';

  let draggedItem = null;
  let dragType = null; // 'param' | 'col'
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
      const parent = handle.closest('.rh-drag-col, .rh-drag-param, .param-box');
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
    const colRow = e.target.closest('.rh-drag-col');

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

    if (colRow) {
      draggedItem = colRow;
      dragType = 'col';
      if (e.dataTransfer) {
        e.dataTransfer.setData('text/plain', colRow.getAttribute('data-col-id') || '');
        e.dataTransfer.effectAllowed = 'move';
      }
      colRow.classList.add('rh-dragging');
      return;
    }
  });

  document.addEventListener('dragover', function (e) {
    if (!draggedItem || !e.target || typeof e.target.closest !== 'function') return;
    const targetParam = e.target.closest('.rh-drag-param');
    const targetRow = e.target.closest('.param-row-layout');
    const targetCol = e.target.closest('.rh-drag-col');

    if ((dragType === 'param' && (targetParam || targetRow)) || (dragType === 'col' && targetCol)) {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
    }
  });

  document.addEventListener('dragenter', function (e) {
    if (!draggedItem || !e.target || typeof e.target.closest !== 'function') return;
    const target = dragType === 'param' ? e.target.closest('.rh-drag-param') : e.target.closest('.rh-drag-col');
    if (target && target !== draggedItem) {
      target.classList.add('rh-drag-over');
    }
  });

  document.addEventListener('dragleave', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const target = dragType === 'param' ? e.target.closest('.rh-drag-param') : e.target.closest('.rh-drag-col');
    if (target && e.relatedTarget && !target.contains(e.relatedTarget)) {
      target.classList.remove('rh-drag-over');
    }
  });

  document.addEventListener('drop', function (e) {
    if (!draggedItem || !e.target || typeof e.target.closest !== 'function') return;
    e.preventDefault();

    if (dragType === 'col') {
      const targetCol = e.target.closest('.rh-drag-col');
      if (targetCol && targetCol !== draggedItem) {
        targetCol.classList.remove('rh-drag-over');
        const fromId = draggedItem.getAttribute('data-col-id');
        const toId = targetCol.getAttribute('data-col-id');

        // Di chuyển vị trí dòng ngay trên DOM để phản hồi lập tức và mượt mà
        const parent = targetCol.parentNode;
        if (parent) {
          const rows = Array.from(parent.children);
          const fromIdx = rows.indexOf(draggedItem);
          const toIdx = rows.indexOf(targetCol);
          if (fromIdx >= 0 && toIdx >= 0) {
            if (fromIdx < toIdx) {
              parent.insertBefore(draggedItem, targetCol.nextSibling);
            } else {
              parent.insertBefore(draggedItem, targetCol);
            }
          }
        }

        if (fromId && toId && fromId !== toId) {
          sendDropEvent({ type: 'col', from_id: fromId, to_id: toId });
        }
      }
    } else if (dragType === 'param') {
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

  // Xóa trực tiếp dòng trên DOM khi người dùng bấm nút xóa (mượt mà 0ms không giật lag)
  document.addEventListener('click', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const delBtn = e.target.closest('.rh-btn-del, [id*="admin-col-del"]');
    if (delBtn) {
      const row = delBtn.closest('.rh-drag-col');
      if (row) {
        row.style.opacity = '0.2';
        row.style.pointerEvents = 'none';
        setTimeout(function () {
          if (row.parentNode) row.parentNode.removeChild(row);
        }, 120);
      }
    }
  });

  // Sắp xếp lại thứ tự DOM ngay lập tức khi bấm Khôi phục thứ tự DB (0ms không lag)
  document.addEventListener('click', function (e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    const restoreBtn = e.target.closest('#admin-col-restore-btn');
    if (restoreBtn) {
      const tbody = document.getElementById('admin-col-tbody');
      if (tbody) {
        const rows = Array.from(tbody.querySelectorAll('tr.rh-drag-col'));
        rows.sort(function (a, b) {
          return (Number(a.getAttribute('data-col-id')) || 0) - (Number(b.getAttribute('data-col-id')) || 0);
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      }
    }
  });

  // Lọc tìm kiếm trực tiếp trên bảng Cấu hình cột theo trường DB (tức thời 0ms)
  document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'admin-col-search') {
      const q = (e.target.value || '').trim().toUpperCase();
      const rows = document.querySelectorAll('.rh-drag-col');
      rows.forEach(function (r) {
        const fieldName = (r.getAttribute('data-field-name') || r.innerText || '').toUpperCase();
        if (!q || fieldName.indexOf(q) >= 0) {
          r.style.display = '';
        } else {
          r.style.display = 'none';
        }
      });
    }
  });
})();
