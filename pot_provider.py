# -*- coding: utf-8 -*-
"""
PO Token provider ל-yt-dlp — מייצר WebPO Token דרך WebView2 )Edge Chromium(.
משחזר בדיוק את מה ש-YTDLnis עושה: Python מבצע את קריאות ה-HTTP ל-BotGuard API
)att/get + GenerateIT(, ו-WebView2 מריץ את ה-BotGuard JS )runBotGuard + obtainPoToken(.
אין תלות ב-Node/npm — DOM אמיתי של Edge עובר את ה-anti-bot )בניגוד ל-jsdom(.

שימוש עצמאי לבדיקה:
    python pot_provider.py
מחזיר JSON: {"po_token": "...", "visitor_data": "..."}
"""
import json
import re
import sys
import time
import base64
import urllib.request
import urllib.error

REQUEST_KEY = "O43z0dpjhgX20SCx4KAo"
GOOG_API_KEY = "AIzaSyDyT5W0Jh49F30Pqqtyfdf7pDLFKLJoAnw"
GOOG_BASE = "https://jnn-pa.googleapis.com/$rpc/google.internal.waa.v1.Waa"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

VERBOSE = True
_LOG_FILE = None      # אם מוגדר — הלוגים נכתבים לקובץ )לדיבוג frozen ללא console(
def log(*a):
    msg = "[pot] " + " ".join(str(x) for x in a)
    if _LOG_FILE:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass
    elif VERBOSE:
        try:
            print(msg, file=sys.stderr, flush=True)
        except Exception:
            pass


def _http(url, data=None, headers=None, method=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_visitor_data():
    """visitor_data טרי מ-ytcfg של עמוד הבית + גרסת client."""
    st, raw = _http("https://www.youtube.com/?hl=en")
    html = raw.decode("utf-8", "replace")
    m = re.search(r'"visitorData":"([^"]+)"', html)
    v = m.group(1) if m else None
    cv = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
    return v, (cv.group(1) if cv else "2.20260603.00.00")


def get_challenge(visitor, cver):
    ctx = {"client": {"clientName": "WEB", "clientVersion": cver}}
    if visitor:
        ctx["client"]["visitorData"] = visitor
    st, raw = _http(
        "https://www.youtube.com/youtubei/v1/att/get?prettyPrint=false",
        data={"context": ctx, "engagementType": "ENGAGEMENT_TYPE_UNBOUND"},
        headers={"Origin": "https://www.youtube.com", "Referer": "https://www.youtube.com/"},
    )
    j = json.loads(raw.decode("utf-8", "replace"))
    bg = j["bgChallenge"]
    iu = bg["interpreterUrl"]["privateDoNotAccessOrElseTrustedResourceUrlWrappedValue"]
    if iu.startswith("//"):
        iu = "https:" + iu
    st2, ijs = _http(iu)
    interpreter_js = ijs.decode("utf-8", "replace")
    log("challenge: globalName=%s program=%dB interpreter=%dB"
        % (bg["globalName"], len(bg["program"]), len(interpreter_js)))
    return {
        "program": bg["program"],
        "globalName": bg["globalName"],
        "interpreterJavascript": {
            "privateDoNotAccessOrElseSafeScriptWrappedValue": interpreter_js
        },
    }


def generate_integrity_token(botguard_response):
    st, raw = _http(
        GOOG_BASE + "/GenerateIT",
        data=[REQUEST_KEY, botguard_response],
        headers={
            "Content-Type": "application/json+protobuf",
            "x-goog-api-key": GOOG_API_KEY,
            "x-user-agent": "grpc-web-javascript/0.1",
            "Origin": "https://www.youtube.com",
        },
    )
    txt = raw.decode("utf-8", "replace")
    log("GenerateIT status=%s body_head=%s" % (st, txt[:160]))
    arr = json.loads(txt)
    # [integrityToken, estimatedTtlSecs, mintRefreshThreshold, websafeFallbackToken]
    # כמו bgutils-js: integrityToken ?? websafeFallbackToken
    it = arr[0]
    if not it and len(arr) > 3:
        it = arr[3]
        log("integrityToken null — נופל ל-websafeFallbackToken")
    return it, (arr[1] if len(arr) > 1 else 3600)


# ── JS שרץ בתוך ה-WebView ─────────────────────────────────────────────
_BOTGUARD_JS = r"""
function loadBotGuard(challengeData) {
  this.vm = this[challengeData.globalName];
  this.program = challengeData.program;
  this.vmFunctions = {};
  this.syncSnapshotFunction = null;
  if (!this.vm) throw new Error('[BG]: VM not found');
  if (!this.vm.a) throw new Error('[BG]: Could not load program');
  var self = this;
  var cb = function (asyncSnap, shutdown, passEvent, checkCam) {
    self.vmFunctions = { asyncSnapshotFunction: asyncSnap, shutdownFunction: shutdown,
                         passEventFunction: passEvent, checkCameraFunction: checkCam };
  };
  this.syncSnapshotFunction = this.vm.a(this.program, cb, true, undefined, function(){}, [[],[]])[0];
  return new Promise(function (resolve, reject) {
    var i = 0;
    var iv = setInterval(function () {
      if (!!self.vmFunctions.asyncSnapshotFunction) { resolve(self); clearInterval(iv); }
      if (i >= 10000) { reject('asyncSnapshotFunction null after 10s'); clearInterval(iv); }
      i += 1;
    }, 1);
  });
}
function snapshot(bg, args) {
  return new Promise(function (resolve, reject) {
    if (!bg.vmFunctions.asyncSnapshotFunction) return reject(new Error('[BG]: no async snapshot'));
    bg.vmFunctions.asyncSnapshotFunction(function (r) { resolve(r); },
      [args.contentBinding, args.signedTimestamp, args.webPoSignalOutput, args.skipPrivacyBuffer]);
  });
}
function runBotGuard(challengeData) {
  var ijs = challengeData.interpreterJavascript.privateDoNotAccessOrElseSafeScriptWrappedValue;
  if (ijs) { new Function(ijs)(); } else throw new Error('Could not load VM');
  var webPoSignalOutput = [];
  return loadBotGuard.call(window, {
    globalName: challengeData.globalName, globalObj: window, program: challengeData.program
  }).then(function (bg) {
    return snapshot(bg, { webPoSignalOutput: webPoSignalOutput });
  }).then(function (botguardResponse) {
    return { webPoSignalOutput: webPoSignalOutput, botguardResponse: botguardResponse };
  });
}
function obtainPoToken(webPoSignalOutput, integrityToken, identifier) {
  var getMinter = webPoSignalOutput[0];
  if (!getMinter) throw new Error('PMD:Undefined');
  var mintCallback = getMinter(integrityToken);
  if (!(mintCallback instanceof Function)) throw new Error('APF:Failed');
  var result = mintCallback(identifier);
  if (!result) throw new Error('YNJ:Undefined');
  if (!(result instanceof Uint8Array)) throw new Error('ODM:Invalid');
  return result;
}

// ── wrappers שמאחסנים state ב-window ומחזירים ערכים serializable ──
function _b64ToU8(b64) {
  var bin = atob(b64.replace(/-/g,'+').replace(/_/g,'/'));
  var u = new Uint8Array(bin.length);
  for (var i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);
  return u;
}
function _u8ToB64url(u) {
  var bin=''; for (var i=0;i<u.length;i++) bin+=String.fromCharCode(u[i]);
  return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
window._poRun = function (cdJson) {
  window._poState='running'; window._poErr=null; window._poRes=null;
  try {
    var cd = JSON.parse(cdJson);
    runBotGuard(cd).then(function (r) {
      window.__bg = r;
      window._sigLen = (r.webPoSignalOutput && r.webPoSignalOutput.length) || 0;
      window._sigType = window._sigLen ? (typeof r.webPoSignalOutput[0]) : 'none';
      window._poRes = (typeof r.botguardResponse==='string') ? r.botguardResponse
                      : JSON.stringify(r.botguardResponse);
      window._poState='done';
    }).catch(function (e) { window._poErr=''+e+(e&&e.stack?' || '+e.stack:''); window._poState='error'; });
  } catch (e) { window._poErr=''+e; window._poState='error'; }
};
window._poMint = function (integrityTokenB64, identifier) {
  window._poState='running'; window._poErr=null; window._poRes=null;
  try {
    var it = _b64ToU8(integrityTokenB64);
    var tok = obtainPoToken(window.__bg.webPoSignalOutput, it, identifier);
    window._poRes = _u8ToB64url(tok);
    window._poState='done';
  } catch (e) { window._poErr=''+e+(e&&e.stack?' || '+e.stack:''); window._poState='error'; }
};
"""

_HTML = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>pot</title>" \
        "<script>%s</script></head><body>pot</body></html>" % _BOTGUARD_JS


def _wait(window, timeout=25.0):
    """poll עד ש-_poState != running. מחזיר (res, err)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        state = window.evaluate_js("window._poState")
        if state == "done":
            return window.evaluate_js("window._poRes"), None
        if state == "error":
            return None, window.evaluate_js("window._poErr")
        time.sleep(0.1)
    return None, "timeout after %ss (state=%s)" % (timeout, state)


_RESULT = {"po_token": None, "visitor_data": None, "ttl": 0, "error": None}
_OUT_FILE = None


def _worker(window):
    try:
        log("worker: started")
        # ממתינים שדף youtube.com ייטען )origin אמיתי ש-BotGuard דורש(, ואז
        # מזריקים את ה-VM functions. ב-about:blank ה-attestation נכשל )origin ריק(.
        for _ in range(60):
            try:
                rs = window.evaluate_js("document.readyState")
            except Exception:
                rs = None
            if rs == "complete":
                break
            time.sleep(0.2)
        host = window.evaluate_js("location.hostname")
        log("page loaded: hostname=%s readyState=%s" % (host, rs))
        window.evaluate_js(_BOTGUARD_JS)

        # visitor_data — עדיף מאותו session של ה-WebView )עקביות עם ה-token(
        visitor = window.evaluate_js(
            "(window.ytcfg&&ytcfg.get&&ytcfg.get('VISITOR_DATA'))||null")
        cver = window.evaluate_js(
            "(window.ytcfg&&ytcfg.get&&ytcfg.get('INNERTUBE_CLIENT_VERSION'))||null")
        if not visitor:
            visitor, cver = get_visitor_data()
        if not cver:
            cver = "2.20260603.00.00"
        # ytcfg מאחסן VISITOR_DATA לעיתים URL-encoded )%3D(; ל-PO token וליצירת
        # ה-binding צריך raw, וכך גם yt-dlp שולח. מפענחים פעם אחת לעקביות.
        if visitor and "%" in visitor:
            from urllib.parse import unquote
            visitor = unquote(visitor)
        log("visitor=%s... cver=%s" % ((visitor or "")[:30], cver))
        _RESULT["visitor_data"] = visitor

        cd = get_challenge(visitor, cver)

        # שלב 1: runBotGuard ב-WebView
        window.evaluate_js("window._poRun(%s)" % json.dumps(json.dumps(cd)))
        bgr, err = _wait(window, 30)
        if err:
            _RESULT["error"] = "runBotGuard: " + str(err)
            log("runBotGuard ERROR:", err)
            window.destroy(); return
        sig_len = window.evaluate_js("window._sigLen")
        sig_type = window.evaluate_js("window._sigType")
        log("botguardResponse len=%d | webPoSignalOutput.len=%s type=%s"
            % (len(bgr or ""), sig_len, sig_type))

        # שלב 2: GenerateIT ב-Python
        integrity_token, ttl = generate_integrity_token(bgr)
        _RESULT["ttl"] = ttl
        log("integrityToken len=%d ttl=%s" % (len(integrity_token or ""), ttl))

        # שלב 3: obtainPoToken ב-WebView, bound ל-visitor_data
        window.evaluate_js("window._poMint(%s, %s)"
                           % (json.dumps(integrity_token), json.dumps(visitor)))
        tok, err = _wait(window, 15)
        if err:
            _RESULT["error"] = "obtainPoToken: " + str(err)
            log("obtainPoToken ERROR:", err)
            window.destroy(); return
        _RESULT["po_token"] = tok
        log("PO TOKEN len=%d: %s..." % (len(tok or ""), (tok or "")[:40]))
    except Exception as e:
        import traceback
        _RESULT["error"] = "%s\n%s" % (e, traceback.format_exc())
        log("WORKER EXCEPTION:", _RESULT["error"])
    finally:
        if _OUT_FILE:
            try:
                with open(_OUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(_RESULT, f)
            except Exception:
                pass
        try:
            window.destroy()
        except Exception:
            pass


def mint():
    import webview
    log("mint: creating window (frozen=%s)" % getattr(sys, "frozen", False))
    win = webview.create_window("pot", url="https://www.youtube.com/?hl=en",
                                hidden=False, width=560, height=420)
    log("mint: webview.start (gui=edgechromium)")
    try:
        webview.start(_worker, win, gui="edgechromium")
    except Exception as e:
        log("mint: webview.start EXCEPTION: %s" % e)
        # נסיון נוסף בלי לכפות gui )ברירת מחדל של pywebview(
        try:
            webview.start(_worker, win)
        except Exception as e2:
            log("mint: fallback start EXCEPTION: %s" % e2)
    log("mint: webview.start returned; token=%s" % bool(_RESULT.get("po_token")))
    return _RESULT


if __name__ == "__main__":
    for _a in sys.argv[1:]:
        if _a.startswith("--out="):
            _OUT_FILE = _a[6:]
        if _a == "-q":
            VERBOSE = False
    r = mint()
    print(json.dumps(r))
