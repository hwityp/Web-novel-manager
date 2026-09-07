"""
==============================================================================
파일: tests/test_foreign_novel_genre_inference.py
역할 및 목적:
    해외(중국/일본) 웹소설의 본문 헤더 스니펫 추출 및 CJK 원문 제목 기반
    장르 추론 기능이 올바르게 동작하는지 종합 검증하는 단위 테스트.
==============================================================================
"""
import os
import tempfile
from pathlib import Path
import pytest

from core.novel_task import NovelTask
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.utils.content_header_extractor import ContentHeaderGenreExtractor, ContentHeaderResult
from config.pipeline_config import PipelineConfig


class TestForeignNovelGenreInference:
    """해외 소설 장르 추론 강화 기능 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.config = PipelineConfig()
        self.adapter = GenreClassifierAdapter(self.config)

    def test_content_header_korean_translation(self, tmp_path):
        """한국어 번역 텍스트 파일 헤더 추출 검증"""
        content = """【작품소개】
장르: 선협 / 수진
태그: #시스템 #환생 #먼치킨
원제: 百年修仙，快死才来金手指
내용: 백 년 동안 수련하여 마침내 치트 시스템을 각성한 주인공의 이야기...
제1장 시작
"""
        txt_file = tmp_path / "백년수선 1-100 (완).txt"
        txt_file.write_text(content, encoding='utf-8')

        result = ContentHeaderGenreExtractor.extract_from_file(txt_file)
        assert result is not None
        assert result.raw_genre == "선협"
        assert "수진" in result.tags
        assert "시스템" in result.tags

        # 어댑터 연동 테스트
        task = NovelTask(
            original_path=txt_file,
            current_path=txt_file,
            raw_name="백년수선 1-100 (완)",
            title="백년수선"
        )
        classified_task = self.adapter.classify(task)
        assert "선협" in classified_task.genre
        assert "시스템" in classified_task.genre
        assert classified_task.source == "본문헤더"
        assert classified_task.confidence == "high"

    def test_content_header_chinese_qidian(self, tmp_path):
        """중국어 치뎬/진장 원문 헤더 파싱 검증 (GB18030 / UTF-8)"""
        content = """【作品类型】 言情
【标签】 穿越 随身空间 农家
【内容简介】
穿越到七十年代农家，带着随身空间物资发家致富的故事。
第一章 穿越七零
"""
        txt_file = tmp_path / "七零空间娇妻 (完).txt"
        txt_file.write_text(content, encoding='utf-8')

        result = ContentHeaderGenreExtractor.extract_from_file(txt_file)
        assert result is not None
        assert result.raw_genre == "言情"
        assert "穿越" in result.tags

        task = NovelTask(
            original_path=txt_file,
            current_path=txt_file,
            raw_name="七零空间娇妻 (完)",
            title="七零空间娇妻"
        )
        classified_task = self.adapter.classify(task)
        assert "언정" in classified_task.genre
        assert classified_task.source == "본문헤더"
        assert classified_task.confidence == "high"

    def test_content_header_japanese_syosetu(self, tmp_path):
        """일본어 나로우/카쿠요무 원문 헤더 파싱 검증"""
        content = """【ジャンル】 ハイファンタジー
【タグ】 異世界転生 チート 追放 魔王
【あらすじ】
追放された元勇者がスローライフを目指して旅立つ...
第1話 追放された日
"""
        txt_file = tmp_path / "追放勇者のスローライフ 1-50 (完).txt"
        txt_file.write_text(content, encoding='utf-8')

        result = ContentHeaderGenreExtractor.extract_from_file(txt_file)
        assert result is not None
        assert result.raw_genre == "ハイファンタジー"
        assert "異世界転生" in result.tags

        task = NovelTask(
            original_path=txt_file,
            current_path=txt_file,
            raw_name="追放勇자의スローライフ 1-50 (完)",
            title="追放勇者のスローライフ"
        )
        classified_task = self.adapter.classify(task)
        assert "판타지" in classified_task.genre
        assert classified_task.source == "본문헤더"
        assert classified_task.confidence == "high"

    def test_cjk_foreign_title_fallback_inference(self):
        """본문 파일이 없어도 괄호 CJK 원문 제목으로 장르가 추론되는지 검증"""
        # 1. 중국 언정 / 사합원 CJK 제목
        raw_name_1 = "사합원 중생54년, 인거사주(四合院：重生54年，邻居傻柱) 1-668 완"
        task1 = NovelTask(
            original_path=Path("dummy/path1.txt"),
            current_path=Path("dummy/path1.txt"),
            raw_name=raw_name_1,
            title="사합원 중생54년, 인거사주"
        )
        res1 = self.adapter.classify(task1)
        assert "현판" in res1.genre
        assert "사합원" in res1.genre

        # 2. 중국 선협 CJK 제목
        raw_name_2 = "수선일지(修仙日记：我能看到隐藏机缘) 1-200 완"
        task2 = NovelTask(
            original_path=Path("dummy/path2.txt"),
            current_path=Path("dummy/path2.txt"),
            raw_name=raw_name_2,
            title="수선일지"
        )
        res2 = self.adapter.classify(task2)
        assert "선협" in res2.genre

        # 3. 일본 로판 악역영애 CJK 제목
        raw_name_3 = "악역영애는 파멸을 피하고 싶다(悪役令嬢は破滅を回避したい) 1-100 완"
        task3 = NovelTask(
            original_path=Path("dummy/path3.txt"),
            current_path=Path("dummy/path3.txt"),
            raw_name=raw_name_3,
            title="악역영애는 파멸을 피하고 싶다"
        )
        res3 = self.adapter.classify(task3)
        assert "로판" in res3.genre
