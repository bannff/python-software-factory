"""Tests for game-type rubrics."""

from factory.games.runtime.rubrics import get_rubric, list_rubrics, RUBRICS


class TestRubrics:
    """Rubric registry tests."""

    def test_all_rubrics_are_non_empty_strings(self):
        for game_type, rubric in RUBRICS.items():
            assert isinstance(rubric, str), f"{game_type} rubric not a string"
            assert len(rubric) > 50, f"{game_type} rubric too short"

    def test_get_rubric_returns_known_types(self):
        assert get_rubric("ctf_challenge") != ""
        assert get_rubric("xss_hunter") != ""
        assert get_rubric("idor_detective") != ""
        assert get_rubric("finding_triage") != ""
        assert get_rubric("task_completion") != ""
        assert get_rubric("connect_four") != ""

    def test_get_rubric_returns_empty_for_unknown(self):
        assert get_rubric("nonexistent_game") == ""

    def test_list_rubrics_returns_all(self):
        rubric_list = list_rubrics()
        assert len(rubric_list) == len(RUBRICS)
        assert "ctf_challenge" in rubric_list
        assert "xss_hunter" in rubric_list

    def test_security_rubrics_have_scoring_dimensions(self):
        """Security rubrics should have multi-dimensional scoring."""
        for game_type in ("xss_hunter", "idor_detective", "finding_triage"):
            rubric = get_rubric(game_type)
            assert "0-1" in rubric, f"{game_type} missing dimension scores"
            assert "Score" in rubric or "score" in rubric

    def test_rubrics_mention_score_thresholds(self):
        """All rubrics should have explicit scoring guidance."""
        for game_type, rubric in RUBRICS.items():
            has_score = any(
                kw in rubric.lower()
                for kw in ("score", "0-1", "1.0", "0.0")
            )
            assert has_score, f"{game_type} rubric missing score guidance"
