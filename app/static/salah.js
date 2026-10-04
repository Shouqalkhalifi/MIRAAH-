/* تعلّم الصلاة: التعرّف على الوضعية داخل المتصفح (MediaPipe Pose Landmarker). لا تُرفع الصورة ولا تُحفظ. */
const MP_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
const MP_MODEL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

const FATIHA = 'بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ ﴿١﴾ الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ ﴿٢﴾ الرَّحْمَنِ الرَّحِيمِ ﴿٣﴾ مَالِكِ يَوْمِ الدِّينِ ﴿٤﴾ إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ ﴿٥﴾ اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ ﴿٦﴾ صِرَاطَ الَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ الْمَغْضُوبِ عَلَيْهِمْ وَلَا الضَّالِّينَ ﴿٧﴾';
const IKHLAS = 'قُلْ هُوَ اللَّهُ أَحَدٌ ﴿١﴾ اللَّهُ الصَّمَدُ ﴿٢﴾ لَمْ يَلِدْ وَلَمْ يُولَدْ ﴿٣﴾ وَلَمْ يَكُنْ لَهُ كُفُوًا أَحَدٌ ﴿٤﴾';
const TASHAHHUD = 'التَّحِيَّاتُ لِلَّهِ، وَالصَّلَوَاتُ وَالطَّيِّبَاتُ، السَّلَامُ عَلَيْكَ أَيُّهَا النَّبِيُّ وَرَحْمَةُ اللَّهِ وَبَرَكَاتُهُ، السَّلَامُ عَلَيْنَا وَعَلَى عِبَادِ اللَّهِ الصَّالِحِينَ، أَشْهَدُ أَنْ لَا إِلَهَ إِلَّا اللَّهُ، وَأَشْهَدُ أَنَّ مُحَمَّدًا عَبْدُهُ وَرَسُولُهُ. اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ، كَمَا صَلَّيْتَ عَلَى إِبْرَاهِيمَ وَعَلَى آلِ إِبْرَاهِيمَ، إِنَّكَ حَمِيدٌ مَجِيدٌ، اللَّهُمَّ بَارِكْ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ، كَمَا بَارَكْتَ عَلَى إِبْرَاهِيمَ وَعَلَى آلِ إِبْرَاهِيمَ، إِنَّكَ حَمِيدٌ مَجِيدٌ';

/* say: ما يُنطق بالصوت (تعليمات فقط؛ لا يُنطق القرآن ولا الذكر آلياً) */
const SALAH_STEPS = [
  { name: 'التكبير', pose: 'takbir', title: 'تكبيرة الإحرام',
    do: 'قف مستقبلاً القبلة، وارفع يديك حذو منكبيك، وقل:', dhikr: 'اللَّهُ أَكْبَرُ',
    say: 'قف مستقبلاً القبلة، وارفع يديك وكبّر.', praise: 'أحسنت، كبّرت',
    src: 'رفع اليدين حذو المنكبين عند التكبير: صحيح البخاري (735) عن ابن عمر رضي الله عنهما.' },
  { name: 'الفاتحة', pose: 'qiyam', title: 'القيام وقراءة الفاتحة',
    do: 'أنزل يديك وقف معتدلاً، ثم اقرأ سورة الفاتحة:', dhikr: FATIHA, quran: true,
    say: 'قف معتدلاً، واقرأ سورة الفاتحة.', praise: 'أحسنت، أنت قائم. اقرأ الفاتحة', wait: 35,
    src: 'سورة الفاتحة. وفي صحيح البخاري (756): «لا صلاة لمن لم يقرأ بفاتحة الكتاب».' },
  { name: 'سورة', pose: null, title: 'ما تيسّر من القرآن',
    do: 'بعد الفاتحة اقرأ ما تيسّر لك من القرآن، مثل سورة الإخلاص:', dhikr: IKHLAS, quran: true,
    say: 'اقرأ ما تيسّر لك من القرآن.', wait: 20, src: 'سورة الإخلاص.' },
  { name: 'الركوع', pose: 'ruku', title: 'الركوع',
    do: 'قل «الله أكبر» واركع: اجعل ظهرك مستوياً ويديك على ركبتيك، وقل:', dhikr: 'سُبْحَانَ رَبِّيَ الْعَظِيمِ', times: 'ثلاث مرات',
    say: 'كبّر واركع.', praise: 'أحسنت، ركوع صحيح الوضعية. قل: سبحان ربي العظيم، ثلاث مرات',
    src: 'صحيح مسلم (772) عن حذيفة رضي الله عنه.' },
  { name: 'الرفع', pose: 'qiyam', title: 'الرفع من الركوع',
    do: 'ارفع من الركوع حتى تعتدل قائماً، وقل:', dhikr: 'سَمِعَ اللَّهُ لِمَنْ حَمِدَهُ، رَبَّنَا لَكَ الْحَمْدُ',
    say: 'ارفع من الركوع حتى تعتدل قائماً.', praise: 'أحسنت، اعتدلت قائماً',
    src: 'صحيح البخاري (789) عن أبي هريرة رضي الله عنه.' },
  { name: 'السجود', pose: 'sujud', title: 'السجود',
    do: 'قل «الله أكبر» واسجد على الجبهة والأنف، واليدين، والركبتين، وأطراف القدمين، وقل:', dhikr: 'سُبْحَانَ رَبِّيَ الْأَعْلَى', times: 'ثلاث مرات',
    say: 'كبّر واسجد.', praise: 'أحسنت، سجود. قل: سبحان ربي الأعلى، ثلاث مرات',
    src: 'الذكر: صحيح مسلم (772) عن حذيفة. والأعضاء السبعة: صحيح البخاري (812) عن ابن عباس رضي الله عنهما.' },
  { name: 'الجلوس', pose: 'julus', title: 'الجلوس بين السجدتين',
    do: 'قل «الله أكبر» وارفع من السجود واجلس، وقل:', dhikr: 'رَبِّ اغْفِرْ لِي، رَبِّ اغْفِرْ لِي',
    say: 'كبّر واجلس بين السجدتين.', praise: 'أحسنت، جلست',
    src: 'سنن أبي داود (874) عن حذيفة رضي الله عنه.' },
  { name: 'السجدة الثانية', pose: 'sujud', title: 'السجدة الثانية',
    do: 'قل «الله أكبر» واسجد مرة ثانية كالأولى، وقل:', dhikr: 'سُبْحَانَ رَبِّيَ الْأَعْلَى', times: 'ثلاث مرات',
    say: 'كبّر واسجد السجدة الثانية.', praise: 'أحسنت، سجدت الثانية',
    src: 'صحيح مسلم (772) عن حذيفة رضي الله عنه.' },
  { name: 'التشهد', pose: 'julus', title: 'الجلوس للتشهد',
    do: 'هذا تدريب على ركعة واحدة؛ في الصلاة تُكمل ركعاتها، ثم تجلس في آخرها للتشهد، وتقول:', dhikr: TASHAHHUD,
    say: 'اجلس للتشهد.', praise: 'أحسنت، جلست للتشهد. اقرأ التشهد', wait: 30,
    src: 'التشهد: صحيح البخاري (831) عن ابن مسعود. والصلاة على النبي ﷺ: صحيح البخاري (3370) عن كعب بن عجرة رضي الله عنهما.' },
  { name: 'التسليم', pose: null, title: 'التسليم',
    do: 'التفت إلى يمينك وقل، ثم إلى يسارك وقل:', dhikr: 'السَّلَامُ عَلَيْكُمْ وَرَحْمَةُ اللَّهِ',
    say: 'التفت يميناً ثم يساراً وسلّم.', wait: 8, src: 'سنن أبي داود (996) عن ابن مسعود رضي الله عنه.' },
];

const POSE_DO = { takbir: 'كبّر', qiyam: 'قم', ruku: 'اركع', sujud: 'اسجد', julus: 'اجلس' };
const POSE_AR = { absent: 'لا يظهر جسمك كاملاً', none: 'لا وضعية واضحة', takbir: 'تكبير', qiyam: 'قيام', ruku: 'ركوع', sujud: 'سجود', julus: 'جلوس' };

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
  let landmarker = null, stream = null, raf = 0, lastT = -1, since = 0, timer = 0;
  return {
    steps: SALAH_STEPS, i: 0, state: 'idle', err: '', pose: 'none', hit: false, done: false, countdown: 0,
    voice: true, voiceOk: false,
    get s() { return this.steps[this.i]; },
    get poseAr() { return POSE_AR[this.pose] || ''; },

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
      speechSynthesis.speak(u);
    },

    /* أول خطوة بعد الحالية لها وضعية؛ الوصول إليها ينقل المتدرب تلقائياً */
    get ahead() { for (let j = this.i + 1; j < this.steps.length; j++) if (this.steps[j].pose) return j; return -1; },
    get autoHint() {
      if (this.state !== 'run' || this.done || (this.s.pose && !this.hit)) return '';
      const j = this.ahead;
      if (this.countdown) return `ننتقل تلقائياً بعد ${this.countdown} ث` + (j > this.i + 1 ? `، أو ${POSE_DO[this.steps[j].pose]} متى أنهيت` : '');
      return j < 0 ? '' : `حين تنتقل إلى ${POSE_AR[this.steps[j].pose]} ننتقل تلقائياً`;
    },

    enter() {
      this.hit = false; since = 0; this.clearTimer(); this.say(this.s.say);
      if (!this.s.pose) this.startTimer();
    },
    go(n) { this.i = n; this.done = false; this.enter(); },
    next() {
      this.clearTimer();
      if (this.i < this.steps.length - 1) return this.go(this.i + 1);
      this.done = true; this.say('أحسنت، أتممت التدريب على ركعة كاملة.');
    },

    /* wait: ثوانٍ للقراءة قبل الانتقال، لأن الكاميرا لا تسمع (الفاتحة، السورة، التشهد، التسليم) */
    startTimer() {
      if (this.state !== 'run' || !this.s.wait) return;
      this.countdown = this.s.wait;
      timer = setInterval(() => { if (--this.countdown <= 0) this.next(); }, 1000);
    },
    clearTimer() { clearInterval(timer); timer = 0; this.countdown = 0; },

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
        this.state = 'run'; this.enter(); this.loop();
      } catch (e) {
        this.stop();
        this.err = e && e.name === 'NotAllowedError' ? 'لم يُسمح بالكاميرا. اسمح بها من إعدادات المتصفح ثم أعد المحاولة.'
          : e && e.name === 'NotFoundError' ? 'لم نجد كاميرا في هذا الجهاز.'
          : 'تعذّر تشغيل الكاميرا أو تحميل نموذج التعرّف على الوضعية. تحقّق من الاتصال وأعد المحاولة.';
      }
    },

    stop() {
      cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach(t => t.stop());
      stream = null; lastT = -1; this.state = 'idle'; this.pose = 'none'; this.clearTimer();
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

    /* الوضعية ثابتة 700ms ← «أحسنت». بعد إتمام الخطوة، الوصول إلى وضعية الخطوة التالية ينقل إليها. */
    track() {
      if (this.done) return;
      const waiting = this.s.pose && !this.hit, j = waiting ? this.i : this.ahead;
      if (j < 0 || this.pose !== this.steps[j].pose) { since = 0; return; }
      if (!since) { since = performance.now(); return; }
      if (performance.now() - since < 700) return;
      since = 0;
      if (j !== this.i) { this.clearTimer(); this.i = j; }
      this.hit = true; this.say(this.s.praise);
      this.startTimer();
    },
  };
}
