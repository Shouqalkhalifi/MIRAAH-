from app.models import AlertType as T
from app.models import MeaningFingerprint
from app.pipeline.chain import analyze_chain
from app.pipeline.fingerprint import Fingerprinted
from app.pipeline.rules import Hit
from app.pipeline.witnesses import agreement, reconcile
from tests.test_chain import THREE_LINKS, by_type, chain_report, fake_align, fake_fp


def F(**kw):
    return Fingerprinted(fp=MeaningFingerprint.model_validate(kw))


def test_agreement_on_impactful_fields_only():
    a, b = F(ruling="permissible", claim="x"), F(ruling="permissible", claim="different wording")
    assert agreement([(a, b)]) == 1.0
    assert agreement([(a, b), (F(ruling="obligatory"), F(ruling="recommended"))]) == 0.5
    assert agreement([]) is None


def test_reconcile_marks_agreement_and_b_only_hits():
    ha = [Hit(T.condition_dropped, "conditions", "x", "", match_key="person is traveling"),
          Hit(T.ruling_shift, "ruling", "a", "b")]
    hb = [Hit(T.condition_dropped, "conditions", "x", "", match_key="traveller"),
          Hit(T.certainty_raised, "certainty", "possible", "definite")]
    ok, only_b = reconcile(ha, hb)
    assert ok == {0: True, 1: False}
    assert [h.type for h in only_b] == [T.witness_disagreement] and only_b[0].before == "رفع اليقين"


def test_two_witnesses_through_chain():
    def witness_b(text, lang):  # الشاهد الثاني يقرأ حكم الملخص «واجباً» فيختلف مع الأول
        fp = fake_fp(text, lang)
        if "Muslims" in text:
            fp = Fingerprinted(fp=fp.fp.model_copy(update={"ruling": "obligatory"}))
        return fp

    stats = {}
    alerts = analyze_chain(chain_report(THREE_LINKS), fake_align, fake_fp, witness_fp_fn=witness_b, stats=stats)
    a = by_type(alerts)
    assert a[T.condition_dropped].witnesses_agree is True
    assert a[T.witness_disagreement].severity.value == "yellow"
    assert "تغيّر الحكم" in a[T.witness_disagreement].explanation_ar
    assert 0 < stats["agreement"] < 1 and stats["compared"] > 0


def test_single_witness_leaves_agreement_unset():
    stats = {}
    alerts = analyze_chain(chain_report(THREE_LINKS), fake_align, fake_fp, stats=stats)
    assert stats["agreement"] is None and all(a.witnesses_agree is None for a in alerts)


def test_scope_seen_only_by_witness_b_is_not_an_alert():
    ok, only_b = reconcile([], [Hit(T.scope_narrowed, "scope", "unspecified", "specific")])
    assert only_b == []
