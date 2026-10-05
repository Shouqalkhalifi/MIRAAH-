"""6.2 بصمة المعنى.

النموذج يستخرج البصمة بقيم إنجليزية ثابتة، ثم نعيد حساب النفي والأرقام **بالقواعد** ونستبدل بها قيم
النموذج. ونطلب اقتباساً حرفياً لكل شرط واستثناء، ولا نقبله إلا إن وُجد فعلاً في النص (لا اختلاق).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, Field

from app.models import MeaningFingerprint
from app.text.normalize import normalize_ar

# ---------- النفي بالقواعد ----------
_NEG_AR = {"لا", "لم", "لن", "ليس", "ليست", "لست", "لسنا", "ليسوا", "لستم", "غير", "بلا"}
_NEG_EN = {"not", "no", "never", "none", "nor", "neither", "cannot", "without", "nobody", "nothing"}
_NEG_FR = {"sans", "jamais"}
_FR_NEG_PARTNERS = {"pas", "jamais", "plus", "rien", "aucun", "aucune", "personne", "point"}
_NEG_HI = {unicodedata.normalize("NFKC", w) for w in ("नहीं", "न", "मत", "बिना")}
# الهندية: علامات الحركات (मात्रा) ليست من \w في re، فتُضمّ كتلة الديفاناغاري كلها وإلا انقسمت «नहीं» إلى «नह»
_WORD = re.compile(r"[\w'\u0900-\u097F]+", re.UNICODE)


def _strip_ar_prefix(tok: str, vocab) -> str:
    """يزيل و/ف/ب/ل الملتصقة إن كان الباقي في المعجم (ولا، فلم، بلا، لغير...)."""
    if tok in vocab:
        return tok
    for pre in ("وب", "ول", "فل", "و", "ف", "ب", "ل"):
        rest = tok[len(pre):]
        if tok.startswith(pre) and len(rest) >= 2 and rest in vocab:
            return rest
    return tok


def count_negations(text: str) -> int:
    t = normalize_ar(text).replace("’", "'")
    toks = _WORD.findall(t)
    fr_ne = sum(1 for tok in toks if tok == "ne" or tok.startswith("n'"))  # ne ... pas/jamais = نفي واحد
    if fr_ne and "que" in toks and not _FR_NEG_PARTNERS & set(toks):
        fr_ne = 0  # «ne ... que» حصر بمعنى "only"، لا نفي
    n = fr_ne
    # النفي الذي يليه استثناء أو غاية قيدٌ لا نفي: «لا ... إلا/حتى» / "not ... except|unless|until"
    # (يقابلها "only ... / only when")، فتُترجم إحداهما بالأخرى دون أن يتغيّر المعنى
    pending_ar = pending_en = 0
    for tok in toks:
        if tok.endswith("n't") or tok in _NEG_EN or tok in _NEG_HI:
            n += 1
            pending_en += 1
        elif tok in ("except", "unless", "until") and pending_en:
            n -= 1
            pending_en -= 1
        elif tok == "sans" or (tok == "jamais" and not fr_ne):
            n += 1
        elif tok in ("الا", "سوي", "حتي") and pending_ar:
            n -= 1
            pending_ar -= 1
        elif _strip_ar_prefix(tok, _NEG_AR) in _NEG_AR or (tok == "ما" and "الا" in toks):
            n += 1
            pending_ar += 1
    return n


# ---------- الأرقام بالقواعد ----------
_NUM_WORDS = {
    # العربية (بعد التطبيع: ة←ه، أ←ا). «واحد» مستبعد لكثرة استعماله غير العددي.
    "اثنان": 2, "اثنين": 2, "اثنتان": 2, "اثنتين": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4,
    "خمس": 5, "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثماني": 8, "ثمانيه": 8,
    "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10, "عشرون": 20, "عشرين": 20, "ثلاثون": 30, "ثلاثين": 30,
    "اربعون": 40, "اربعين": 40, "مائه": 100, "مئه": 100, "الف": 1000,
    # الإنجليزية («one» مستبعد: no one / one should)
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
    "thousand": 1000,
    # الفرنسية («un/une» مستبعدان لأنهما أداتا تنكير)
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "onze": 11, "douze": 12, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "cent": 100,
    "mille": 1000,
}
# الهندية («एक» مستبعد لأنه أداة تنكير أيضاً). المفاتيح بعد NFKC كالنص، فالنقطة (़) في «हज़ार» تنفصل في الطرفين
_NUM_WORDS.update({unicodedata.normalize("NFKC", w): n for w, n in {
    "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "बीस": 20, "तीस": 30, "चालीस": 40, "पचास": 50, "सौ": 100, "हज़ार": 1000, "हजार": 1000,
}.items()})
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> list[str]:
    t = normalize_ar(text)
    nums = [d.replace(",", ".") for d in _DIGITS.findall(t)]
    for tok in _WORD.findall(_DIGITS.sub(" ", t)):
        tok = _strip_ar_prefix(tok, _NUM_WORDS)
        if tok in _NUM_WORDS:
            nums.append(str(_NUM_WORDS[tok]))
    return sorted(nums, key=lambda x: (float(x), x))


# ---------- الاستخراج بالنموذج ----------
SYSTEM_FP = """You extract a "meaning fingerprint" from a short passage of Islamic content (Arabic, English, French or another language). The fingerprint records meaning-critical invariants so that versions of the same passage in different languages can be compared field by field. All values must be in English whatever the passage language.

Describe ONLY what the passage itself says. Never add knowledge, rulings, sources, grades or context from memory. If a field is not expressed, use its empty/none value.

Fields:
- attribution.to: who the passage attributes its statement to: "allah" (Quran / Allah said), "prophet" (the Prophet ﷺ said or did), "companion", "scholar" (an imam, a named or unnamed scholar, "some scholars", a proverb or saying of the predecessors), "religion" (the statement is presented as the position of Islam itself: الإسلام يحرّم، في الإسلام، الشريعة تقول، "Islam forbids", "in Islam"), "author" (the writer's own statement, not attributed to anyone), "none".
- attribution.form: "tamrid" when the attribution uses weakening/reporting wording (رُوي، يُروى، قيل، يُذكر، يُحكى، "it is reported", "it is said", "reportedly"); "assertive" when attributed directly (قال، ثبت، صح، "said", "it is established", or a plain statement of fact about the person); "none" when attribution.to is "author" or "none".
- claim: one short neutral English paraphrase of the core statement (max 15 words).
- ruling: the legal category stated by the wording: يجب/فرض/must/obligatory -> "obligatory"; يستحب/يسن/recommended -> "recommended"; يجوز/يباح/may/permissible -> "permissible"; يكره/disliked -> "disliked"; يحرم/لا يجوز/forbidden/must not -> "forbidden"; otherwise "none".
- scope.quantifier: "all" (everyone, all Muslims, كل), "some" (بعض, some people), "specific" (a specific group or person: the traveler, women, the imam), "unspecified".
- scope.restricted_to: the group the statement is limited to, 1-3 lowercase English words (e.g. "travelers"), else null.
- conditions: every condition or restriction on when/for whom the statement holds, as short lowercase English phrases in the simplest common words (e.g. "person is traveling", "if able"). A restriction of WHO it applies to (e.g. "للمسافر", "for the traveler") is ALSO listed as a condition. A general subject such as "muslims" or "people" is NOT a condition. A relative clause that merely identifies or describes an object (e.g. "ما أفطره من أيام" / "the days he missed") is NOT a condition.
- exceptions: explicit exceptions (إلا، سوى، غير، except, unless) as short lowercase English phrases. Do not list the exclusive "only" of a restriction (hasr) as an exception.
- certainty: how certain the passage presents its claim: "definite" (asserted as fact or firm rule), "probable" (الأرجح، الأظهر، likely), "possible" (قد، ربما، يحتمل، perhaps, may possibly), "unstated" (reported without commitment, e.g. after رُوي / قيل).
- restriction_hasr: true if the passage uses an exclusive restriction (إنما، ما ... إلا، لا ... إلا، "only", "nothing but").
- negations: number of negation words.
- numbers: every number in the passage as digit strings.
- quran_refs: Quran references explicitly cited in the passage (e.g. "2:185"), else [].
- hadith_mentions: each hadith quoted or mentioned: a short verbatim snippet and grade_stated only if the passage itself states the grade, else "none".
- consensus_claim: "ijma" (إجماع، consensus, all scholars agree), "majority" (الجمهور، most scholars), "some_scholars" (بعض العلماء، some scholars), else "none".
- disagreement_stated: true if the passage says scholars differ or the issue is disputed (اختلف العلماء، في المسألة خلاف، قولان، "scholars differ", "there is disagreement"), else false.
- key_terms: important Islamic terms used, lowercase transliteration (e.g. "sunnah", "makruh", "qada").

Also return condition_quotes and exception_quotes: for each item of conditions / exceptions (same order), the exact substring of the passage that expresses it, copied verbatim in the passage language; null if there is none.

Example 1 passage (ar): يجوز للمسافر أن يفطر في رمضان.
Example 1 output: {"fingerprint": {"attribution": {"to": "author", "form": "none"}, "claim": "a traveler may break the fast in ramadan", "ruling": "permissible", "scope": {"quantifier": "specific", "restricted_to": "travelers"}, "conditions": ["person is traveling"], "exceptions": [], "certainty": "definite", "restriction_hasr": false, "negations": 0, "numbers": [], "quran_refs": [], "hadith_mentions": [], "consensus_claim": "none", "key_terms": ["ramadan"]}, "condition_quotes": ["للمسافر"], "exception_quotes": []}

Example 2 passage (en): It is reported that some scholars said the prayer is only valid with purification.
Example 2 output: {"fingerprint": {"attribution": {"to": "scholar", "form": "tamrid"}, "claim": "prayer is valid only with purification", "ruling": "none", "scope": {"quantifier": "unspecified", "restricted_to": null}, "conditions": ["person has purification"], "exceptions": [], "certainty": "unstated", "restriction_hasr": true, "negations": 0, "numbers": [], "quran_refs": [], "hadith_mentions": [], "consensus_claim": "some_scholars", "key_terms": ["salah", "taharah"]}, "condition_quotes": ["with purification"], "exception_quotes": []}

Example 3 passage (fr): Le Prophète ﷺ a dit : « Facilitez et ne rendez pas les choses difficiles. »
Example 3 output: {"fingerprint": {"attribution": {"to": "prophet", "form": "assertive"}, "claim": "make things easy and do not make them difficult", "ruling": "none", "scope": {"quantifier": "unspecified", "restricted_to": null}, "conditions": [], "exceptions": [], "certainty": "definite", "restriction_hasr": false, "negations": 1, "numbers": [], "quran_refs": [], "hadith_mentions": [{"snippet": "Facilitez et ne rendez pas les choses difficiles", "grade_stated": "none"}], "consensus_claim": "none", "key_terms": []}, "condition_quotes": [], "exception_quotes": []}"""


class FingerprintLLM(BaseModel):
    fingerprint: MeaningFingerprint
    condition_quotes: list[Optional[str]] = Field(default_factory=list)
    exception_quotes: list[Optional[str]] = Field(default_factory=list)


class Fingerprinted(BaseModel):
    """البصمة بعد التصحيح بالقواعد، مع اقتباسات متحقَّق منها (None إن لم توجد في النص)."""
    fp: MeaningFingerprint
    condition_quotes: list[Optional[str]] = Field(default_factory=list)
    exception_quotes: list[Optional[str]] = Field(default_factory=list)
    lang: str = ""  # لغة النص: العدّ بالقواعد لا يُقارن بين لغتين إلا بحذر


def verify_quote(quote: Optional[str], text: str) -> Optional[str]:
    """يقبل الاقتباس فقط إن كان موجوداً حرفياً (بعد التطبيع) في النص، ويعيده كما ورد في النص."""
    if not quote or not quote.strip():
        return None
    q = quote.strip()
    if q in text:
        return q
    nq, nt = normalize_ar(q), normalize_ar(text)
    return q if nq and nq in nt else None


def _align_quotes(quotes: list[Optional[str]], n: int, text: str) -> list[Optional[str]]:
    quotes = (list(quotes) + [None] * n)[:n]
    return [verify_quote(q, text) for q in quotes]


def apply_rules(raw: FingerprintLLM, text: str) -> Fingerprinted:
    fp = raw.fingerprint.model_copy(deep=True)
    fp.negations = count_negations(text)
    fp.numbers = extract_numbers(text)
    return Fingerprinted(
        fp=fp,
        condition_quotes=_align_quotes(raw.condition_quotes, len(fp.conditions), text),
        exception_quotes=_align_quotes(raw.exception_quotes, len(fp.exceptions), text),
    )


def fingerprint(llm, text: str, lang: str, role: str = "main") -> Fingerprinted:
    prompt = f"Passage ({lang}):\n<<<\n{text}\n>>>"
    raw = llm.complete_json(prompt, FingerprintLLM, system=SYSTEM_FP, role=role, purpose="fingerprint")
    out = apply_rules(raw, text)
    out.lang = lang
    return out


# ---------- تحقق موجّه: هل ما زال الشرط/الاستثناء موجوداً في النسخة؟ ----------
SYSTEM_PRESENCE = """You check whether one specific meaning element taken from a parent text (a condition, an exception, or a locked element such as a certainty word, an attribution form, a hadith grade, or a term) is still expressed in a derived version (a translation or summary), possibly in different words or another language.

Answer present=true ONLY if the version itself clearly expresses the same meaning element: the same restriction on when, for whom or except whom the statement holds; the same degree of certainty; the same attribution form (e.g. "it is reported" vs. a direct assertion); the same grade; the same term sense. Similar topic is not enough.
If present, copy into quote the exact substring of the version that expresses it, verbatim. If not present, quote is null."""


class Presence(BaseModel):
    present: bool
    quote: Optional[str] = None


def find_in_version(llm, item: str, kind: str, parent_text: str, version_text: str, version_lang: str,
                    role: str = "main") -> Optional[str]:
    """يعيد اقتباساً متحقَّقاً منه من النسخة إن كان الشرط/الاستثناء ما زال فيها، وإلا None.

    لا يُقبل «موجود» بلا اقتباس حرفي موجود فعلاً في النص، حتى لا نُخفي سقوطاً حقيقياً.
    """
    prompt = (f"{kind.upper()} (from the parent): {item}\n\n"
              f"PARENT TEXT:\n<<<\n{parent_text}\n>>>\n\n"
              f"VERSION ({version_lang}):\n<<<\n{version_text}\n>>>")
    res = llm.complete_json(prompt, Presence, system=SYSTEM_PRESENCE, role=role, purpose="presence")
    return verify_quote(res.quote, version_text) if res.present else None
