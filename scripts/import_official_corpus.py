"""يبني المدونة الرسمية لمِرآة من مصادرها، دون أي نص من ذاكرة نموذج:

- القرآن: مصحف المدينة النبوية من «منصة مطوري برمجيات القرآن الكريم» في مجمع الملك فهد لطباعة المصحف الشريف
  (kfgqpc_hafs_v30.zip): النص العثماني للعرض، والنص الإملائي للمطابقة.
- ترجمة معاني القرآن بالإنجليزية: Saheeh International من واجهة QuranEnc (موسوعة القرآن الكريم).
- الحديث: «موسوعة الأحاديث النبوية» HadeethEnc: المتن، والحكم، والتخريج، والترجمة الإنجليزية.

الاستخدام:
    python scripts/import_official_corpus.py --cache <مجلد> --quran-zip <مسار kfgqpc_hafs_v30.zip>

كل ما يُنزَّل يُحفظ في --cache فلا يُعاد طلبه، ويُكتب الناتج إلى data/corpus/quran_kfgqpc.jsonl و hadith_hadeethenc.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corpus"
QURANENC = "https://quranenc.com/api/v1/translation/sura/english_saheeh/{sura}"
HADEETH_ROOTS = "https://hadeethenc.com/api/v1/categories/roots/?language=ar"
HADEETH_LIST = "https://hadeethenc.com/api/v1/hadeeths/list/?language=ar&category_id={cat}&page={page}&per_page=100"
HADEETH_ONE = "https://hadeethenc.com/api/v1/hadeeths/one/?language={lang}&id={id}"
HADEETH_PAGE = "https://hadeethenc.com/ar/browse/hadith/{id}"
UA = {"User-Agent": "MIRAAH corpus import (hackathon project; local verification corpus)"}

QURAN_LICENSE = ("النص من «منصة مطوري برمجيات القرآن الكريم» في مجمع الملك فهد لطباعة المصحف الشريف (kfgqpc_hafs_v30)، "
                 "منقول دون تعديل: العثماني للعرض والإملائي (text_match) للمطابقة. الترجمة: Saheeh International من QuranEnc.com "
                 "دون تعديل، وحُذفت علامات الحواشي [n] فقط.")
HADITH_LICENSE = ("من «موسوعة الأحاديث النبوية» HadeethEnc.com، منقول دون تعديل (سوى حذف علامة @ التي تضعها الموسوعة قبل موضع الشاهد): المتن والحكم والتخريج من النسخة العربية، "
                  "والترجمة من النسخة الإنجليزية للموسوعة. المتون ملك عام، والترجمة والحكم والتخريج لأصحابها مع الإسناد.")
# الأحكام في الموسوعة ← درجات المدونة. ما لا يُعرف يُترك خارج المدونة ولا يُخمَّن.
GRADES = {"صحيح": "sahih", "حسن": "hasan", "ضعيف": "daif", "موضوع": "mawdu"}


def grade_of(text: str) -> str | None:
    t = (text or "").strip()
    for ar, g in GRADES.items():
        if t.startswith(ar):  # «صحيح لغيره»، «حسن صحيح»… تبدأ بالدرجة
            return g
    return None


def get_json(client: httpx.Client, url: str, cache: Path, tries: int = 4):
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    for n in range(tries):
        try:
            r = client.get(url, timeout=60)
            if r.status_code == 200:
                cache.write_text(r.text, encoding="utf-8")
                return r.json()
            if r.status_code == 404:  # لا ترجمة لهذا الحديث بهذه اللغة: جواب نهائي، لا يُعاد طلبه
                cache.write_text("null", encoding="utf-8")
                return None
        except httpx.HTTPError:
            pass
        time.sleep(2 * (n + 1))
    raise RuntimeError(f"تعذّر: {url}")


def build_quran(zip_path: Path, cache: Path, client: httpx.Client) -> int:
    z = zipfile.ZipFile(zip_path)
    ayat = json.loads(z.read("kfgqpc_hafs_v30-data/kfgqpc_hafs_v30.json").decode("utf-8-sig"))
    assert len(ayat) == 6236, len(ayat)
    (cache / "quranenc").mkdir(parents=True, exist_ok=True)
    en: dict[tuple[int, int], str] = {}
    for sura in range(1, 115):
        for v in get_json(client, QURANENC.format(sura=sura), cache / "quranenc" / f"{sura}.json")["result"]:
            en[(int(v["sura"]), int(v["aya"]))] = re.sub(r"\[\d+\]", "", v["translation"]).strip()
    with open(OUT / "quran_kfgqpc.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for a in ayat:
            s, n = int(a["sura_no"]), int(a["aya_no"])
            f.write(json.dumps({
                "id": f"q-{s}-{n}-kfgqpc", "type": "quran",
                "text_ar": re.sub(r"\s*۝[٠-٩]+\s*$", "", a["aya_text_unicode"]).strip(),
                "text_match": a["aya_text_emlaey"], "text_en": en[(s, n)], "grade": None,
                "source_name": f"القرآن الكريم، سورة {a['sura_name_ar']} {s}:{n} — مصحف المدينة النبوية (مجمع الملك فهد)؛ الترجمة: Saheeh International",
                "source_url": f"https://quranenc.com/ar/browse/english_saheeh/{s}#{n}",
                "license_note": QURAN_LICENSE,
            }, ensure_ascii=False) + "\n")
    return len(ayat)


def build_hadith(cache: Path, client: httpx.Client, workers: int = 4) -> tuple[int, dict]:
    (cache / "hadeethenc").mkdir(parents=True, exist_ok=True)
    ids: list[str] = []
    for root in get_json(client, HADEETH_ROOTS, cache / "hadeethenc" / "roots.json"):
        page, last = 1, 1
        while page <= last:
            d = get_json(client, HADEETH_LIST.format(cat=root["id"], page=page),
                         cache / "hadeethenc" / f"list-{root['id']}-{page}.json")
            last = int(d["meta"]["last_page"])
            ids += [x["id"] for x in d["data"]]
            page += 1
    ids = list(dict.fromkeys(ids))
    print(f"HadeethEnc: {len(ids)} حديثاً بلا تكرار", flush=True)

    def fetch(i_lang):
        i, lang = i_lang
        try:
            return i, lang, get_json(client, HADEETH_ONE.format(lang=lang, id=i), cache / "hadeethenc" / f"{lang}-{i}.json")
        except RuntimeError:
            return i, lang, None

    rec: dict[tuple[str, str], dict | None] = {}
    jobs = [(i, lang) for i in ids for lang in ("ar", "en")]
    with ThreadPoolExecutor(workers) as ex:
        for k, (i, lang, d) in enumerate(ex.map(fetch, jobs), 1):
            rec[(i, lang)] = d
            if k % 500 == 0:
                print(f"  {k}/{len(jobs)}", flush=True)

    skipped = {"no_arabic": 0, "unknown_grade": 0}
    written = 0
    with open(OUT / "hadith_hadeethenc.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i in ids:
            ar, en = rec.get((i, "ar")), rec.get((i, "en"))
            if not ar or not ar.get("hadeeth"):
                skipped["no_arabic"] += 1
                continue
            g = grade_of(ar.get("grade", ""))
            if g is None:
                skipped["unknown_grade"] += 1
                continue
            ref = " · ".join(x.strip() for x in (ar.get("reference") or "").splitlines()[:2] if x.strip())
            f.write(json.dumps({
                "id": f"h-he-{i}", "type": "hadith", "text_ar": ar["hadeeth"].replace("@", "").strip(),
                "text_en": (en or {}).get("hadeeth", "").strip(), "grade": g,
                "source_name": f"{ar.get('attribution', '').strip()} ({ar.get('grade', '').strip()})"
                               + (f" — {ref}" if ref else "") + f" — موسوعة الأحاديث النبوية رقم {i}",
                "source_url": HADEETH_PAGE.format(id=i), "license_note": HADITH_LICENSE,
            }, ensure_ascii=False) + "\n")
            written += 1
    return written, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--quran-zip", type=Path, required=True)
    ap.add_argument("--only", choices=["quran", "hadith"])
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    a.cache.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=UA, follow_redirects=True) as client:
        if a.only in (None, "quran"):
            print("القرآن:", build_quran(a.quran_zip, a.cache, client), "آية", flush=True)
        if a.only in (None, "hadith"):
            n, skipped = build_hadith(a.cache, client)
            print("الحديث:", n, "حديثاً · استُبعد:", skipped, flush=True)


if __name__ == "__main__":
    main()
