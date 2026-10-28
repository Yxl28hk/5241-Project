"""Quiz bank and playability rules; pure functions, no database required."""

from collections import Counter

import json
from types import SimpleNamespace

import pytest

from app.quiz.content import (
    DRAW_QUOTA,
    LEGACY_CODES,
    LEVEL_COUNT,
    MISSION_ID,
    MISSION_IDS,
    QUESTIONS_PER_LEVEL,
    REVENGE_MAX,
    TOTAL_QUESTIONS,
    bank_version,
    judge,
    persona_for,
    question_rows,
    suggested_level,
    valid_choice,
)
from app.quiz import service
from app.quiz.content import MISSION_IDS
from app.quiz.service import _streak, draw_questions, pick_count, run_questions

MODE_TOTAL = {"quest": TOTAL_QUESTIONS, "quick": 8, "revenge": REVENGE_MAX}
FIXED_MIX = {"concepts": 5, "ai-assistant": 5, "soft-skills": 4, "process": 4}


def test_bank_has_enough_questions_for_every_quota():
    rows = question_rows()
    assert len(rows) == 30
    for level, quota in DRAW_QUOTA.items():
        for topic, count in quota.items():
            available = sum(1 for r in rows if r["level"] == level and r["topic"] == topic)
            assert available >= count, f"L{level} {topic}: {available} < {count}"
    assert len(rows) // LEVEL_COUNT == 10


def test_codes_and_versions_are_unique():
    rows = question_rows()
    assert len({row["code"] for row in rows}) == len(rows)
    assert len({row["version"] for row in rows}) == len(rows)
    assert all(row["version"] == bank_version(row["code"]) for row in rows)
    assert all(row["version"].startswith("quiz-") for row in rows)


def test_every_question_is_well_formed():
    for row in question_rows():
        ids = [choice["id"] for choice in row["choices"]]
        assert len(ids) >= 2, row["code"]
        assert len(set(ids)) == len(ids), row["code"]
        assert row["kind"] in ("single", "multi", "order"), row["code"]
        for answer in row["correct_choice_id"].split(","):
            assert answer in ids, row["code"]
        assert set(row["explanations"]) == set(ids), row["code"]
        assert row["explanation"], row["code"]
        if row["kind"] == "multi":
            assert 2 <= len(row["correct_choice_id"].split(",")) < len(ids), row["code"]
        if row["kind"] == "order":
            assert set(row["correct_choice_id"].split(",")) == set(ids), row["code"]


def test_exactly_one_boss_on_the_last_level():
    bosses = [row for row in question_rows() if row["boss"]]
    assert len(bosses) == 1
    assert bosses[0]["level"] == LEVEL_COUNT
    assert bosses[0]["topic"] == "ai-assistant"


def test_quest_draw_is_random_but_keeps_the_topic_mix():
    pool = question_rows()
    orders = set()
    for _ in range(40):
        drawn = draw_questions(pool, "quest")
        assert drawn is not None
        assert len(drawn) == TOTAL_QUESTIONS
        assert drawn[-1]["boss"] is True
        assert Counter(q["topic"] for q in drawn) == FIXED_MIX
        assert [q["level"] for q in drawn] == sorted(q["level"] for q in drawn)
        orders.add(tuple(q["code"] for q in drawn))
    assert len(orders) > 1, "random draw must vary between runs"


def test_quest_draw_fills_every_level():
    pool = question_rows()
    drawn = draw_questions(pool, "quest")
    per_level = Counter(q["level"] for q in drawn)
    assert per_level == {level: QUESTIONS_PER_LEVEL for level in range(1, LEVEL_COUNT + 1)}


def test_quick_draw_has_eight_questions_and_no_boss():
    pool = question_rows()
    orders = set()
    for _ in range(40):
        drawn = draw_questions(pool, "quick")
        assert drawn is not None
        assert len(drawn) == MODE_TOTAL["quick"]
        assert not any(q.get("boss") for q in drawn)
        orders.add(tuple(q["code"] for q in drawn))
    assert len(orders) > 1


def test_draw_returns_none_when_the_pool_is_short():
    pool = [row for row in question_rows() if row["level"] != 1]
    assert draw_questions(pool, "quest") is None


def test_single_kind_scoring():
    question = {"kind": "single", "correct_choice_id": "a",
                "choices": [{"id": "a"}, {"id": "b"}]}
    assert judge(question, "a") is True
    assert judge(question, "b") is False
    assert valid_choice(question, "a") is True
    assert valid_choice(question, "z") is False
    assert valid_choice(question, "a,b") is False


def test_multi_kind_ignores_order_but_rejects_wrong_counts():
    question = {"kind": "multi", "correct_choice_id": "a,c",
                "choices": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]}
    assert judge(question, "a,c") is True
    assert judge(question, "c,a") is True
    assert judge(question, "a,b") is False
    # selecting everything must not be a free win
    assert valid_choice(question, "a,b,c,d") is False
    assert valid_choice(question, "a") is False
    assert valid_choice(question, "a,a") is False
    assert valid_choice(question, "a,c") is True


def test_order_kind_depends_on_sequence():
    question = {"kind": "order", "correct_choice_id": "b,c,a",
                "choices": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    assert judge(question, "b,c,a") is True
    assert judge(question, "a,b,c") is False
    assert valid_choice(question, "a,b") is False
    assert valid_choice(question, "a,b,c") is True


def test_pick_count_matches_kind():
    single = {"kind": "single", "correct_choice_id": "a", "choices": [{"id": "a"}, {"id": "b"}]}
    multi = {"kind": "multi", "correct_choice_id": "a,c",
             "choices": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]}
    order = {"kind": "order", "correct_choice_id": "b,a", "choices": [{"id": "a"}, {"id": "b"}]}
    assert pick_count(single) == 1
    assert pick_count(multi) == 2
    assert pick_count(order) == 2


def test_seeded_bank_is_scored_correctly_by_kind():
    """Every seeded question must accept its own correct answer and reject a wrong one."""
    for row in question_rows():
        assert judge(row, row["correct_choice_id"]) is True, row["code"]
        assert valid_choice(row, row["correct_choice_id"]) is True, row["code"]
        if row["kind"] == "single":
            wrong = next(c["id"] for c in row["choices"] if c["id"] != row["correct_choice_id"])
        elif row["kind"] == "multi":
            right = set(row["correct_choice_id"].split(","))
            others = [c["id"] for c in row["choices"] if c["id"] not in right]
            picked = (others + [c["id"] for c in row["choices"] if c["id"] in right])
            wrong = ",".join(picked[: len(right)])
        else:
            ids = [c["id"] for c in row["choices"]]
            wrong = ",".join(ids[1:] + ids[:1])
        assert valid_choice(row, wrong) is True, row["code"]
        assert judge(row, wrong) is False, row["code"]


def test_legacy_order_reproduces_the_v1_query_order():
    """Runs created before random draw must replay exactly what they answered."""
    level_of = {row["code"]: row["level"] for row in question_rows()}
    assert len(LEGACY_CODES) == TOTAL_QUESTIONS
    assert all(code in level_of for code in LEGACY_CODES)
    assert LEGACY_CODES == tuple(sorted(LEGACY_CODES, key=lambda c: (level_of[c], c)))


def test_run_without_frozen_codes_falls_back_to_the_legacy_order():
    pool = question_rows()
    row = {"answers": json.dumps({"mode": "quest", "items": []}), "step": 0}
    assert [q["code"] for q in run_questions(row, pool)] == list(LEGACY_CODES)


def test_run_with_frozen_codes_keeps_them():
    pool = question_rows()
    drawn = draw_questions(pool, "quest")
    codes = [q["code"] for q in drawn]
    row = {"answers": json.dumps({"mode": "quest", "codes": codes, "items": []}), "step": 0}
    assert [q["code"] for q in run_questions(row, pool)] == codes


def test_quick_and_revenge_use_separate_mission_ids():
    assert MISSION_IDS["quest"] == MISSION_ID == "level-quest-v1"
    assert len(set(MISSION_IDS.values())) == 3


@pytest.mark.parametrize("score,expected", [(18, "experienced"), (13, "experienced"),
                                           (10, "intermediate"), (8, "intermediate"),
                                           (7, "beginner"), (0, "beginner")])
def test_suggested_level_thresholds(score, expected):
    assert suggested_level(score, TOTAL_QUESTIONS) == expected


# ---------- Q1: correct answers must not sit on the same option ----------

def test_correct_answers_are_spread_across_options():
    rows = [row for row in question_rows() if row["kind"] == "single"]
    spread = Counter(row["correct_choice_id"] for row in rows)
    assert len(spread) >= 3, spread
    assert max(spread.values()) <= len(rows) / 2, spread
    biggest_share = max(spread.values()) / len(rows)
    assert biggest_share < 0.6, f"one option holds {biggest_share:.0%}"


def test_no_correct_answer_sits_outside_its_own_options():
    for row in question_rows():
        ids = [choice["id"] for choice in row["choices"]]
        assert set(row["correct_choice_id"].split(",")) <= set(ids), row["code"]


def test_shuffle_keeps_explanations_paired_with_options():
    """single/multi: the option that says 正确。 must be the correct one."""
    for row in question_rows():
        if row["kind"] == "order":
            # order explanations describe the position, not right vs wrong
            # ("回滚...但它排在保留证据之后"), so they carry no 正确 marker.
            # Their pairing is covered by test_seeded_bank_is_scored_correctly_by_kind.
            continue
        for answer in row["correct_choice_id"].split(","):
            assert row["explanations"][answer].startswith("正确。"), (
                row["code"], answer, row["explanations"][answer])
        wrong = [c["id"] for c in row["choices"] if c["id"] not in row["correct_choice_id"].split(",")]
        for answer in wrong:
            assert not row["explanations"][answer].startswith("正确。"), (row["code"], answer)


def test_multi_and_order_answers_are_not_degenerate():
    order = next(row for row in question_rows() if row["kind"] == "order")
    ids = [choice["id"] for choice in order["choices"]]
    assert order["correct_choice_id"] != ",".join(ids), "looks unshuffled"
    multis = [row for row in question_rows() if row["kind"] == "multi"]
    assert multis and all(2 <= len(r["correct_choice_id"].split(",")) for r in multis)


# ---------- A1 combo ----------

def test_streak_counts_trailing_correct_answers():
    assert _streak([]) == 0
    assert _streak([{"correct": False}]) == 0
    assert _streak([{"correct": True}] * 5) == 5
    assert _streak([{"correct": True}, {"correct": False}, {"correct": True}, {"correct": True}]) == 2


def test_combo_does_not_change_the_score():
    """The combo is display only: score stays the number of correct answers."""
    items = [{"correct": True}] * 5
    assert _streak(items) == 5
    assert sum(1 for item in items if item["correct"]) == 5


# ---------- A3 persona ----------

def test_persona_is_none_without_topic_scores():
    assert persona_for([]) is None
    assert persona_for(None) is None
    assert persona_for([{"topic": "concepts", "correct": 0, "total": 0}]) is None


def test_persona_follows_the_strongest_dimension():
    scores = [{"topic": "concepts", "correct": 2, "total": 5},
              {"topic": "ai-assistant", "correct": 5, "total": 5},
              {"topic": "soft-skills", "correct": 1, "total": 4},
              {"topic": "process", "correct": 2, "total": 4}]
    assert persona_for(scores)["id"] == "commander"


def test_persona_all_round_needs_every_dimension_high():
    perfect = [{"topic": topic, "correct": 5, "total": 5}
               for topic in ("concepts", "ai-assistant", "soft-skills", "process")]
    assert persona_for(perfect)["id"] == "allround"
    mixed = [{"topic": "concepts", "correct": 2, "total": 5}] + perfect[1:]
    assert persona_for(mixed)["id"] != "allround"


def test_persona_exposes_only_the_documented_keys():
    """§6.13 contract is {id, icon, label, note}; topic stays internal."""
    scores = [{"topic": topic, "correct": 4, "total": 5}
              for topic in ("concepts", "ai-assistant", "soft-skills", "process")]
    persona = persona_for(scores)
    assert set(persona) == {"id", "icon", "label", "note"}, set(persona)
    assert all(isinstance(persona[key], str) and persona[key] for key in persona)


def test_clear_progress_removes_runs_not_just_the_profile():
    """Regression: level badges come from runs, so a reset must delete them too."""
    seen = []

    def run_delete(db, params):
        seen.append(("runs", params))

    def result_delete(db, params):
        seen.append(("results", params))

    def profile_clear(db, params):
        seen.append(("profile", params))

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(service.repository, "delete_user_runs", run_delete)
        monkeypatch.setattr(service.repository, "find_anchor_course", lambda db: {"id": 17})
        monkeypatch.setattr(service.repository, "delete_user_results", result_delete)
        monkeypatch.setattr(service.repository, "clear_profile_reference", profile_clear)
        service.clear_progress(user_id=13, get_db=lambda: SimpleNamespace(commit=lambda: None))
    finally:
        monkeypatch.undo()

    assert [name for name, _ in seen] == ["runs", "results", "profile"]
    params = dict(seen)
    assert set(params["runs"][1]) == set(MISSION_IDS.values()), "all three modes reset"
    assert "release-rescue-v1" not in params["runs"][1], "Release Rescue must survive"
    assert params["results"] == (13, 17), "answers scoped to the anchor course"


def test_persona_is_deterministic_on_ties():
    scores = [{"topic": topic, "correct": 3, "total": 5}
              for topic in ("concepts", "ai-assistant", "soft-skills", "process")]
    assert persona_for(scores) == persona_for(list(reversed(scores)))
