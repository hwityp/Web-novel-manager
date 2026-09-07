"""
==============================================================================
파일: tests/test_novel_origin_detector.py
역할 및 목적:
    NovelOriginDetector 및 GenreClassifierAdapter와의 국적 판별 연동 기능 검증 테스트.
==============================================================================
"""
from pathlib import Path
import pytest

from core.novel_task import NovelTask
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.utils.novel_origin_detector import NovelOriginDetector
from core.utils.content_header_extractor import ContentHeaderResult
from config.pipeline_config import PipelineConfig


class TestNovelOriginDetector:
    """소설 국적(원산지) 감지기 및 파이프라인 연동 단위 테스트"""

    def test_detect_chinese_by_cjk_title(self):
        """괄호 한자 원문 제목 및 중국식 키워드 기반 CN 판정 검증"""
        raw_name = "사합원 중생54년, 인거사주(四合院：重生54年，邻居傻柱) 1-668 완"
        res = NovelOriginDetector.detect(
            title="사합원 중생54년, 인거사주",
            raw_name=raw_name,
            foreign_title="四合院：重生54年，邻居傻柱"
        )
        assert res.country == "CN"
        assert res.confidence == "high"
        assert res.is_foreign is True
        assert any("한자" in r or "사합원" in r for r in res.reasons)

    def test_detect_japanese_by_kana_title(self):
        """괄호 일본어 가나 원문 제목 기반 JP 판정 검증"""
        raw_name = "악역영애는 파멸을 피하고 싶다(悪役令嬢は破滅を回避したい) 1-100 완"
        res = NovelOriginDetector.detect(
            title="악역영애는 파멸을 피하고 싶다",
            raw_name=raw_name,
            foreign_title="悪役令嬢は破滅を回避したい"
        )
        assert res.country == "JP"
        assert res.confidence == "high"
        assert res.is_foreign is True
        assert any("일본어 가나" in r for r in res.reasons)

    def test_detect_chinese_by_source_tag(self):
        """치뎬/진장 등 플랫폼 태그 기반 CN 판정 검증"""
        raw_name = "[치뎬] 만위세계적맹왕 1-373 (완)"
        res = NovelOriginDetector.detect(
            title="만위세계적맹왕",
            raw_name=raw_name
        )
        assert res.country == "CN"
        assert res.confidence == "high"
        assert res.is_foreign is True

    def test_detect_japanese_by_source_tag(self):
        """나로우/카쿠요무 등 플랫폼 태그 기반 JP 판정 검증"""
        raw_name = "[나로우] 전생했더니 슬라임 1-500 (완)"
        res = NovelOriginDetector.detect(
            title="전생했더니 슬라임",
            raw_name=raw_name
        )
        assert res.country == "JP"
        assert res.confidence == "high"
        assert res.is_foreign is True

    def test_detect_korean_novel(self):
        """순수 한국 소설 판정 검증 (해외 단서 없음, K-키워드)"""
        raw_name = "나 혼자만 레벨업 1-270 (완)"
        res = NovelOriginDetector.detect(
            title="나 혼자만 레벨업",
            raw_name=raw_name
        )
        assert res.country == "KR"
        assert res.is_foreign is False

    def test_adapter_pipeline_metadata_injection(self):
        """GenreClassifierAdapter에서 task.metadata에 국적 정보가 정상 주입되는지 검증"""
        config = PipelineConfig()
        adapter = GenreClassifierAdapter(config)

        # 1. 중국 소설 태스크
        task_cn = NovelTask(
            original_path=Path("dummy/cn_novel.txt"),
            current_path=Path("dummy/cn_novel.txt"),
            raw_name="사합원：공간물자(四合院：随身空间) 1-100 완",
            title="사합원：공간물자"
        )
        adapter.classify(task_cn)
        assert task_cn.metadata.get("country_origin") == "CN"
        assert task_cn.metadata.get("is_foreign") is True
        assert "언정" in task_cn.genre

        # 2. 일본 소설 태스크
        task_jp = NovelTask(
            original_path=Path("dummy/jp_novel.txt"),
            current_path=Path("dummy/jp_novel.txt"),
            raw_name="악역영애의 익애(悪役令嬢の溺愛) 1-50 완",
            title="악역영애의 익애"
        )
        adapter.classify(task_jp)
        assert task_jp.metadata.get("country_origin") == "JP"
        assert task_jp.metadata.get("is_foreign") is True
        assert "로판" in task_jp.genre
