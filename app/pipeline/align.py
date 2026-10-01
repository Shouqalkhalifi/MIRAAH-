"""6.1 محاذاة جمل النسخة بجمل حلقتها الأم.

استدعاء نموذج واحد يعيد JSON يربط كل جملة في النسخة بجملة أو أكثر في الأم، ثم نحوّل الأزواج إلى
«وحدات محاذاة» عبر المكوّنات المترابطة (تدعم الدمج والتقسيم). الجملة بلا مقابل = محذوفة أو مضافة.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

SYSTEM_ALIGN = """You align the sentences of a derived version (a translation or a summary) to the sentences of its parent text, by meaning.

Rules:
- Each version sentence maps to the parent sentence(s) whose meaning it carries. A summary sentence may merge several parent sentences; one parent sentence may be split into several version sentences.
- Partial or distorted correspondence still counts as aligned: do NOT judge correctness, only which sentences correspond.
- A parent sentence whose meaning is completely absent from the version is "dropped".
- A version sentence with no counterpart at all in the parent is "added".
- Use the 0-based indices shown. Every index must appear in exactly one place: in a pair, in dropped_parent, or in added_version."""


class AlignPair(BaseModel):
    version: list[int] = Field(min_length=1)
    parent: list[int] = Field(min_length=1)


class AlignmentLLM(BaseModel):
    pairs: list[AlignPair] = Field(default_factory=list)
    dropped_parent: list[int] = Field(default_factory=list)
    added_version: list[int] = Field(default_factory=list)


@dataclass(frozen=True)
class Unit:
    """وحدة محاذاة: جمل في الأم ↔ جمل في الابن. أحد الطرفين قد يكون فارغاً (محذوف/مضاف)."""
    parent: tuple[int, ...]
    child: tuple[int, ...]


@dataclass
class _UF:
    parent: dict = field(default_factory=dict)

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def build_units(links: dict[int, set[int]], n_parent: int, n_child: int) -> list[Unit]:
    """links: رقم جملة الابن ← مجموعة أرقام جمل الأم. يعيد وحدات مرتبة بأول جملة في الأم."""
    uf = _UF()
    for i in range(n_parent):
        uf.find(("p", i))
    for j in range(n_child):
        uf.find(("c", j))
    for j, ps in links.items():
        for i in ps:
            if 0 <= i < n_parent and 0 <= j < n_child:
                uf.union(("c", j), ("p", i))
    groups: dict = {}
    for node in list(uf.parent):
        groups.setdefault(uf.find(node), []).append(node)
    units = []
    for nodes in groups.values():
        p = tuple(sorted(i for k, i in nodes if k == "p"))
        c = tuple(sorted(j for k, j in nodes if k == "c"))
        units.append(Unit(p, c))
    return sorted(units, key=lambda u: (u.parent[0] if u.parent else 10**6, u.child[0] if u.child else -1))


def units_to_links(units: list[Unit]) -> dict[int, set[int]]:
    return {c: set(u.parent) for u in units for c in u.child}


def compose(child_to_parent: dict[int, set[int]], parent_to_source: dict[int, set[int]]) -> dict[int, set[int]]:
    """يركّب المحاذاة: جملة الابن ← جمل الأصل عبر الحلقة الأم."""
    out: dict[int, set[int]] = {}
    for c, ps in child_to_parent.items():
        out[c] = set().union(*(parent_to_source.get(p, set()) for p in ps)) if ps else set()
    return out


def _render(sents: list[str]) -> str:
    return "\n".join(f"[{i}] {s}" for i, s in enumerate(sents))


def align(llm, parent_sents: list[str], child_sents: list[str], parent_lang: str, child_lang: str) -> list[Unit]:
    if len(parent_sents) == 1 and len(child_sents) == 1:
        return [Unit((0,), (0,))]
    prompt = (f"PARENT ({parent_lang}):\n{_render(parent_sents)}\n\n"
              f"VERSION ({child_lang}):\n{_render(child_sents)}")
    res = llm.complete_json(prompt, AlignmentLLM, system=SYSTEM_ALIGN, purpose="align")
    links: dict[int, set[int]] = {}
    for pair in res.pairs:
        for j in pair.version:
            links.setdefault(j, set()).update(pair.parent)
    return build_units(links, len(parent_sents), len(child_sents))
