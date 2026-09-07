"""
tests/test_chinese_novel_rules.py

중국 번역본 소설 장르 추론 개선 검증:
1. 사합원(四合院) 소설은 여성향 클리셰가 없으면 기본 '현판' ([현판, 사합원])
2. 내용을 이끄는 핵심 키워드가 '시스템'일 경우 '시스템' 서브 태그 필수 포함
3. 여성향 클리셰(교처/단총/복보 등)가 있는 사합원은 '언정' 유지
"""
import pytest
from core.utils.novel_trait_extractor import NovelTraitExtractor
from core.utils.novel_origin_detector import NovelOriginDetector
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.novel_task import NovelTask
from config.pipeline_config import PipelineConfig


class TestChineseNovelRules:
    """중국 번역본 소설 장르 분류 규칙 테스트"""

    def test_sahapwon_default_to_hyeonpan(self):
        """사합원 소설은 여성향 클리셰가 없을 때 기본 '현판'으로 유도되어야 함"""
        # 1. '사합원：아시유광기'
        res1 = NovelTraitExtractor.format_genre_tag(
            primary_genre="언정",  # 웹검색/기존 분류가 언정으로 잘못 들어온 상황
            title="사합원：아시유광기 1-335 (완).txt"
        )
        assert res1 == "현판, 사합원", f"기대값: '현판, 사합원', 실제값: {res1}"

        # 2. '사합원 중생54년, 인거사주'
        res2 = NovelTraitExtractor.format_genre_tag(
            primary_genre="역사",  # 역사로 들어온 상황
            title="사합원 중생54년, 인거사주(四合院：重生54年，邻居傻柱) 1-668 (완).txt"
        )
        assert res2 == "현판, 사합원", f"기대값: '현판, 사합원', 실제값: {res2}"

    def test_sahapwon_with_female_cliche_stays_eonjeong(self):
        """사합원이라도 여성향 클리셰(단총, 교처, 복보 등)가 있으면 '언정' 유지"""
        res = NovelTraitExtractor.format_genre_tag(
            primary_genre="언정",
            title="사합원：교처의 복보 일상 1-300 (완).txt"
        )
        assert res.startswith("언정"), f"기대값: '언정' 시작, 실제값: {res}"
        assert "사합원" in res

    def test_system_trait_guaranteed(self):
        """내용을 이끄는 키워드가 시스템(계통, 모의기, 사인 등)일 경우 장르 정보에 '시스템' 필수 추가"""
        # 사합원 + 계통(시스템)
        res1 = NovelTraitExtractor.format_genre_tag(
            primary_genre="현판",
            title="사합원：개국사인계통 1-500 (완).txt"
        )
        assert "사합원" in res1
        assert "시스템" in res1
        assert res1 == "현판, 사합원, 시스템"

        # 선협 + 모의기/역습계통
        res2 = NovelTraitExtractor.format_genre_tag(
            primary_genre="선협",
            title="대승기재유역습계통 1-780 (완).txt"
        )
        assert res2 == "선협, 시스템"

        # 선협 + 인생모의기
        res3 = NovelTraitExtractor.format_genre_tag(
            primary_genre="선협",
            title="수선：아적무혼시모의기 1-300 (완).txt"
        )
        assert res3 == "선협, 시스템"

    def test_system_trait_prioritized_over_minor_traits(self):
        """다른 traits가 많아도 '시스템'이 누락되지 않고 2개 슬롯 안에 보존되는지 검증"""
        # 공간 + 연대물 + 시스템이 동시에 존재하는 경우
        traits = NovelTraitExtractor.extract_traits(
            primary_genre="현판",
            title="70년대 연대물 휴대공간과 출석체크 계통 치트 1-100.txt"
        )
        assert "시스템" in traits, f"'시스템'이 traits에 포함되어야 함: {traits}"
        assert len(traits) <= 2

    def test_cn_origin_detection_for_translated_titles(self):
        """중국 번역투 음독 제목에 대한 국적 판별 검증"""
        # 대승기재유역습계통
        r1 = NovelOriginDetector.detect(
            title="대승기재유역습계통",
            raw_name="대승기재유역습계통 1-780 (완).txt"
        )
        assert r1.country == "CN"
        assert r1.is_foreign is True

        # 려포적인생모의기
        r2 = NovelOriginDetector.detect(
            title="려포적인생모의기",
            raw_name="려포적인생모의기 1-779 (완).txt"
        )
        assert r2.country == "CN"
        assert r2.is_foreign is True

    def test_adapter_full_classification_pipeline(self):
        """GenreClassifierAdapter 전체 분류 파이프라인 검증"""
        from pathlib import Path
        adapter = GenreClassifierAdapter(PipelineConfig())
        
        # 사합원 소설 분류
        dummy_path1 = Path("사합원：아시유광기 1-335 (완).txt")
        task1 = NovelTask(original_path=dummy_path1, current_path=dummy_path1, raw_name=dummy_path1.name)
        adapter.classify(task1)
        assert task1.genre == "현판, 사합원"
        
        # 대승기재유역습계통 분류
        dummy_path2 = Path("대승기재유역습계통 1-780 (완).txt")
        task2 = NovelTask(original_path=dummy_path2, current_path=dummy_path2, raw_name=dummy_path2.name)
        adapter.classify(task2)
        assert task2.genre == "선협, 시스템"

    def test_sf_mapped_to_fusion_fantasy(self):
        """SF, SF판타지, 공상과학, 科幻는 '퓨판'으로 분류되어야 함"""
        from core.utils.genre_mapping import GenreMappingLoader
        from pathlib import Path
        loader = GenreMappingLoader()
        
        # 1. GenreMappingLoader 매핑 검증
        assert loader.map_genre("SF") == "퓨판"
        assert loader.map_genre("SF판타지") == "퓨판"
        assert loader.map_genre("공상과학") == "퓨판"
        assert loader.map_genre("科幻") == "퓨판"

        # 2. 파일명 첨언 태그 파싱 검증
        extracted = NovelTraitExtractor.extract_from_annotations("[SF] 은하계의 지배자 1-100 (완).txt")
        assert extracted == "퓨판"

        # 3. 어댑터 파이프라인 검증
        adapter = GenreClassifierAdapter(PipelineConfig())
        sf_path = Path("[SF] 은하함대사령관 1-200.txt")
        task = NovelTask(original_path=sf_path, current_path=sf_path, raw_name=sf_path.name)
        adapter.classify(task)
        assert task.genre.startswith("퓨판")
