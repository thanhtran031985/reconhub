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
 * Cell renderer cho bảng Lịch sử báo cáo (task 55, sửa task 57).
 *
 * Đăng ký vào window.dashAgGridComponentFunctions để columnDefs tham
 * chiếu bằng tên. Nút bấm là DMC Button thật có icon (task 57, theo
 * tài liệu DMC Dash AG Grid): mỗi nút bấm gọi props.setData(action)
 * → Dash nhận qua prop cellRendererData {"value", "colId", "rowIndex",
 * "rowId", "timestamp"} (spike ~/workspace/spike-aggrid-dmc/ đã chứng
 * minh; cellClicked chỉ báo colId nên không phân biệt được nhiều nút
 * trong cùng 1 cột). "Chạy lại"/"Tải file" là điều hướng thuần túy nên
 * renderer chuyển trang trực tiếp bằng JS, không qua Dash.
 */
var dagcomp = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

dagcomp.reconRunsFileCell = function (props) {
  var exp = (props.data && props.data._export) || null;
  if (!exp) return React.createElement('span', null, '—');
  if (exp.status === 'DONE') {
    return React.createElement(
      window.dash_mantine_components.Button,
      {
        size: 'xs',
        variant: 'subtle',
        leftSection: React.createElement(window.dash_iconify.DashIconify, { icon: 'lucide:file-spreadsheet', width: 14 }),
        onClick: function () { window.open('/download/report-export/' + exp.id, '_blank'); },
      },
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
  // Task 73 (D8): màu trạng thái dùng token --ok/--crit/--info/--ink-soft
  // thay vì tên màu CSS cố định ('green'/'red'/...) — tên CSS không đổi
  // theo dark mode nên 'green' chìm trên nền tối (tương phản 2.83).
  var colors = { DONE: 'var(--ok)', FAILED: 'var(--crit)', RUNNING: 'var(--info)', QUEUED: 'var(--ink-soft)', CANCELLED: 'var(--ink-soft)' };
  var code = props.data ? props.data.status_code : '';
  return React.createElement(
    'span',
    { style: { color: colors[code] || 'var(--ink-soft)', fontWeight: 600 } },
    props.value
  );
};

dagcomp.reconRunsActionsCell = function (props) {
  var Button = window.dash_mantine_components.Button;
  var Icon = window.dash_iconify.DashIconify;
  var exp = (props.data && props.data._export) || null;
  var canDelete = !!props.canDelete;
  function mk(action, label, icon, color, show) {
    var btnProps = {
      key: action,
      size: 'xs',
      variant: 'subtle',
      color: color || undefined,
      leftSection: React.createElement(Icon, { icon: icon, width: 14 }),
      onClick: function () { props.setData(action); },
    };
    if (!show) {
      // Task 58: nút giữ chỗ — cùng kích thước với nút thật, ẩn khỏi
      // màn hình, không bấm được — để Xuất lại/Chạy lại không bị đẩy
      // khi nút trước đó biến mất (ví dụ bấm Xóa xong).
      btnProps.style = { visibility: 'hidden' };
      btnProps.disabled = true;
    }
    return React.createElement(Button, btnProps, label);
  }
  // Task 58: 4 vị trí cố định theo thứ tự [Hủy/Thử lại] [Xóa]
  // [Xuất lại] [Chạy lại] — vị trí không phù hợp vẽ nút giữ chỗ nên
  // mọi nút luôn đứng yên một chỗ trên mọi dòng. Lưu ý: nhãn "Thử
  // lại" rộng hơn "Hủy" nên vị trí 1 hơi rộng hơn ở dòng FAILED so
  // với dòng khác — chỉ khác nhau giữa các dòng, không nhảy khi bấm.
  var showCancel = !!exp && (exp.status === 'QUEUED' || exp.status === 'RUNNING');
  var showRetry = !!exp && exp.status === 'FAILED';
  var showDelete = canDelete && !!exp && (exp.status === 'DONE' || exp.status === 'FAILED' || exp.status === 'CANCELLED');
  var buttons = [
    showCancel
      ? mk('cancel', 'Hủy', 'lucide:x', undefined, true)
      : showRetry
        ? mk('retry', 'Thử lại', 'lucide:rotate-ccw', undefined, true)
        : mk('cancel', 'Hủy', 'lucide:x', undefined, false),
    mk('delete', 'Xóa', 'lucide:trash-2', 'red', showDelete),
    mk('rerun', 'Xuất lại', 'lucide:file-spreadsheet', undefined, true),
    React.createElement(
      Button,
      {
        key: 'rerun_link',
        size: 'xs',
        variant: 'subtle',
        leftSection: React.createElement(Icon, { icon: 'lucide:play-circle', width: 14 }),
        onClick: function () {
          window.location.href = '/reports/' + props.data._report_id + '?rerun_from=' + props.data.id;
        },
      },
      'Chạy lại'
    ),
  ];
  return React.createElement(
    'div',
    { style: { display: 'flex', gap: '2px', alignItems: 'center' } },
    buttons
  );
};

/* Task 107 Bước 1: Model Center (/report-models) status & actions renderers. */
dagcomp.rmModelStatusCell = function (props) {
  var colors = {
    ACTIVE: 'var(--ok)',
    VALIDATED: 'var(--info)',
    DRAFT: 'var(--warn)',
    ARCHIVED: 'var(--ink-soft)',
  };
  var code = (props.data && props.data.status) || 'DRAFT';
  var color = colors[code] || 'var(--ink-soft)';
  return React.createElement(
    'span',
    { style: { display: 'inline-flex', alignItems: 'center', gap: '6px', color: color, fontWeight: 600 } },
    React.createElement('span', {
      style: {
        width: '7px',
        height: '7px',
        borderRadius: '50%',
        backgroundColor: color,
        display: 'inline-block',
        flexShrink: 0,
      },
    }),
    props.value || code
  );
};

dagcomp.rmModelActionsCell = function (props) {
  var Button = window.dash_mantine_components.Button;
  var Icon = window.dash_iconify.DashIconify;
  var row = props.data || {};
  var modelId = row.id;
  var isArchived = !!row.is_archived;

  function mk(action, label, icon, color, disabled) {
    return React.createElement(
      Button,
      {
        key: action,
        size: 'xs',
        variant: 'subtle',
        color: color || undefined,
        disabled: !!disabled,
        'aria-label': label + ' ' + (row.code || ''),
        leftSection: React.createElement(Icon, { icon: icon, width: 13 }),
        style: { paddingInline: '6px', height: '24px' },
        onClick: function () {
          props.setData({ action: action, id: modelId, ts: Date.now() });
        },
      },
      label
    );
  }

  return React.createElement(
    'div',
    { style: { display: 'flex', gap: '2px', alignItems: 'center' } },
    mk('open', 'Mở Studio', 'lucide:boxes', undefined, false),
    mk('clone', 'Clone', 'lucide:copy', undefined, false),
    mk('impact', 'Ảnh hưởng', 'lucide:git-branch', undefined, false),
    mk('archive', 'Lưu trữ', 'lucide:archive', 'red', isArchived)
  );
};

/* Task 109 Bước 3: Report Studio Center (/report-studio) status & actions renderers. */
dagcomp.rsStudioStatusCell = function (props) {
  var colors = {
    ACTIVE: 'var(--ok)',
    DRY_RUN_OK: 'var(--info)',
    DRAFT: 'var(--warn)',
    ARCHIVED: 'var(--ink-soft)',
  };
  var code = (props.data && props.data.status) || 'DRAFT';
  var color = colors[code] || 'var(--ink-soft)';
  return React.createElement(
    'span',
    { style: { display: 'inline-flex', alignItems: 'center', gap: '6px', color: color, fontWeight: 600 } },
    React.createElement('span', {
      style: {
        width: '7px',
        height: '7px',
        borderRadius: '50%',
        backgroundColor: color,
        display: 'inline-block',
        flexShrink: 0,
      },
    }),
    props.value || code
  );
};

dagcomp.rsStudioActionsCell = function (props) {
  var Button = window.dash_mantine_components.Button;
  var Icon = window.dash_iconify.DashIconify;
  var row = props.data || {};
  var reportId = row.id;
  var isArchived = !!row.is_archived;
  var canPublish = !!row.can_publish;

  function mk(action, label, icon, color, disabled) {
    return React.createElement(
      Button,
      {
        key: action,
        size: 'xs',
        variant: 'subtle',
        color: color || undefined,
        disabled: !!disabled,
        'aria-label': label + ' ' + (row.code || ''),
        leftSection: React.createElement(Icon, { icon: icon, width: 13 }),
        style: { paddingInline: '6px', height: '24px' },
        onClick: function () {
          props.setData({ action: action, id: reportId, ts: Date.now() });
        },
      },
      label
    );
  }

  return React.createElement(
    'div',
    { style: { display: 'flex', gap: '2px', alignItems: 'center' } },
    mk('design', 'Thiết kế', 'lucide:pen-line', undefined, false),
    mk('view', 'Xem', 'lucide:eye', undefined, false),
    mk('clone', 'Clone', 'lucide:copy', undefined, false),
    mk('publish', 'Phát hành', 'lucide:upload-cloud', undefined, !canPublish),
    mk('impact', 'Ảnh hưởng', 'lucide:git-branch', undefined, false),
    mk('archive', 'Lưu trữ', 'lucide:archive', 'red', isArchived)
  );
};
