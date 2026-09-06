"""
Unit tests for foreign web novel title parsing and normalization (3 types)
"""
import pytest
from core.title_anchor_extractor import parse_foreign_title_info, TitleAnchorExtractor
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter
from core.novel_task import NovelTask
from config.pipeline_config import PipelineConfig
from pathlib import Path


class TestForeignTitleParser:

    def test_sino_korean_title(self):
        """Type 1: 원문 제목(간체/번체)을 한국식 한자음으로 적은 경우"""
        raw = "아가낭자타강산(我家娘子打江山) 1-300 (완).txt"
        info = parse_foreign_title_info("아가낭자타강산(我家娘子打江山)")
        assert info['original_foreign_title'] == "我家娘子打江山"
        assert info['clean_title'] == "아가낭자타강산"
        assert info['foreign_type'] == "sino_korean"

    def test_translation_title(self):
        """Type 2: 원문 제목을 한국어로 번역해서 적은 경우"""
        raw = "말세: 여인이 소모한 물자는 만 배로 돌려받는다 (末世：女人消耗的物资万倍返还)"
        info = parse_foreign_title_info(raw)
        assert info['original_foreign_title'] == "末世：女人消耗的物资万倍返还"
        assert "여인이 소모한 물자는 만 배로 돌려받는다" in info['clean_title']
        assert info['foreign_type'] == "translation"

    def test_parallel_title(self):
        """Type 3: 원문 제목과 번역문을 함께 적은 경우"""
        raw = "아가낭자타강산 - 말세: 여인이 소모한 물자는 만 배로 돌려받는다 (我家娘子打江山)"
        info = parse_foreign_title_info(raw)
        assert info['original_foreign_title'] == "我家娘子打江山"
        assert "아가낭자타강산" in info['clean_title']
        assert info['foreign_type'] == "parallel"

    def test_foreign_title_normalization(self):
        """해외 소설 정규화 파일명 생성 검증"""
        extractor = TitleAnchorExtractor()

        # Case 1: Sino-Korean (공백 없는 원문 유지)
        res1 = extractor.extract("아가낭자타강산(我家娘子打江山) 1-300 (완).txt")
        normalized1 = res1.to_normalized_filename(genre="선협, 여주, 시스템")
        assert normalized1 == "[선협, 여주, 시스템] 아가낭자타강산(我家娘子打江山) 1-300 (완).txt"

        # Case 1-2: Sino-Korean (공백 있는 원문 유지)
        res1_space = extractor.extract("아가낭자타강산 (我家娘子打江山) 1-300 (완).txt")
        assert res1_space.to_normalized_filename(genre="선협, 여주, 시스템") == "[선협, 여주, 시스템] 아가낭자타강산 (我家娘子打江山) 1-300 (완).txt"

        # Case 2: Translation
        res2 = extractor.extract("말세: 여인이 소모한 물자는 만 배로 돌려받는다 (末世：女人消耗的物资万倍返还) 1-500 (완).txt")
        normalized2 = res2.to_normalized_filename(genre="퓨판, 말세, 시스템")
        assert normalized2 == "[퓨판, 말세, 시스템] 말세: 여인이 소모한 물자는 만 배로 돌려받는다 (末世：女人消耗的物资万倍返还) 1-500 (완).txt"

        # Case 3: Parallel
        res3 = extractor.extract("아가낭자타강산 - 말세: 여인이 소모한 물자는 만 배로 돌려받는다 (我家娘子打江山) 1-300 (완).txt")
        normalized3 = res3.to_normalized_filename(genre="현판, 사합원, 시스템")
        assert normalized3 == "[현판, 사합원, 시스템] 아가낭자타강산 - 말세: 여인이 소모한 물자는 만 배로 돌려받는다 (我家娘子打江山) 1-300 (완).txt"


class TestFilenameNormalizerWithForeignTitles:

    @pytest.fixture
    def normalizer(self):
        config = PipelineConfig()
        return FilenameNormalizerAdapter(config)

    def test_normalizer_adapter_foreign_titles(self, normalizer):
        task = NovelTask(
            original_path=Path("아가낭자타강산(我家娘子打江山) 1-300 (완).txt"),
            current_path=Path("아가낭자타강산(我家娘子打江山) 1-300 (완).txt"),
            raw_name="아가낭자타강산(我家娘子打江山) 1-300 (완)"
        )
        task.genre = "선협, 여주, 시스템"
        task = normalizer.normalize(task)
        result = task.metadata['normalized_name']
        assert result == "[선협, 여주, 시스템] 아가낭자타강산(我家娘子打江山) 1-300 (완).txt"
