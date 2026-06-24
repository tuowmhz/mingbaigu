"""跌倒体质测试：打分与人格映射。"""
from app.profile_quiz import ARCHETYPES, QUESTIONS, get_quiz, score_quiz


def _answers(picker) -> dict:
    """picker(question) -> option index"""
    return {q["id"]: picker(q) for q in QUESTIONS}


def _safe_index(q) -> int:
    """每题选权重为空的'清醒'选项。"""
    for i, o in enumerate(q["options"]):
        if not o["w"]:
            return i
    return 0


class TestQuiz:
    def test_questions_complete(self):
        quiz = get_quiz()
        assert len(quiz["questions"]) == 12
        for q in QUESTIONS:
            assert len(q["options"]) >= 3
            assert any(not o["w"] for o in q["options"]), f"{q['id']} 缺中性选项"

    def test_disciplined_answers_yield_monk(self):
        result = score_quiz(_answers(_safe_index))
        assert result["archetype"]["key"] == "monk"
        assert result["top_pitfalls"] == []

    def test_fomo_answers_yield_chaser(self):
        def fomo(q):
            # 纯追风人格：有 FOMO 选项就选，没有就保持清醒（选中性项）
            best, best_w = _safe_index(q), 0
            for i, o in enumerate(q["options"]):
                w = sum(o["w"].get(k, 0) for k in ("chase_hot", "tips", "guru", "narrative"))
                if w > best_w:
                    best, best_w = i, w
            return best
        result = score_quiz(_answers(fomo))
        assert result["archetype"]["key"] == "chaser"
        assert any(t["id"] in ("chase_hot", "tips", "guru") for t in result["top_pitfalls"])

    def test_share_text_has_brand(self):
        result = score_quiz(_answers(lambda q: 0))
        assert "mingbaigu.com" in result["share_text"]

    def test_incomplete_answers_rejected(self):
        partial = {q["id"]: 0 for q in QUESTIONS[:5]}
        assert "error" in score_quiz(partial)

    def test_all_archetype_ids_valid(self):
        from app.failures import FAILURES
        valid = {f["id"] for f in FAILURES}
        for a in ARCHETYPES:
            assert set(a["ids"]) <= valid, f"{a['key']} 引用了不存在的死法"
