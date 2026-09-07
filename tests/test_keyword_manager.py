"""
==============================================================================
파일: tests/test_keyword_manager.py
역할 및 목적:
    KeywordManager의 calculate_scores 및 키워드 매칭, 한글 인코딩 안전성을 검증하는 테스트.
==============================================================================
"""
import pytest
from modules.classifier.src.core.keyword_manager import KeywordManager


class TestKeywordManager:
    """KeywordManager 기능 및 calculate_scores 단위 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.km = KeywordManager()

    def test_calculate_scores_returns_dict(self):
        """calculate_scores가 점수 내림차순 정렬된 dict를 반환하는지 검증"""
        scores = self.km.calculate_scores("천마가 환생하여 남궁세가에 들어갔다")
        assert isinstance(scores, dict)
        assert len(scores) > 0
        assert "무협" in scores
        # 무협 점수가 가장 높아야 함
        first_genre = list(scores.keys())[0]
        assert first_genre == "무협"
        assert scores["무협"] > 0

    def test_calculate_scores_single_genre(self):
        """특정 genre 인자를 지정했을 때 float 점수를 반환하는지 검증"""
        score = self.km.calculate_scores("천마 환생", genre="무협")
        assert isinstance(score, float)
        assert score > 0

        score_zero = self.km.calculate_scores("천마 환생", genre="로판")
        assert isinstance(score_zero, float)
        assert score_zero == 0.0

    def test_calculate_scores_empty_and_none(self):
        """None 및 빈 문자열 입력 시 예외 없이 안전하게 0점 dict 반환하는지 검증"""
        scores_none = self.km.calculate_scores(None)
        assert isinstance(scores_none, dict)
        assert all(v == 0.0 for v in scores_none.values())

        scores_empty = self.km.calculate_scores("")
        assert isinstance(scores_empty, dict)
        assert all(v == 0.0 for v in scores_empty.values())

        score_none_genre = self.km.calculate_scores(None, genre="무협")
        assert score_none_genre == 0.0

    def test_calculate_scores_compound_patterns(self):
        """복합 키워드 패턴 매칭 보너스가 반영되는지 검증"""
        # '무공' + '시스템' 복합 패턴 매칭
        scores = self.km.calculate_scores("주인공이 무공과 시스템을 얻었다")
        assert scores.get("무협", 0) > 0

    def test_calculate_scores_special_cases(self):
        """특수 케이스 제목 매칭 시 해당 장르 보너스 반영 검증"""
        scores = self.km.calculate_scores("나 혼자만 레벨업 1권")
        assert scores.get("현판", 0) > 20

    def test_calculate_scores_normalization(self):
        """normalize=True 옵션 적용 시 정규화 점수 계산 검증"""
        raw_scores = self.km.calculate_scores("천마 남궁세가", normalize=False)
        norm_scores = self.km.calculate_scores("천마 남궁세가", normalize=True)
        assert isinstance(norm_scores, dict)
        assert norm_scores["무협"] > 0
        assert norm_scores["무협"] <= raw_scores["무협"]
