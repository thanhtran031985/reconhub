/**
 * ReconHub — Chọn menu bằng phím mũi tên trong ô tìm kiếm header (task 30 bước 3).
 * Dash TextInput không có sẵn phím tắt di chuyển nên bắt phím ở tầng document
 * (capture phase, chạy trước listener của React/Dash nên chặn được n_submit).
 *
 * - Mũi tên xuống/lên: tô sáng kết quả đang chọn (lần đầu: kết quả đầu tiên).
 * - Enter khi đã tô sáng: bấm vào kết quả đó, chặn n_submit của Dash.
 * - Enter khi chưa tô sáng kết quả nào: để Dash xử lý như cũ (tới kết quả đầu).
 * Trạng thái tô sáng suy ra từ DOM nên không cần store riêng; gõ từ mới thì
 * kết quả vẽ lại, tô sáng reset về đầu một cách tự nhiên.
 */
(function () {
  'use strict';

  var HIGHLIGHT_CLASS = 'menu-search-highlight';
  var INPUT_ID = 'app-menu-search-input';
  var RESULTS_ID = 'app-menu-search-results';

  function resultLinks() {
    var box = document.getElementById(RESULTS_ID);
    if (!box) return [];
    return Array.prototype.slice.call(box.querySelectorAll('a[href]'));
  }

  function highlightedIndex(links) {
    for (var i = 0; i < links.length; i++) {
      if (links[i].classList.contains(HIGHLIGHT_CLASS)) return i;
    }
    return -1;
  }

  function setHighlight(links, index) {
    links.forEach(function (link, i) {
      link.classList.toggle(HIGHLIGHT_CLASS, i === index);
    });
  }

  document.addEventListener(
    'keydown',
    function (e) {
      var target = e.target;
      if (!target || target.id !== INPUT_ID) return;
      var links = resultLinks();
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!links.length) return;
        e.preventDefault();
        var cur = highlightedIndex(links);
        var next;
        if (e.key === 'ArrowDown') {
          next = cur < links.length - 1 ? cur + 1 : links.length - 1;
        } else {
          next = cur > 0 ? cur - 1 : 0;
        }
        setHighlight(links, next);
      } else if (e.key === 'Enter') {
        var idx = highlightedIndex(links);
        if (idx >= 0 && links[idx]) {
          // Tới kết quả đang tô sáng, chặn n_submit của Dash (tránh chạy 2 lần).
          e.preventDefault();
          e.stopPropagation();
          links[idx].click();
        }
        // Chưa tô sáng kết quả nào: để Dash xử lý Enter như cũ (tới kết quả đầu).
      }
    },
    true
  );
})();
