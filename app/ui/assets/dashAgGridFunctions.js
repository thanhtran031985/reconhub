/**
 * ReconHub — Comparator cho grid kết quả trung tâm báo cáo (task 39).
 *
 * rowData của grid mang chuỗi ĐÃ ĐỊNH DẠNG theo mask (vd "1.275.000",
 * "35,80%", "01/11/2026") nên sort mặc định của AG Grid (so chuỗi) sẽ
 * sai — "9.000" > "55.000". Hai hàm này parse ngược chuỗi về số /
 * timestamp để sort trong trang đúng; sau refetch server grid sort lại
 * cũng đúng thứ tự.
 *
 * Đăng ký vào window.dashAgGridFunctions để columnDefs tham chiếu bằng
 * tên ({"function": "reconViewerNumCompare"}). Dạng inline
 * {"function": "function(a, b) {...}"} đã thử ở dash-ag-grid 35.3.0 và
 * KHÔNG chạy (rơi về sort chuỗi mặc định) — xem prototype
 * ~/workspace/dag-comparator-proto.py.
 */
var dagfuncs = window.dashAgGridFunctions = window.dashAgGridFunctions || {};

dagfuncs.reconViewerNumCompare = function (a, b) {
  var num = function (v) {
    if (v == null || v === '' || v === '—') return null;
    if (typeof v === 'number') return v;
    var s = String(v).trim();
    var pct = false;
    if (s.slice(-1) === '%') { pct = true; s = s.slice(0, -1); }
    s = s.replace(/\./g, '').replace(',', '.');
    var f = parseFloat(s);
    if (isNaN(f)) return null;
    return pct ? f / 100 : f;
  };
  var x = num(a), y = num(b);
  if (x == null && y == null) return 0;
  if (x == null) return -1;
  if (y == null) return 1;
  return x < y ? -1 : (x > y ? 1 : 0);
};

dagfuncs.reconViewerDateCompare = function (a, b) {
  var ts = function (v) {
    if (v == null || v === '' || v === '—') return null;
    if (v instanceof Date) return v.getTime();
    var s = String(v).trim();
    var m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})(?: (\d{2}):(\d{2})(?::(\d{2}))?)?$/);
    if (m) return new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)).getTime();
    m = s.match(/^(\d{2})\/(\d{4})$/);
    if (m) return new Date(+m[2], +m[1] - 1, 1).getTime();
    var d = Date.parse(s);
    return isNaN(d) ? null : d;
  };
  var x = ts(a), y = ts(b);
  if (x == null && y == null) return 0;
  if (x == null) return -1;
  if (y == null) return 1;
  return x < y ? -1 : (x > y ? 1 : 0);
};

/**
 * Cell renderer cho bảng Lịch sử báo cáo (task 55).
 *
 * Đăng ký vào window.dashAgGridComponentFunctions để columnDefs tham
 * chiếu bằng tên ({"cellRenderer": "reconRunsFileCell"}). Nút bấm trong
 * cell KHÔNG cần onClick: click nổi bọt lên cell, Dash nhận qua prop
 * cellClicked với colId + rowId (spike ~/workspace/spike-aggrid-button/
 * đã chứng minh; ngược lại props.setData / rowData KHÔNG đồng bộ về
 * Dash nên không dùng đường đó).
 */
var dagcomp = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

dagcomp.reconRunsFileCell = function (props) {
  var exp = (props.data && props.data._export) || null;
  if (!exp) return React.createElement('span', null, '—');
  if (exp.status === 'DONE') {
    return React.createElement(
      'a',
      { href: '/download/report-export/' + exp.id, target: '_blank', className: 'rh-grid-link' },
      'Tải file'
    );
  }
  var labels = {
    QUEUED: 'Đang chờ',
    RUNNING: 'Đang xuất ' + (exp.progress_pct || 0) + '%',
    FAILED: 'Lỗi',
    CANCELLED: 'Đã hủy'
  };
  return React.createElement('span', null, labels[exp.status] || exp.status);
};

dagcomp.reconRunsStatusCell = function (props) {
  var colors = { DONE: 'green', FAILED: 'red', RUNNING: 'blue', QUEUED: 'gray', CANCELLED: 'gray' };
  var code = props.data ? props.data.status_code : '';
  return React.createElement(
    'span',
    { style: { color: colors[code] || 'gray', fontWeight: 600 } },
    props.value
  );
};

dagcomp.reconRunsActionCell = function (props) {
  var action = props.action;
  var exp = (props.data && props.data._export) || null;
  var show = false;
  if (action === 'cancel') show = !!exp && (exp.status === 'QUEUED' || exp.status === 'RUNNING');
  else if (action === 'retry') show = !!exp && exp.status === 'FAILED';
  else if (action === 'delete') show = !!exp && (exp.status === 'DONE' || exp.status === 'FAILED' || exp.status === 'CANCELLED');
  else if (action === 'rerun') show = true;
  if (!show) return null;
  var labels = { cancel: 'Hủy', retry: 'Thử lại', delete: 'Xóa', rerun: 'Xuất lại' };
  var cls = 'rh-grid-btn' + (action === 'delete' ? ' danger' : '');
  return React.createElement('button', { type: 'button', className: cls }, labels[action] || action);
};

dagcomp.reconRunsRerunLink = function (props) {
  return React.createElement(
    'a',
    { href: '/reports/' + props.data._report_id + '?rerun_from=' + props.data.id, className: 'rh-grid-link' },
    'Chạy lại'
  );
};
