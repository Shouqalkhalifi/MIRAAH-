from app.models import Alert, ContentLevel, Severity, Span
from app.models import AlertType as T
from app.pipeline.severity import TIERS, apply_severity, needs_referral


def A(t, sev, idx=0):
    return Alert(type=t, severity=sev, version_label="v", explanation_ar="x",
                 source_span=Span(text="s"), source_sentence_indices=[idx])


def test_every_alert_type_has_a_tier():
    assert set(TIERS) == set(T)


def test_order_attribution_then_ruling_then_conditions_then_terms_then_style():
    alerts = [A(T.length_drop, Severity.info), A(T.term_narrowing, Severity.yellow),
              A(T.condition_dropped, Severity.red), A(T.ruling_shift, Severity.red),
              A(T.new_prophetic_attribution, Severity.red), A(T.scope_widened, Severity.yellow)]
    out = [a.type for a in apply_severity(alerts, ContentLevel.B)]
    assert out == [T.new_prophetic_attribution, T.ruling_shift, T.condition_dropped,
                   T.scope_widened, T.term_narrowing, T.length_drop]


def test_level_a_raises_yellow_in_upper_tiers_only():
    out = {a.type: a for a in apply_severity(
        [A(T.scope_widened, Severity.yellow), A(T.term_narrowing, Severity.yellow), A(T.length_drop, Severity.info)],
        ContentLevel.A)}
    assert out[T.scope_widened].severity == Severity.red
    assert any("مستوى المحتوى A" in e.detail for e in out[T.scope_widened].evidence)
    assert out[T.term_narrowing].severity == Severity.yellow
    assert out[T.length_drop].severity == Severity.info


def test_level_b_keeps_defaults():
    assert apply_severity([A(T.scope_widened, Severity.yellow)], ContentLevel.B)[0].severity == Severity.yellow


def test_referral_only_for_d():
    assert needs_referral(ContentLevel.D) and not needs_referral(ContentLevel.A)
