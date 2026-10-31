/* Chỉ dùng cho preview: thanh chuyển 4 trạng thái + sáng/tối + bộ icon. Không chuyển sang Dash. */
(function(){
  var I={check:'<path d="M20 6 9 17l-5-5"/>','not-equal':'<path d="M5 9h14M5 15h14M17 5 7 19"/>',
  'database-x':'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3M4 11v6c0 1.7 3.6 3 8 3M20 5v5"/><path d="m16 15 5 5M21 15l-5 5"/>',
  'file-x':'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M10 12l4 4M14 12l-4 4"/>',
  shuffle:'<path d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/>',copy:'<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  'alert-triangle':'<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  info:'<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',play:'<path d="m6 3 14 9-14 9z"/>',
  upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',x:'<path d="M18 6 6 18M6 6l12 12"/>',refresh:'<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
  layout:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  history:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',puzzle:'<path d="M15 6a2 2 0 0 0-2-2H9.5a2.5 2.5 0 1 0-5 0H4v5.5a2.5 2.5 0 1 1 0 5V20h5.5a2.5 2.5 0 1 1 5 0H15v-4a2 2 0 1 0 0-4z"/>',
  pencil:'<path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>',database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
  users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 12 0v1"/>',key:'<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  sigma:'<path d="M18 7V4H6l6 8-6 8h12v-3"/>','git-compare':'<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7M11 18H8a2 2 0 0 1-2-2V9"/>',
  flag:'<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7"/>',sparkles:'<path d="m12 3-1.9 5.8L4 10.6l5.9 1.9L12 18l1.9-5.5L20 10.6l-6.1-1.8z"/>',
  trash:'<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',lock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  unlock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.9-1"/>','log-out':'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>'};
  window.RH_ICONS=I;
  document.querySelectorAll('svg[data-i]').forEach(function(s){s.setAttribute('viewBox','0 0 24 24');s.classList.add('rh-icon');s.setAttribute('aria-hidden','true');s.innerHTML=I[s.getAttribute('data-i')]||'';});
  var u=document.getElementById('usr'),m=document.getElementById('usrm');
  if(u&&m){u.addEventListener('click',function(){m.hidden=!m.hidden;});document.addEventListener('click',function(e){if(!u.contains(e.target)&&!m.contains(e.target))m.hidden=true;});}
  var root=document.getElementById('root');if(!root)return;if(!root.dataset.state)root.dataset.state='normal';
  var bar=document.createElement('div');bar.className='pv-bar';bar.setAttribute('role','toolbar');bar.setAttribute('aria-label','Trạng thái xem trước');
  [['normal','Bình thường'],['loading','Đang tải'],['empty','Trống'],['error','Lỗi']].forEach(function(p){var b=document.createElement('button');b.type='button';b.textContent=p[1];b.dataset.s=p[0];
    b.setAttribute('aria-pressed',String(root.dataset.state===p[0]));b.addEventListener('click',function(){root.dataset.state=p[0];bar.querySelectorAll('button[data-s]').forEach(function(x){x.setAttribute('aria-pressed',String(x.dataset.s===p[0]));});});bar.appendChild(b);});
  var t=document.createElement('button');t.type='button';t.textContent='Sáng/Tối';t.addEventListener('click',function(){var h=document.documentElement;h.dataset.theme=h.dataset.theme==='dark'?'light':'dark';});bar.appendChild(t);
  document.body.appendChild(bar);
})();
