/**
 * ReconHub — Semantic Model Studio Canvas Clientside Interactions (Task 107 Bước 3).
 *
 * Dùng Vanilla Pointer Events + SVG DOM + window.dash_clientside.set_props
 * để đảm bảo 60fps không reload server khi kéo thả card hoặc nối cột-tới-cột:
 * - Vẽ SVG bezier đường quan hệ trên #rms-rel-svg-layer (tự cập nhật từng frame khi kéo)
 * - Kéo thả card (.rms-entity-header[data-drag-handle]) -> rms-drag-pos-store
 * - Kéo thả điểm nối (.rms-port-dot) từ cột nguồn sang cột đích -> rms-connect-draft-store
 * - Click card / cột / đường quan hệ / vùng trống -> rms-canvas-click-store
 * - Double-click card -> rms-canvas-dblclick-store
 * - Kéo vùng trống để pan canvas
 */
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var CONTAINER_ID = 'rm-canvas-container';
  var INNER_ID = 'rm-canvas-inner';
  var SVG_HOST_ID = 'rms-rel-svg-layer';

  function setProps(id, props) {
    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
      try {
        window.dash_clientside.set_props(id, props);
      } catch (err) {
        console.error('semantic_model_canvas set_props error:', id, err);
      }
    }
  }

  function getZoom(inner) {
    if (!inner) return 1;
    var z = parseFloat(inner.getAttribute('data-zoom') || '1');
    return isNaN(z) || z <= 0 ? 1 : z;
  }

  function clientToCanvas(container, inner, clientX, clientY) {
    var rect = inner.getBoundingClientRect();
    var z = getZoom(inner);
    return {
      x: (clientX - rect.left) / z,
      y: (clientY - rect.top) / z,
    };
  }

  function getCardBox(inner, tableId) {
    var el = inner.querySelector('.rms-entity-card[data-table-id="' + tableId + '"]');
    if (!el) return null;
    return {
      el: el,
      x: parseFloat(el.style.left || '0') || 0,
      y: parseFloat(el.style.top || '0') || 0,
      w: el.offsetWidth || 252,
      h: el.offsetHeight || 120,
    };
  }

  function getColumnCenterY(inner, box, tableId, colName) {
    var cols = box.el.querySelectorAll('.rms-entity-col');
    var targetUpper = String(colName || '').toUpperCase();
    for (var i = 0; i < cols.length; i++) {
      var c = cols[i];
      if (String(c.getAttribute('data-column') || '').toUpperCase() === targetUpper) {
        return box.y + c.offsetTop + (c.offsetHeight / 2);
      }
    }
    return box.y + Math.min(box.h - 14, 48);
  }

  function buildPathFromBoxes(srcBox, dstBox, y1, y2) {
    var srcCx = srcBox.x + srcBox.w / 2;
    var dstCx = dstBox.x + dstBox.w / 2;
    var x1, x2, dir;
    if (dstCx >= srcCx) {
      x1 = srcBox.x + srcBox.w;
      x2 = dstBox.x;
      dir = 1;
    } else {
      x1 = srcBox.x;
      x2 = dstBox.x + dstBox.w;
      dir = -1;
    }
    var curve = Math.max(48, Math.abs(x2 - x1) / 2);
    var cx1 = x1 + dir * curve;
    var cx2 = x2 - dir * curve;
    return {
      d: 'M ' + x1 + ' ' + y1 + ' C ' + cx1 + ' ' + y1 + ', ' + cx2 + ' ' + y2 + ', ' + x2 + ' ' + y2,
      midX: Math.round((x1 + x2) / 2),
      midY: Math.round((y1 + y2) / 2),
    };
  }

  function renderSvgLayer() {
    var host = document.getElementById(SVG_HOST_ID);
    var inner = document.getElementById(INNER_ID);
    if (!host || !inner) return;
    var relsJson = host.getAttribute('data-rels');
    var w = parseInt(host.getAttribute('data-width') || '1120', 10);
    var h = parseInt(host.getAttribute('data-height') || '680', 10);
    var rels = [];
    try {
      rels = relsJson ? JSON.parse(relsJson) : [];
    } catch (_e) {
      rels = [];
    }

    var svg = host.querySelector('svg');
    if (!svg) {
      svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('class', 'rms-rel-svg-el');
      host.innerHTML = '';
      host.appendChild(svg);
    }
    svg.setAttribute('width', String(w));
    svg.setAttribute('height', String(h));
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    rels.forEach(function (rel) {
      var sb = getCardBox(inner, rel.from_table_id);
      var db = getCardBox(inner, rel.to_table_id);
      var pathD = rel.path_d;
      var midX = rel.mid_x;
      var midY = rel.mid_y;
      if (sb && db) {
        var y1 = getColumnCenterY(inner, sb, rel.from_table_id, rel.from_column);
        var y2 = getColumnCenterY(inner, db, rel.to_table_id, rel.to_column);
        var geom = buildPathFromBoxes(sb, db, y1, y2);
        pathD = geom.d;
        midX = geom.midX;
        midY = geom.midY;
      }

      var chip = inner.querySelector('.rms-rel-chip[data-rel-id="' + rel.id + '"]');
      if (chip) {
        chip.style.left = Math.max(4, midX - 18) + 'px';
        chip.style.top = Math.max(4, midY - 11) + 'px';
      }

      var g = document.createElementNS(NS, 'g');
      var visPath = document.createElementNS(NS, 'path');
      visPath.setAttribute('d', pathD);
      visPath.setAttribute('fill', 'none');
      visPath.setAttribute('class', 'rms-svg-path ' + (rel.state_cls || 'normal'));
      if (!rel.is_active) {
        visPath.setAttribute('stroke-dasharray', '5,4');
      }

      var hitPath = document.createElementNS(NS, 'path');
      hitPath.setAttribute('d', pathD);
      hitPath.setAttribute('fill', 'none');
      hitPath.setAttribute('stroke', 'transparent');
      hitPath.setAttribute('stroke-width', '14');
      hitPath.setAttribute('class', 'rms-rel-hit');
      hitPath.setAttribute('data-rel-id', String(rel.id));

      g.appendChild(visPath);
      g.appendChild(hitPath);
      svg.appendChild(g);
    });

    var tempPath = document.createElementNS(NS, 'path');
    tempPath.setAttribute('id', 'rms-drag-temp-path');
    tempPath.setAttribute('fill', 'none');
    tempPath.setAttribute('class', 'rms-svg-path temp');
    tempPath.setAttribute('stroke-dasharray', '6,4');
    tempPath.style.display = 'none';
    svg.appendChild(tempPath);
  }

  var mode = null; // 'card' | 'connect' | 'pan' | null
  var dragState = {};
  var suppressClick = false;

  document.addEventListener('pointerdown', function (e) {
    if (e.button !== 0 && e.button !== 1) return;
    var container = document.getElementById(CONTAINER_ID);
    var inner = document.getElementById(INNER_ID);
    if (!container || !inner || !container.contains(e.target)) return;

    var portDot = e.target.closest('.rms-port-dot');
    if (portDot && e.button === 0) {
      e.preventDefault();
      var srcTid = parseInt(portDot.getAttribute('data-table-id') || '0', 10);
      var srcCol = portDot.getAttribute('data-column') || '';
      var pt = clientToCanvas(container, inner, e.clientX, e.clientY);
      mode = 'connect';
      suppressClick = false;
      dragState = {
        srcTid: srcTid,
        srcCol: srcCol,
        startX: pt.x,
        startY: pt.y,
        rawX: e.clientX,
        rawY: e.clientY,
      };
      return;
    }

    var handle = e.target.closest('.rms-entity-header[data-drag-handle]');
    if (handle && e.button === 0) {
      e.preventDefault();
      var card = handle.closest('.rms-entity-card');
      if (!card) return;
      mode = 'card';
      suppressClick = false;
      dragState = {
        card: card,
        tableId: parseInt(card.getAttribute('data-table-id') || '0', 10),
        origLeft: parseFloat(card.style.left || '0') || 0,
        origTop: parseFloat(card.style.top || '0') || 0,
        startX: e.clientX,
        startY: e.clientY,
        zoom: getZoom(inner),
      };
      return;
    }

    if (!e.target.closest('.rms-entity-card') && !e.target.closest('.rms-rel-chip') && !e.target.closest('.rms-rel-hit')) {
      mode = 'pan';
      suppressClick = false;
      dragState = {
        container: container,
        startX: e.clientX,
        startY: e.clientY,
        scrollLeft: container.scrollLeft,
        scrollTop: container.scrollTop,
      };
    }
  });

  document.addEventListener('pointermove', function (e) {
    if (!mode) return;
    var container = document.getElementById(CONTAINER_ID);
    var inner = document.getElementById(INNER_ID);
    if (!container || !inner) return;

    if (mode === 'card' && dragState.card) {
      var dxRaw = e.clientX - dragState.startX;
      var dyRaw = e.clientY - dragState.startY;
      if (Math.abs(dxRaw) > 3 || Math.abs(dyRaw) > 3) suppressClick = true;
      var nx = Math.max(16, Math.round(dragState.origLeft + dxRaw / dragState.zoom));
      var ny = Math.max(16, Math.round(dragState.origTop + dyRaw / dragState.zoom));
      dragState.card.style.left = nx + 'px';
      dragState.card.style.top = ny + 'px';
      dragState.lastX = nx;
      dragState.lastY = ny;
      window.requestAnimationFrame(renderSvgLayer);
      return;
    }

    if (mode === 'connect') {
      if (Math.abs(e.clientX - dragState.rawX) > 3 || Math.abs(e.clientY - dragState.rawY) > 3) {
        suppressClick = true;
      }
      var tempPath = document.getElementById('rms-drag-temp-path');
      if (tempPath) {
        var pt = clientToCanvas(container, inner, e.clientX, e.clientY);
        var x1 = dragState.startX;
        var y1 = dragState.startY;
        var x2 = pt.x;
        var y2 = pt.y;
        var dir = x2 >= x1 ? 1 : -1;
        var curve = Math.max(36, Math.abs(x2 - x1) / 2);
        tempPath.setAttribute('d', 'M ' + x1 + ' ' + y1 + ' C ' + (x1 + dir * curve) + ' ' + y1 + ', ' + (x2 - dir * curve) + ' ' + y2 + ', ' + x2 + ' ' + y2);
        tempPath.style.display = '';
      }
      inner.querySelectorAll('.rms-entity-col.drop-target').forEach(function (el) {
        el.classList.remove('drop-target');
      });
      var hoveredCol = e.target && e.target.closest ? e.target.closest('.rms-entity-col[data-table-id]') : null;
      if (hoveredCol) {
        var hTid = parseInt(hoveredCol.getAttribute('data-table-id') || '0', 10);
        if (hTid && hTid !== dragState.srcTid) {
          hoveredCol.classList.add('drop-target');
        }
      }
      return;
    }

    if (mode === 'pan' && dragState.container) {
      var pdx = e.clientX - dragState.startX;
      var pdy = e.clientY - dragState.startY;
      if (Math.abs(pdx) > 4 || Math.abs(pdy) > 4) suppressClick = true;
      dragState.container.scrollLeft = dragState.scrollLeft - pdx;
      dragState.container.scrollTop = dragState.scrollTop - pdy;
    }
  });

  document.addEventListener('pointerup', function (e) {
    if (!mode) return;
    var currentMode = mode;
    mode = null;

    if (currentMode === 'card' && suppressClick && dragState.tableId) {
      setProps('rms-drag-pos-store', {
        data: {
          table_id: dragState.tableId,
          pos_x: dragState.lastX != null ? dragState.lastX : dragState.origLeft,
          pos_y: dragState.lastY != null ? dragState.lastY : dragState.origTop,
          ts: Date.now(),
        },
      });
    } else if (currentMode === 'connect') {
      var tempPath = document.getElementById('rms-drag-temp-path');
      if (tempPath) tempPath.style.display = 'none';
      var inner = document.getElementById(INNER_ID);
      if (inner) {
        inner.querySelectorAll('.rms-entity-col.drop-target').forEach(function (el) {
          el.classList.remove('drop-target');
        });
      }
      var targetEl = document.elementFromPoint(e.clientX, e.clientY);
      var colTarget = targetEl && targetEl.closest ? targetEl.closest('.rms-entity-col[data-table-id]') : null;
      if (colTarget) {
        var dstTid = parseInt(colTarget.getAttribute('data-table-id') || '0', 10);
        var dstCol = colTarget.getAttribute('data-column') || '';
        if (dstTid && dstTid !== dragState.srcTid && dstCol) {
          setProps('rms-connect-draft-store', {
            data: {
              from_table_id: dragState.srcTid,
              from_column: dragState.srcCol,
              to_table_id: dstTid,
              to_column: dstCol,
              ts: Date.now(),
            },
          });
        }
      }
    }
    dragState = {};
  });

  document.addEventListener(
    'click',
    function (e) {
      var container = document.getElementById(CONTAINER_ID);
      if (!container || !container.contains(e.target)) return;
      if (suppressClick) {
        suppressClick = false;
        return;
      }
      var relHit = e.target.closest('.rms-rel-hit');
      if (relHit) {
        var rid = parseInt(relHit.getAttribute('data-rel-id') || '0', 10);
        if (rid) setProps('rms-canvas-click-store', { data: { kind: 'relationship', id: rid, ts: Date.now() } });
        return;
      }
      var relChip = e.target.closest('.rms-rel-chip[data-rel-id]');
      if (relChip) {
        var cid = parseInt(relChip.getAttribute('data-rel-id') || '0', 10);
        if (cid) setProps('rms-canvas-click-store', { data: { kind: 'relationship', id: cid, ts: Date.now() } });
        return;
      }
      var colEl = e.target.closest('.rms-entity-col[data-field-id]');
      if (colEl && !e.target.closest('.rms-port-dot')) {
        var fid = parseInt(colEl.getAttribute('data-field-id') || '0', 10);
        var ftid = parseInt(colEl.getAttribute('data-table-id') || '0', 10);
        if (fid) setProps('rms-canvas-click-store', { data: { kind: 'field', id: fid, table_id: ftid, ts: Date.now() } });
        return;
      }
      var cardEl = e.target.closest('.rms-entity-card[data-table-id]');
      if (cardEl) {
        var tid = parseInt(cardEl.getAttribute('data-table-id') || '0', 10);
        if (tid) setProps('rms-canvas-click-store', { data: { kind: 'table', id: tid, ts: Date.now() } });
        return;
      }
      setProps('rms-canvas-click-store', { data: { kind: 'clear', ts: Date.now() } });
    },
    true
  );

  document.addEventListener(
    'dblclick',
    function (e) {
      var container = document.getElementById(CONTAINER_ID);
      if (!container || !container.contains(e.target)) return;
      var cardEl = e.target.closest('.rms-entity-card[data-table-id]');
      if (!cardEl) return;
      var tid = parseInt(cardEl.getAttribute('data-table-id') || '0', 10);
      if (!tid) return;
      cardEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
      setProps('rms-canvas-dblclick-store', { data: { kind: 'table', id: tid, ts: Date.now() } });
    },
    true
  );

  var lastFocusToken = '';
  var observer = new MutationObserver(function () {
    if (document.getElementById(SVG_HOST_ID)) {
      window.requestAnimationFrame(renderSvgLayer);
    }
    var inner = document.getElementById(INNER_ID);
    if (inner) {
      var token = inner.getAttribute('data-focus-target') || '';
      if (token && token !== lastFocusToken) {
        lastFocusToken = token;
        var target = inner.querySelector('.rms-entity-card.selected') || inner.querySelector('.rms-rel-chip.selected');
        if (target && target.scrollIntoView) {
          target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        }
      }
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('load', function () {
    renderSvgLayer();
  });
})();
