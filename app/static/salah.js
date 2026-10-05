/* تعلّم الصلاة: التعرّف على الوضعية داخل المتصفح (MediaPipe Pose Landmarker)، فلا تُرفع الصورة ولا تُحفظ.
   الاستماع اختياري عبر Web Speech API في المتصفح (في Chrome يُرسَل الصوت إلى خدمة Google للتعرّف على الكلام). */
const MP_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
const MP_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
const SALAH_SR = window.SpeechRecognition || window.webkitSpeechRecognition;

/* الخطوات تأتي من الخادم (app/salah.py): لا نص ذكر ولا آية في هذا الملف. كل dhikr من مدونة مِرآة (data/corpus)
   بعد أن يجده الميزان بألفاظه وترتيبها، ومعه مرجعه ورابطه (sources) ومراجع صفة الحركة (refs).
   say: ما يُنطق بالصوت (تعليمات فقط؛ لا يُنطق القرآن ولا الذكر آلياً). wait/alt: ثوانٍ حين يكون الاستماع مطفأً.
   count/key: عدد مرات الذكر في التدريب وكلمته. wrong: ذكر خطوة أخرى في المصدر إن سُمع هنا. */
const SALAH_STEPS = window.SALAH_STEPS || [];

const POSE_DO = { takbir: 'كبّر', qiyam: 'قم', ruku: 'اركع', sujud: 'اسجد', julus: 'اجلس' };
const POSE_AR = { absent: 'لا يظهر جسمك كاملاً', none: 'لا وضعية واضحة', takbir: 'تكبير', qiyam: 'قيام', ruku: 'ركوع', sujud: 'سجود', julus: 'جلوس' };

/* رسوم الوضعيات من الجانب (الوجه إلى اليسار) */
const SALAH_FIG = (() => {
  const g = (body, head) => `<svg viewBox="0 0 120 120" aria-hidden="true"><path d="M8 111h104" class="fg-ground"/><circle cx="${head[0]}" cy="${head[1]}" r="7" class="fg-head"/><path d="${body}" class="fg-body"/></svg>`;
  return {
    takbir: g('M60 30v34M60 64l-4 44M60 64l4 44M60 36l8-8l-4-12', [60, 19]),
    qiyam: g('M60 30v34M60 64l-4 44M60 64l4 44M60 36l7 10l-9 2', [60, 19]),
    ruku: g('M72 62v46M72 62H38M40 62l6 12l22 8', [29, 60]),
    sujud: g('M90 108H66l8-28M74 80L40 98M44 96l-6 12', [31, 103]),
    julus: g('M38 108h34M72 108l-6-8M66 100V64M66 70l-8 14l-12 14', [66, 54]),
  };
})();

/* مطابقة الكلام بنص الذكر: تطبيع عربي ثم كلمة بكلمة */
function salahNorm(t) {
  return t.replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g, '').replace(/[﴿﴾٠-٩0-9.,،؛«»:!؟?]/g, ' ')
    .replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/ؤ/g, 'و').replace(/ئ/g, 'ي')
    .split(/\s+/).filter(Boolean);
}
function salahLev(a, b) {
  if (Math.abs(a.length - b.length) > 1) return 2;
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}
function salahWordHeard(w, heard) {
  return heard.some(h => h === w || h === 'و' + w || w === 'و' + h || (w.length >= 4 && salahLev(h, w) <= 1));
}
/* المقابلة بلغة مِرآة: النسخة (ما سُمع) بأصلها (نص الذكر في المصدر).
   لكل كلمة: ok (قالها، أخضر) · skip (تجاوزها إلى ما بعدها، أحمر: «لم تذكر …») · غير ذلك لم يصل إليها بعد (باهتة).
   المحاذاة بالموضع لا بمجرد الوجود (في الإخلاص «أحد» مرتان): أطول تسلسل مشترك بين الذكر وما سُمع، وكل كلمة مسموعة
   تُحسب لكلمة واحدة من الذكر. كلمة خارجه قيلت بعده استدراك لما سقط، وكلمة خارجه قيلت قبله تعني أن الترتيب يختلف.
   verdict: match «مطابق للمصدر» · dropped «لم تذكر …» · order «الترتيب يختلف» · other «ذكر خطوة أخرى» */
function salahLcs(words, heard) {
  const m = words.length, h = heard.length, eq = (i, j) => salahWordHeard(words[i].n, [heard[j]]);
  const D = Array.from({ length: m + 1 }, () => new Array(h + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) for (let j = h - 1; j >= 0; j--)
    D[i][j] = eq(i, j) ? D[i + 1][j + 1] + 1 : Math.max(D[i + 1][j], D[i][j + 1]);
  const inLcs = new Set(), used = new Set(); let i = 0, j = 0, end = -1;
  while (i < m && j < h) {
    if (eq(i, j) && D[i][j] === D[i + 1][j + 1] + 1) { inLcs.add(i); used.add(j); end = j; i++; j++; }
    else if (D[i + 1][j] >= D[i][j + 1]) i++; else j++;
  }
  return { inLcs, used, end };
}
function salahHear(step, text) {
  const heard = salahNorm(text || '');
  const tokens = (step.dhikr || '').split(/\s+/).filter(Boolean).map(t => ({ t, n: salahNorm(t).join('') }));
  const words = tokens.filter(x => x.n);
  const { inLcs, used, end } = salahLcs(words, heard);
  let ordered = true;
  words.forEach((x, n) => {
    if (inLcs.has(n)) { x.ok = true; return; }
    const j = heard.findIndex((w, k) => !used.has(k) && salahWordHeard(x.n, [w]));
    x.ok = j >= 0;
    if (j >= 0) used.add(j);
    if (j >= 0 && j <= end) ordered = false;   // قيلت قبل آخر ما طابق الترتيب: الترتيب يختلف عن المصدر
  });
  const cover = words.filter(x => x.ok).length / (words.length || 1);
  const lastOk = words.reduce((k, x, n) => (x.ok ? n : k), -1);
  words.forEach((x, n) => { x.skip = !x.ok && n < lastOk; });
  const missing = words.filter(x => x.skip).map(x => x.t.replace(/[،.؛:]+$/, ''));
  const count = step.count ? heard.filter(h => h === step.key || h === 'و' + step.key).length : 0;
  const w = (step.wrong || []).find(x => heard.includes(x.has));
  const wrong = w ? `ما سمعناه هو ذكر ${w.where} في المصدر: «${w.text}». وذكر هذه الخطوة في المصدر: «${step.dhikr}».` : '';
  // لا تكتمل الخطوة وفيها كلمة سقطت حتى يذكرها. وما لم يصل إليه بعد له هامش في القرآن لأخطاء التعرّف على الكلام في الآيات الطويلة
  const ok = !wrong && ordered && !missing.length && cover >= (step.quran ? 0.75 : 0.8)
    && (!step.count || count >= step.count);
  let verdict = '';
  if (heard.length && words.length) {
    if (wrong) verdict = 'other';
    else if (missing.length) verdict = 'dropped';
    else if (!ordered) verdict = 'order';
    else if (cover === 1) verdict = 'match';
  }
  return { tokens, cover, count, ok, wrong, where: w ? w.where : '', any: heard.length > 0, verdict, missing, ordered };
}

/* النقاط: 0 الأنف، 11/12 الكتفان، 15/16 المعصمان، 23/24 الوركان، 25/26 الركبتان. الإحداثيات من 0 إلى 1 والمحور y للأسفل. */
function salahMid(L, a, b) {
  const A = L[a], B = L[b], va = A.visibility ?? 1, vb = B.visibility ?? 1;
  if (va + vb < 0.6) return null;
  return { x: (A.x * va + B.x * vb) / (va + vb), y: (A.y * va + B.y * vb) / (va + vb) };
}

function salahClassify(L) {
  const sh = salahMid(L, 11, 12), hp = salahMid(L, 23, 24), kn = salahMid(L, 25, 26), nose = L[0];
  if (!sh || !hp) return 'absent';
  const tx = sh.x - hp.x, ty = sh.y - hp.y, torso = Math.hypot(tx, ty) || 1e-6;
  const tilt = Math.atan2(Math.abs(tx), -ty) * 180 / Math.PI;  // 0 قائم، 90 أفقي، أكبر من 90 الرأس أدنى من الورك
  let legDown = 1;                                              // 1 الساق عمودية (قيام)، قرب 0 أفقية (جلوس)
  if (kn) { const kx = kn.x - hp.x, ky = kn.y - hp.y; legDown = ky / (Math.hypot(kx, ky) || 1e-6); }
  if (nose && nose.y > hp.y + 0.25 * torso && tilt > 95) return 'sujud';
  if (tilt >= 50 && tilt <= 115 && legDown > 0.7) return 'ruku';
  if (tilt < 35) {
    if (kn && legDown < 0.55) return 'julus';
    const wr = [L[15], L[16]].filter(w => (w.visibility ?? 1) > 0.5);
    if (wr.length && wr.every(w => w.y < sh.y + 0.1 * torso)) return 'takbir';
    return 'qiyam';
  }
  return 'none';
}

const SALAH_BONES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28]];

function salahDraw(canvas, video, L, match) {
  const w = video.videoWidth, h = video.videoHeight;
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const g = canvas.getContext('2d');
  g.clearRect(0, 0, w, h);
  if (!L) return;
  const c = match ? '#2EF2C2' : 'rgba(255,255,255,.85)';
  g.lineWidth = Math.max(3, w / 220); g.strokeStyle = c; g.fillStyle = c; g.lineCap = 'round';
  for (const [a, b] of SALAH_BONES) {
    if ((L[a].visibility ?? 1) < 0.4 || (L[b].visibility ?? 1) < 0.4) continue;
    g.beginPath(); g.moveTo(L[a].x * w, L[a].y * h); g.lineTo(L[b].x * w, L[b].y * h); g.stroke();
  }
  for (const i of [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]) {
    if ((L[i].visibility ?? 1) < 0.4) continue;
    g.beginPath(); g.arc(L[i].x * w, L[i].y * h, g.lineWidth * 1.4, 0, Math.PI * 2); g.fill();
  }
}

function salahTrainer() {
  let landmarker = null, stream = null, raf = 0, lastT = -1, since = 0, timer = 0, absent = 0, seen = 0;
  let rec = null, finals = '', ttsUntil = 0, moving = 0, cueT = 0, cued = '';
  return {
    steps: SALAH_STEPS, i: 0, state: 'idle', err: '', pose: 'none', hit: false, done: false, countdown: 0, fallback: false,
    voice: true, voiceOk: false, canListen: !!SALAH_SR, listen: !!SALAH_SR, micErr: '', heard: '', away: false, praiseText: '',
    stats: {},  // مؤشر الأثر: مطابقة الألفاظ للمصدر في أول محاولة وآخرها لكل خطوة، يُحسب في المتصفح ولا يُرسل
    get s() { return this.steps[this.i]; },
    get poseAr() { return POSE_AR[this.pose] || ''; },
    get fig() { return SALAH_FIG[this.s.pose] || ''; },
    get listening() { return this.listen && this.canListen && this.state === 'run'; },
    get hearing() { return salahHear(this.s, this.heard); },
    get poseOk() { return !this.s.pose || this.hit || this.away; },
    get verdictAr() {
      const h = this.hearing;
      return { match: 'المقابلة: مطابق للمصدر',
               dropped: 'لم تذكر ' + h.missing.map(w => '«' + w + '»').join(' و') + '، قلها حتى يكتمل الذكر',
               order: 'المقابلة: الألفاظ موجودة لكن ترتيبها يختلف عن المصدر',
               other: 'المقابلة: ذكر خطوة أخرى في المصدر' }[h.verdict] || '';
    },
    /* أول محاولة = أول ما سمعناه في الخطوة، وآخر محاولة = أفضل ما سمعناه قبل مغادرتها */
    record() {
      if (!this.heard || !this.s.dhikr) return;
      const c = Math.round(this.hearing.cover * 100), st = this.stats[this.i];
      this.stats = { ...this.stats, [this.i]: st ? { first: st.first, last: Math.max(st.last, c) } : { first: c, last: c } };
    },
    /* ما يظهر على المسرح: الذكر كله إن كان قصيراً، وإلا المقطع (آية أو جملة) الذي فيه أول كلمة سقطت أو أول ما لم يُقل */
    get stage() {
      const toks = this.hearing.tokens, live = this.listening && this.hearing.any;
      const cls = x => (live && x.n ? (x.ok ? 'w-ok' : (x.skip ? 'w-drop' : 'w-miss')) : '');
      const all = toks.map((x, k) => ({ t: x.t, k, cls: cls(x) }));
      const narrow = (this.$refs.stage?.clientWidth || 999) < 520;   // مسرح الجوال: مقطع أقصر حتى لا تغطي الطبقة الكاميرا
      if (toks.filter(x => x.n).length <= (narrow ? 10 : 16)) return { words: all, pre: false, post: false };
      const segs = []; let st = 0;
      toks.forEach((x, k) => { if (/^﴿|[،.]$/.test(x.t)) { segs.push([st, k]); st = k + 1; } });
      if (st < toks.length) segs.push([st, toks.length - 1]);
      let f = toks.findIndex(x => x.skip);
      if (f < 0 && live) f = toks.findIndex(x => x.n && !x.ok);
      if (f < 0) f = live ? toks.length - 1 : 0;
      const a = segs.findIndex(([x, y]) => f >= x && f <= y);
      // يُلحق المقطع التالي بالقصير ما دام المجموع قصيراً يُقرأ من بُعد
      const nWords = (x, y) => toks.slice(segs[x][0], segs[y][1] + 1).filter(t => t.n).length;
      let b = a;
      while (b + 1 < segs.length && nWords(a, b) < (narrow ? 4 : 8) && nWords(a, b + 1) <= (narrow ? 7 : 14)) b++;
      return { words: all.slice(segs[a][0], segs[b][1] + 1), pre: a > 0, post: b < segs.length - 1 };
    },
    /* الذكر في اللوحة الجانبية: الصنف يُحسب هنا لا في القالب، فلا يبقى x-for على كائنات كلمات قديمة */
    get dhikrWords() {
      const live = this.listening;
      return this.hearing.tokens.map((x, k) => ({ t: x.t, k, cls: live && x.n ? (x.ok ? 'w-ok' : (x.skip ? 'w-drop' : 'w-miss')) : '' }));
    },
    get stageVerdict() {
      const h = this.hearing;
      return { match: '✓ مطابق للمصدر', dropped: 'لم تذكر ' + h.missing.map(w => '«' + w + '»').join(' و'),
               order: 'الترتيب يختلف عن المصدر', other: 'هذا ذكر ' + h.where + '، لا ذكر هذه الخطوة' }[h.verdict] || '';
    },
    /* تنبيه صوتي حين يتوقف عن الكلام وفي الذكر كلمة سقطت: يُنطق ما سقط بلفظه من المدونة، فلا يحتاج المتعلّم الواقف إلى الشاشة */
    cue() {
      clearTimeout(cueT);
      cueT = setTimeout(() => {
        const miss = this.hearing.missing, key = miss.join('|');
        if (!this.listening || !key || key === cued) return;
        cued = key;
        this.say((miss.length > 1 ? 'لم تذكر: ' : 'لم تذكر كلمة: ') + miss.join('، ') + '. قلها حتى يكتمل الذكر.');
      }, 2000);
    },
    fullscreen() {
      const el = this.$refs.stage;
      if (document.fullscreenElement) document.exitFullscreen();
      else if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
    },
    get score() {
      const v = Object.values(this.stats);
      if (!v.length) return null;
      const avg = k => Math.round(v.reduce((a, x) => a + x[k], 0) / v.length);
      return { first: avg('first'), last: avg('last'), n: v.length };
    },

    init() {
      if (!('speechSynthesis' in window)) return;
      const check = () => { this.voiceOk = speechSynthesis.getVoices().some(v => (v.lang || '').startsWith('ar')); };
      check(); speechSynthesis.addEventListener('voiceschanged', check);
    },

    say(text) {
      if (!this.voice || !this.voiceOk || this.state !== 'run') return;
      const v = speechSynthesis.getVoices().find(x => (x.lang || '').startsWith('ar'));
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = v.lang; u.voice = v; u.rate = 0.95;
      ttsUntil = Infinity;                                   // لا نحتسب ما يلتقطه الميكروفون من صوت الإرشاد
      u.onend = u.onerror = () => { ttsUntil = Date.now() + 600; };
      speechSynthesis.speak(u);
    },

    /* أول خطوة بعد الحالية لها وضعية؛ الوصول إليها ينقل المتدرب تلقائياً (حين يكون الاستماع مطفأً) */
    get ahead() { for (let j = this.i + 1; j < this.steps.length; j++) if (this.steps[j].pose) return j; return -1; },
    get autoHint() {
      if (this.state !== 'run' || this.done) return '';
      if (this.listening) {
        if (moving) return 'أحسنت، ننتقل إلى الخطوة التالية…';
        if (!this.poseOk) return '';
        return this.s.count ? `قلها ${this.s.count === 3 ? 'ثلاث مرات' : 'مرتين'}، ونحن نسمعك` : 'الآن قل الذكر، ونحن نسمعك';
      }
      if (this.fallback) return `جسمك لا يظهر كاملاً، فننتقل بالوقت بعد ${this.countdown} ث`;
      if (this.s.pose && !this.hit) return '';
      const j = this.ahead;
      if (this.countdown) return `ننتقل تلقائياً بعد ${this.countdown} ث` + (j > this.i + 1 ? `، أو ${POSE_DO[this.steps[j].pose]} متى أنهيت` : '');
      return j < 0 ? '' : `حين تنتقل إلى ${POSE_AR[this.steps[j].pose]} ننتقل تلقائياً`;
    },

    enter() {
      this.hit = false; since = 0; finals = ''; this.heard = ''; this.praiseText = ''; clearTimeout(cueT); cued = '';
      clearTimeout(moving); moving = 0; this.clearTimer(); this.say(this.s.say);
      if (!this.s.pose) this.startTimer();
    },
    go(n) { if (n === 0) this.stats = {}; this.i = n; this.done = false; this.enter(); },
    next() {
      this.clearTimer(); clearTimeout(moving); moving = 0;
      if (this.i < this.steps.length - 1) return this.go(this.i + 1);
      this.done = true; this.say('أحسنت، أتممت التدريب على ركعة كاملة.');
    },

    startTimer(sec = this.s.wait, fb = false) {
      if (this.state !== 'run' || !sec || (this.listening && !fb)) return;
      this.clearTimer(); this.fallback = fb; this.countdown = sec;
      timer = setInterval(() => { if (--this.countdown <= 0) this.next(); }, 1000);
    },
    clearTimer() { clearInterval(timer); timer = 0; this.countdown = 0; this.fallback = false; },

    /* مع الاستماع: الخطوة تتم حين تصحّ الوضعية (أو لا يظهر الجسم) ويُقال الذكر كاملاً */
    check() {
      if (!this.listening || this.done || moving) return;
      if (!this.poseOk || !this.hearing.ok) return;
      this.praiseText = 'أحسنت، قلتها صحيحة';
      this.say('أحسنت');
      moving = setTimeout(() => { moving = 0; this.next(); }, 1600);
    },

    listenStart() {
      if (!this.listening || rec) return;
      rec = new SALAH_SR();
      rec.lang = 'ar-SA'; rec.continuous = true; rec.interimResults = true; rec.maxAlternatives = 5;
      rec.onresult = e => {
        if (Date.now() < ttsUntil) return;
        let interim = '';
        for (let k = e.resultIndex; k < e.results.length; k++) {
          const r = e.results[k], t = this.pickAlt(r);
          if (r.isFinal) finals += ' ' + t; else interim += ' ' + t;
        }
        this.heard = (finals + ' ' + interim).trim();
        this.record();
        this.cue();
        this.check();
      };
      rec.onerror = e => {
        if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
          this.listen = false; this.micErr = 'لم يُسمح بالميكروفون، فننتقل بالوقت بدل الاستماع.';
        }
      };
      rec.onend = () => { if (this.listening && rec) { try { rec.start(); } catch { } } else rec = null; };
      try { rec.start(); this.micErr = ''; } catch { rec = null; }
    },
    /* التعرّف على الكلام قد يخلط العربية بكلمات إنجليزية: يُحذف الحرف اللاتيني، ومن البدائل يُختار أقربها إلى ذكر الخطوة
       (والذكر الخاطئ المتوقع، حتى لا يُخفى «ذكر خطوة أخرى»)، ثم أكثرها عربية */
    pickAlt(r) {
      const ref = salahNorm([this.s.dhikr || ''].concat((this.s.wrong || []).map(w => w.text)).join(' '));
      let best = '', bestScore = -1;
      for (let a = 0; a < r.length; a++) {
        const raw = r[a].transcript || '', t = raw.replace(/[A-Za-z'’-]+/g, ' ').replace(/(^|\s)[,.!?]+(?=\s|$)/g, ' ').replace(/\s+/g, ' ').trim();
        const words = salahNorm(t);
        const hits = words.filter(w => salahWordHeard(w, ref)).length;
        const score = hits * 10 + words.length - (raw.length - t.length > 0 ? 1 : 0);
        if (score > bestScore) { bestScore = score; best = t; }
      }
      return best;
    },
    listenStop() { if (rec) { const r = rec; rec = null; try { r.stop(); } catch { } } },
    toggleListen() {
      if (this.listening) { this.listenStart(); this.clearTimer(); }
      else { this.listenStop(); if (!this.s.pose || this.hit) this.startTimer(); }
    },

    async start() {
      this.err = ''; this.state = 'load';
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 960 }, height: { ideal: 720 } }, audio: false });
        const v = this.$refs.video;
        v.srcObject = stream; await v.play();
        if (!landmarker) {
          const { FilesetResolver, PoseLandmarker } = await import(`${MP_CDN}/vision_bundle.mjs`);
          const files = await FilesetResolver.forVisionTasks(`${MP_CDN}/wasm`);
          const opts = d => ({ baseOptions: { modelAssetPath: MP_MODEL, delegate: d }, runningMode: 'VIDEO', numPoses: 1 });
          try { landmarker = await PoseLandmarker.createFromOptions(files, opts('GPU')); }
          catch { landmarker = await PoseLandmarker.createFromOptions(files, opts('CPU')); }
        }
        this.state = 'run'; this.listenStart(); this.enter(); this.loop();
      } catch (e) {
        this.stop();
        this.err = e && e.name === 'NotAllowedError' ? 'لم يُسمح بالكاميرا. اسمح بها من إعدادات المتصفح ثم أعد المحاولة.'
          : e && e.name === 'NotFoundError' ? 'لم نجد كاميرا في هذا الجهاز.'
          : 'تعذّر تشغيل الكاميرا أو تحميل نموذج التعرّف على الوضعية. تحقّق من الاتصال وأعد المحاولة.';
      }
    },

    stop() {
      cancelAnimationFrame(raf); this.listenStop();
      if (stream) stream.getTracks().forEach(t => t.stop());
      stream = null; lastT = -1; this.state = 'idle'; this.pose = 'none'; this.away = false; this.clearTimer();
      clearTimeout(moving); moving = 0;
      if ('speechSynthesis' in window) speechSynthesis.cancel();
      const c = this.$refs.canvas; c.getContext('2d').clearRect(0, 0, c.width, c.height);
    },

    loop() {
      if (this.state !== 'run') return;
      const v = this.$refs.video;
      if (v.readyState >= 2 && v.currentTime !== lastT) {
        lastT = v.currentTime;
        const L = landmarker.detectForVideo(v, performance.now()).landmarks?.[0];
        this.pose = L ? salahClassify(L) : 'absent';
        salahDraw(this.$refs.canvas, v, L, !!this.s.pose && this.pose === this.s.pose);
        this.track();
      }
      raf = requestAnimationFrame(() => this.loop());
    },

    /* الوضعية ثابتة 700ms ← «أحسنت». الجسم غائب 1.5 ث ← away (تُقبل الخطوة بالذكر وحده، أو بالوقت إن كان الاستماع مطفأً). */
    track() {
      if (this.done) return;
      const now = performance.now();
      if (this.pose === 'absent') {
        since = 0; seen = 0; absent ||= now;
        if (now - absent > 1500 && !this.away) {
          this.away = true;
          if (this.listening) this.check();
          else if (!this.countdown && ((this.s.pose && !this.hit) || this.ahead >= 0)) this.startTimer(this.s.alt || this.s.wait, true);
        }
        return;
      }
      absent = 0; seen ||= now;
      if (this.away && now - seen > 1000) { this.away = false; if (this.fallback) this.clearTimer(); }
      const waiting = this.s.pose && !this.hit, j = waiting ? this.i : (this.listening ? -1 : this.ahead);
      if (j < 0 || this.pose !== this.steps[j].pose) { since = 0; return; }
      if (!since) { since = now; return; }
      if (now - since < 700) return;
      since = 0;
      if (j !== this.i) { this.clearTimer(); this.i = j; finals = ''; this.heard = ''; }
      this.hit = true; this.say(this.s.praise);
      this.startTimer(); this.check();
    },
  };
}
