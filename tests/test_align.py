import json

from app.pipeline.align import Unit, align, build_units, compose, units_to_links


def test_one_to_one():
    assert build_units({0: {0}, 1: {1}}, 2, 2) == [Unit((0,), (0,)), Unit((1,), (1,))]


def test_merge_and_drop():
    # الملخص يدمج الجملتين 0 و1، والجملة 2 محذوفة
    assert build_units({0: {0, 1}}, 3, 1) == [Unit((0, 1), (0,)), Unit((2,), ())]


def test_split_and_add():
    # جملة الأم 0 قُسمت إلى جملتين، وجملة 2 في الابن مضافة
    units = build_units({0: {0}, 1: {0}}, 1, 3)
    assert Unit((0,), (0, 1)) in units and Unit((), (2,)) in units


def test_out_of_range_indices_ignored():
    assert build_units({0: {0, 9}, 7: {0}}, 1, 1) == [Unit((0,), (0,))]


def test_compose_through_chain():
    # الأصل(2 جمل) ← ترجمة 1:1 ← ملخص يدمجهما
    trans = units_to_links(build_units({0: {0}, 1: {1}}, 2, 2))
    summ = units_to_links(build_units({0: {0, 1}}, 2, 1))
    assert compose(summ, trans) == {0: {0, 1}}


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def complete_json(self, prompt, schema, **kw):
        self.prompts.append(prompt)
        return schema.model_validate_json(json.dumps(self.reply))


def test_align_trivial_skips_llm():
    llm = FakeLLM({})
    assert align(llm, ["a"], ["b"], "ar", "en") == [Unit((0,), (0,))]
    assert llm.prompts == []


def test_align_uses_llm_pairs():
    llm = FakeLLM({"pairs": [{"version": [0], "parent": [0, 1]}], "dropped_parent": [2], "added_version": []})
    units = align(llm, ["s0", "s1", "s2"], ["v0"], "ar", "en")
    assert units == [Unit((0, 1), (0,)), Unit((2,), ())]
    assert "[2] s2" in llm.prompts[0]
