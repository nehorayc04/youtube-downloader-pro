// ── YouTube Downloader Pro — לוגיקת frontend ──
// shim: ממפה את ה-API הישן )eel.fn(args)()( ל-pywebview )window.pywebview.api.fn(args)(.
// כך כל הקריאות הקיימות עובדות ללא שינוי. eel.expose → no-op )Python קורא
// ל-on_progress ישירות דרך window.evaluate_js(.
const eel = new Proxy({}, {
  get(_, fn) {
    if (fn === 'expose') return () => {};
    return (...args) => () => window.pywebview.api[fn](...args);
  }
});

let INIT = null, DL = {};
const cards = {};

function $(id) { return document.getElementById(id); }
function detectMode(u) { return (u || '').toLowerCase().includes('music.youtube.com') ? 'audio' : 'video'; }

function makeStore(c) {
  const subs = INIT.subtitles;
  const sv = (subs[c.default_subtitle] || subs[0])[1];
  return {
    mode: c.mode_auto ? 'auto' : c.default_mode,
    video_quality: c.video_quality, video_only: !!c.video_only,
    audio_format: c.audio_format, audio_bitrate: c.audio_bitrate, sub_lang: sv,
    embed_thumbnail: !!c.embed_thumbnail, embed_chapters: !!c.embed_chapters,
    embed_subs: !!c.embed_subs, split_chapters: !!c.split_chapters,
    sponsorblock: !!c.sponsorblock, reencode: c.reencode,
    live_from_start: !!c.live_from_start, filename_template: c.filename_template || '',
    extra_args: c.extra_args || '', trim_start: c.trim_start || '', trim_end: c.trim_end || '',
  };
}

function save(persist, key, val) { if (persist) { try { eel.save_setting(key, val)(); } catch (e) {} } }

// מחבר dropdown מותאם: פתיחה/סגירה + בחירה
function wireDropdown(dd, onPick) {
  const key = dd.dataset.dd;
  const head = dd.querySelector('.dd-head');
  head.onclick = (e) => {
    e.stopPropagation();
    const wasOpen = dd.classList.contains('open');
    document.querySelectorAll('.dd.open').forEach(o => o.classList.remove('open'));
    if (!wasOpen) dd.classList.add('open');
  };
  dd.querySelectorAll('.dd-opt').forEach(opt => opt.onclick = (e) => {
    e.stopPropagation();
    const v = opt.dataset.v;
    dd.querySelector('.dd-val').textContent = opt.textContent;
    dd.querySelectorAll('.dd-opt').forEach(o => o.classList.toggle('sel', o === opt));
    dd.classList.remove('open');
    onPick(key, v, opt.textContent);
  });
}
// לחיצה מחוץ — סגירת כל ה-dropdowns
document.addEventListener('click', () =>
  document.querySelectorAll('.dd.open').forEach(o => o.classList.remove('open')));

// dropdown זכוכיתי מותאם )מחליף <select> שהיה לבן-על-לבן ולא נראה(
function ddHtml(key, choices, val) {
  const cur = (choices.find(c => c[1] === val) || choices[0] || ['', ''])[0];
  return `<div class="dd" data-dd="${key}">
    <button type="button" class="dd-head"><span class="dd-val">${cur}</span><span class="dd-arr">▾</span></button>
    <div class="dd-list">
      ${choices.map(c => `<div class="dd-opt ${c[1] === val ? 'sel' : ''}" data-v="${c[1]}">${c[0]}</div>`).join('')}
    </div>
  </div>`;
}

const CHIPS = [
  ['embed_thumbnail', 'image', 'תמונה ממוזערת'],
  ['embed_chapters', 'bookmark', 'פרקים'],
  ['embed_subs', 'captions', 'הטמע כתוביות'],
  ['sponsorblock', 'shield', 'חוסם ספונסרים'],
  ['live_from_start', 'broadcast', 'שידור חי'],
  ['split_chapters', 'scissors', 'פיצול לפי פרקים'],
];
const MODE_ICON = { auto: 'bolt', video: 'video', audio: 'music' };

// בונה את כל מערכת האפשרויות לתוך container
function buildOptions(box, store, persist) {
  box.innerHTML = `
    <div class="seg" data-seg>
      ${INIT.modes.map(m => `<button data-mode="${m[1]}" class="${store.mode === m[1] ? 'active' : ''}">${ic(MODE_ICON[m[1]] || 'bolt')}<span>${m[0]}</span></button>`).join('')}
    </div>
    <div data-vf style="margin-top:12px">
      <div class="grid2">
        <div><label class="lbl">איכות וידאו</label>${ddHtml('video_quality', INIT.video_qualities, store.video_quality)}</div>
        <div><label class="lbl">קידוד מחדש</label>${ddHtml('reencode', INIT.reencode, store.reencode)}</div>
      </div>
      <div class="chip ${store.video_only ? 'on' : ''}" data-chip="video_only" style="margin-top:10px">${ic('mute')}<span>וידאו ללא שמע</span></div>
    </div>
    <div data-af style="margin-top:12px">
      <div class="grid2">
        <div><label class="lbl">פורמט שמע</label>${ddHtml('audio_format', INIT.audio_formats, store.audio_format)}</div>
        <div><label class="lbl">קצב סיביות</label>${ddHtml('audio_bitrate', INIT.audio_bitrates, store.audio_bitrate)}</div>
      </div>
    </div>
    <label class="lbl" style="margin-top:12px">כתוביות</label>
    ${ddHtml('sub_lang', INIT.subtitles, store.sub_lang)}
    <label class="lbl" style="margin-top:14px">התאמה אישית</label>
    <div class="chips">
      ${CHIPS.map(c => `<div class="chip ${store[c[0]] ? 'on' : ''}" data-chip="${c[0]}">${ic(c[1])}<span>${c[2]}</span></div>`).join('')}
    </div>
    <div class="grid2" style="margin-top:10px">
      <input type="text" class="small" data-k="filename_template" placeholder="תבנית שם — %(title)s" value="${store.filename_template}" style="grid-column:1/3">
      <input type="text" class="small" data-k="trim_start" placeholder="חיתוך מ- (0:30)" value="${store.trim_start}">
      <input type="text" class="small" data-k="trim_end" placeholder="חיתוך עד- (2:00)" value="${store.trim_end}">
      <input type="text" class="small" data-k="extra_args" placeholder="פקודות yt-dlp נוספות" value="${store.extra_args}" style="grid-column:1/3">
    </div>`;

  const vf = box.querySelector('[data-vf]'), af = box.querySelector('[data-af]');
  function syncMode() {
    let eff = store.mode;
    if (eff === 'auto') eff = persist ? 'video' : detectMode($('url') ? $('url').value : '');
    vf.classList.toggle('hide', eff === 'audio');
    af.classList.toggle('hide', eff !== 'audio');
  }
  store._sync = syncMode;

  // בורר מצב
  box.querySelectorAll('[data-seg] button').forEach(b => b.onclick = () => {
    box.querySelectorAll('[data-seg] button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    store.mode = b.dataset.mode;
    save(persist, 'mode_auto', store.mode === 'auto');
    if (store.mode !== 'auto') save(persist, 'default_mode', store.mode);
    syncMode();
  });
  // dropdowns מותאמים
  box.querySelectorAll('[data-dd]').forEach(dd => wireDropdown(dd, (key, v, label) => {
    store[key] = v;
    if (key === 'sub_lang') {
      const idx = INIT.subtitles.findIndex(x => x[1] === v);
      save(persist, 'default_subtitle', idx < 0 ? 0 : idx);
    } else save(persist, key, v);
  }));
  // chips
  box.querySelectorAll('[data-chip]').forEach(ch => ch.onclick = () => {
    const k = ch.dataset.chip; store[k] = !store[k];
    ch.classList.toggle('on', store[k]);
    save(persist, k, store[k]);
  });
  // text fields
  box.querySelectorAll('input[data-k]').forEach(inp => inp.onchange = () => {
    store[inp.dataset.k] = inp.value; save(persist, inp.dataset.k, inp.value);
  });

  syncMode();
}

// ── ניווט ──
function setupNav() {
  document.querySelectorAll('.nav-btn').forEach(b => b.onclick = () => {
    document.querySelectorAll('.nav-btn').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    b.classList.add('active');
    $('page-' + b.dataset.page).classList.add('active');
  });
}

// ── URL ──
function setupUrl() {
  const url = $('url'), badge = $('badge');
  function onType() {
    const u = url.value.trim();
    if (!u) { badge.innerHTML = ''; }
    else {
      let icn = 'video', kind = 'סרטון';
      if (u.includes('list=')) { icn = 'list'; kind = 'פלייליסט'; }
      else if (/\/(channel|c|user)\/|\/@/.test(u)) { icn = 'broadcast'; kind = 'ערוץ'; }
      let extra = (DL.mode === 'auto' && detectMode(u) === 'audio') ? `  ·  ${ic('music')}<span>שמע</span>` : '';
      badge.style.color = 'var(--green)';
      badge.innerHTML = `${ic(icn)}<span>${kind}</span>${extra}`;
    }
    if (DL._sync) DL._sync();
  }
  url.oninput = onType;
  $('paste').onclick = async () => { try { url.value = (await navigator.clipboard.readText()).trim(); onType(); } catch (e) {} };
  $('detect').onclick = async () => {
    const u = url.value.trim(); if (!u) return;
    badge.style.color = 'var(--orange)'; badge.innerHTML = `${ic('search')}<span>טוען מידע...</span>`;
    const r = await eel.fetch_info(u)();
    if (r.ok) {
      badge.style.color = 'var(--green)';
      badge.innerHTML = r.playlist ? `${ic('list')}<span>${r.count} סרטונים · ${r.title}</span>`
        : `${ic('video')}<span>${r.title}  (${Math.floor(r.duration / 60)}:${String(r.duration % 60).padStart(2, '0')})</span>`;
    } else { badge.style.color = 'var(--error)'; badge.innerHTML = `${ic('alert')}<span>לא ניתן לטעון מידע</span>`; }
  };
}

// ── הורדה ──
function buildOpts() {
  const o = {}; for (const k in DL) if (!k.startsWith('_')) o[k] = DL[k];
  o.path = $('path').value.trim();
  return o;
}

function setupDownload() {
  $('browse').onclick = async () => { const d = await eel.pick_folder($('path').value)(); if (d) $('path').value = d; };
  $('start').onclick = async () => {
    const u = $('url').value.trim();
    if (!u || !u.startsWith('http')) { $('badge').style.color = 'var(--error)'; $('badge').innerHTML = ic('alert') + '<span>הדבק כתובת תקינה</span>'; return; }
    const it = await eel.start_download(u, buildOpts())();
    addCard(it);
  };
}

function fmtSize(b) { return (b / 1048576).toFixed(1) + ' MB'; }
function fmtSpeed(s) { return s >= 1048576 ? (s / 1048576).toFixed(1) + ' MB/s' : (s / 1024).toFixed(0) + ' KB/s'; }

const ST = {
  downloading: ['arrowDown', 'מוריד...', 'var(--blue)'], paused: ['pause', 'מושהה', 'var(--orange)'],
  merging: ['merge', 'ממזג...', 'var(--orange)'], done: ['check', 'הושלם', 'var(--green)'],
  error: ['x', 'שגיאה', 'var(--error)'], cancelled: ['x', 'בוטל', 'var(--txt3)'], pending: ['hourglass', 'ממתין', 'var(--txt2)'],
};

function addCard(it) {
  $('empty') && $('empty').remove();
  const el = document.createElement('div');
  el.className = 'dlcard glass-soft';
  el.innerHTML = `
    <div class="top">
      <div class="fname"></div>
      <button class="ctrl pause">${ic('pause')}</button>
      <button class="ctrl x">${ic('x')}</button>
    </div>
    <div class="bar"><i></i></div>
    <div class="dlinfo"><span class="pct">0%</span><span class="sz"></span><span class="sp"></span><span class="st"></span></div>
    <div class="note hide"></div>`;
  $('downloads').prepend(el);
  cards[it.id] = el;
  el.querySelector('.pause').onclick = async () => { await eel.pause_download(it.id)(); };
  el.querySelector('.x').onclick = async () => { await eel.cancel_download(it.id)(); };
  updateCard(it);
}

function updateCard(it) {
  const el = cards[it.id]; if (!el) return;
  el.querySelector('.fname').textContent = it.filename || it.url;
  el.querySelector('.bar > i').style.width = Math.min(it.progress, 100) + '%';
  el.querySelector('.pct').textContent = it.progress.toFixed(1) + '%';
  el.querySelector('.sz').textContent = it.total_bytes ? `${fmtSize(it.dl_bytes)} / ${fmtSize(it.total_bytes)}` : '';
  el.querySelector('.sp').innerHTML = (it.status === 'downloading' && it.speed) ? ic('bolt') + '<span>' + fmtSpeed(it.speed) + '</span>' : '';
  const st = ST[it.status] || ['', '', 'var(--txt2)'];
  const s = el.querySelector('.st'); s.innerHTML = (st[0] ? ic(st[0]) : '') + '<span>' + st[1] + '</span>'; s.style.color = st[2];
  el.querySelector('.pct').style.color = st[2];
  const pb = el.querySelector('.pause');
  if (['done', 'error', 'cancelled'].includes(it.status)) {
    pb.classList.add('hide'); el.querySelector('.x').classList.add('hide');
  } else pb.innerHTML = ic(it.status === 'paused' ? 'play2' : 'pause');
  const note = el.querySelector('.note');
  if (it.note) { note.textContent = it.note; note.classList.remove('hide'); }
  if (it.error && it.status === 'error') { note.textContent = it.error; note.classList.remove('hide'); note.style.color = 'var(--error)'; }
}

// callback מה-backend
eel.expose(on_progress);
function on_progress(it) { if (cards[it.id]) updateCard(it); else addCard(it); }

// ── הגדרות ──
function setupSettings() {
  const c = INIT.config;
  // בורר דפדפן — dropdown מותאם )זכוכיתי, אחיד עם השאר(
  const brChoices = INIT.browsers.map(b => [b, b]);
  $('browser-dd').innerHTML = ddHtml('browser', brChoices, c.browser);
  wireDropdown($('browser-dd').firstElementChild, (k, v) => eel.save_setting('browser', v)());
  // cookies switch
  const sw = $('cookies-sw'); sw.classList.toggle('on', c.use_cookies);
  $('cookies-row').onclick = () => { const v = !sw.classList.contains('on'); sw.classList.toggle('on', v); eel.save_setting('use_cookies', v)(); };
  // cookies file
  $('ckfile').value = c.cookies_file || '';
  $('ckfile').onchange = () => eel.save_setting('cookies_file', $('ckfile').value.trim())();
  $('pickck').onclick = async () => { const f = await eel.pick_cookies()(); if (f) { $('ckfile').value = f; eel.save_setting('cookies_file', f)(); } };
  $('clearck').onclick = () => { $('ckfile').value = ''; eel.save_setting('cookies_file', '')(); };
  // update yt-dlp
  $('update').onclick = async () => {
    $('update').innerHTML = ic('refresh') + '<span>מעדכן...</span>';
    const r = await eel.update_ytdlp()();
    $('update').innerHTML = ic(r.ok ? 'check' : 'x') + '<span>' + (r.ok ? 'עודכן' : 'שגיאה') + '</span>';
  };
  // עדכון עצמי לתוכנה )לפי SHA-256(
  $('appupdate').onclick = async () => {
    const st = $('appupd-status');
    $('appupdate').innerHTML = ic('refresh') + '<span>בודק...</span>';
    const info = await eel.check_app_update()();
    const reset = (label) => { $('appupdate').innerHTML = ic('refresh') + '<span>' + label + '</span>'; };
    if (info.error === 'dev') { st.textContent = 'עדכון זמין רק בגרסת ה-exe המותקנת'; reset('בדוק עדכון לתוכנה'); return; }
    if (info.error)           { st.textContent = 'שגיאת בדיקה: ' + info.error; reset('בדוק עדכון לתוכנה'); return; }
    if (!info.available)      { st.textContent = 'התוכנה מעודכנת'; $('appupdate').innerHTML = ic('check') + '<span>מעודכן</span>'; return; }
    // עדכון זמין → לחיצה נוספת מורידה ומתקינה
    st.textContent = 'עדכון זמין' + (info.notes ? ' — ' + info.notes : '');
    $('appupdate').innerHTML = ic('refresh') + '<span>הורד והתקן</span>';
    $('appupdate').onclick = async () => {
      window.on_update_progress = (phase, pct) => {
        st.textContent = (phase === 'verify' ? 'מאמת' : 'מוריד') + ' ' + pct + '%';
      };
      $('appupdate').innerHTML = ic('refresh') + '<span>מעדכן...</span>';
      const r = await eel.do_app_update(info.url, info.latest_sha)();
      if (!r.ok) { st.textContent = 'שגיאה: ' + r.msg; }
      else { st.textContent = 'מותקן — התוכנה תיפתח מחדש...'; }
    };
  };
}

// pywebview.api מוכן רק ב-'pywebviewready' )לא ב-DOMContentLoaded(
window.addEventListener('pywebviewready', async () => {
  injectIcons();   // אייקונים סטטיים )סרגל צד, כותרות, כפתורים, לוגו(
  INIT = await eel.get_init()();
  $('ver').textContent = 'v' + INIT.app_ver;
  $('ytv').textContent = INIT.yt_dlp_ver;
  const ff = $('ff');
  ff.className = INIT.ffmpeg ? 'status-line ok' : 'status-line warn';
  ff.innerHTML = `<span class="dot"></span> FFmpeg ${INIT.ffmpeg ? 'מוכן' : 'חסר'}`;
  $('about').innerHTML = `${INIT.app_name}<br>גרסה ${INIT.app_ver} · yt-dlp ${INIT.yt_dlp_ver}`;
  $('path').value = INIT.config.download_path || '';

  DL = makeStore(INIT.config);
  buildOptions($('opts-dl'), DL, false);
  buildOptions($('opts-set'), makeStore(INIT.config), true);

  setupNav(); setupUrl(); setupDownload(); setupSettings();
});
