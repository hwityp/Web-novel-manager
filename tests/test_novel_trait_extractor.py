"""
Tests for NovelTraitExtractor and Reference Examples Keyword Tagging
"""
import pytest
from core.utils.novel_trait_extractor import NovelTraitExtractor
from core.title_anchor_extractor import TitleAnchorExtractor
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter
from core.novel_task import NovelTask
from config.pipeline_config import PipelineConfig
from pathlib import Path


class TestNovelTraitExtractor:

    @pytest.mark.parametrize("raw_tag, expected_primary, expected_traits", [
        ("판타지, 시스템", "판타지", ["시스템"]),
        ("겜판", "겜판", []),
        ("언정, 궁정", "언정", ["궁정"]),
        ("언정, 궁투, 빙의", "언정", ["궁투", "빙의"]),
        ("언정, 공간, 농촌", "언정", ["공간", "농촌"]),
        ("언정, 책빙의", "언정", ["책빙의"]),
        ("로판", "로판", []),
        ("무협, 시스템", "무협", ["시스템"]),
        ("선협, 시스템", "선협", ["시스템"]),
        ("현판, 사합원, 시스템", "현판", ["사합원", "시스템"]),
        ("선협, 여주, 시스템", "선협", ["여주", "시스템"]),
        ("언정, 하렘, 시스템", "언정", ["하렘", "시스템"]),
        ("스포츠", "스포츠", []),
        ("언정, 가족", "언정", ["가족"]),
        ("언정, 시스템", "언정", ["시스템"]),
        ("언정, 연대물, 공간", "언정", ["연대물", "공간"]),
        ("역사", "역사", []),
        ("현판, 연대물, 재테크", "현판", ["연대물", "재테크"]),
        ("패러디, 드래곤볼", "패러디", ["드래곤볼"]),
        ("퓨판, 말세, 이세계", "퓨판", ["말세", "이세계"]),
        ("퓨판, 시스템", "퓨판", ["시스템"]),
        ("퓨판, 종말", "퓨판", ["종말"]),
        ("현대, 군사, 첩보", "현대", ["군사", "첩보"]),
        ("현대, 로맨스, 코미디", "현대", ["로맨스", "코미디"]),
        ("현대, 시스템, 코미디", "현대", ["시스템", "코미디"]),
        ("현대, 힐링, 일상", "현대", ["힐링", "일상"]),
        ("현판 시스템", "현판", ["시스템"]),
    ])
    def test_parse_existing_tag(self, raw_tag, expected_primary, expected_traits):
        primary, traits = NovelTraitExtractor.parse_existing_tag(raw_tag)
        assert primary == expected_primary
        assert traits == expected_traits

    @pytest.mark.parametrize("primary, title, existing_kw, expected_tag", [
        ("판타지", "새박붕극：아능안장유희모조 1-173 (완).txt", None, "판타지, 시스템"),
        ("현판", "사합원 삼국 1-100 (완).txt", ["사합원", "시스템"], "현판, 사합원, 시스템"),
        ("선협", "여주 선협 전설 1-50 (완).txt", ["여주", "시스템"], "선협, 여주, 시스템"),
        ("언정", "하렘 시스템 이야기 1-80 (완).txt", ["하렘", "시스템"], "언정, 하렘, 시스템"),
        ("겜판", "로열페이트 1-26 (완).txt", None, "겜판"),
        ("언정", "궤비：군성귀위자 1-790 (완).txt", None, "언정, 궁정"),
        ("언정", "아재궁투극리당태의 1-187 (완).txt", ["궁투", "빙의"], "언정, 궁투, 빙의"),
        ("언정", "단총교처：아대공간물자천칠령(70년대로 천월) 1-399 (완).txt", ["공간", "농촌"], "언정, 공간, 농촌"),
        ("언정", "천서후，아성료오개대노적마 1-322 (완).txt", None, "언정, 책빙의"),
        ("로판", "그오토메 게임의 배드엔딩 1-240 (완).txt", None, "로판"),
        ("무협", "사조：종피축출도화도개시 1-582 (완).txt", None, "무협, 시스템"),
        ("선협", "백 년 수선, 죽기 직전에야 치트가 찾아왔다 1-1308 (완).txt", None, "선협, 시스템"),
        ("스포츠", "프로축구 생존기 1-258 (완).txt", None, "스포츠"),
        ("언정", "복보유량전、단총소내포，농가복매경시진천금 1-796 (완).txt", ["가족"], "언정, 가족"),
        ("언정", "농문수부금리처 1-585 (완).txt", ["시스템"], "언정, 시스템"),
        ("언정", "칠령공간：교교지청료득조한심전(애교쟁이 지청이 거친 사내의 마음을 흔든다) 1-324 (완).txt", None, "언정, 연대물, 공간"),
        ("역사", "고려 흑태자 1-571 (완) + 외전.txt", None, "역사"),
        ("현판", "지가가1990 1-1593 (완).txt", None, "현판, 연대물, 재테크"),
        ("판타지", "반파필수장명백세 1-230 (완).txt", None, "판타지, 시스템"),
        ("패러디", "내 손오공이 초사이어인 파이브로 변신 베지터를 기절시킴 1-330 (완).txt", None, "패러디, 드래곤볼"),
        ("퓨판", "이차원말일도계시 1-1366 (완).txt", None, "퓨판, 말세, 이세계"),
        ("퓨판", "이차원말일도계시 1-1366 (완).txt", ["말세", "이세계"], "퓨판, 말세, 이세계"),
        ("퓨판", "탄서성공에서 출석 체크로 강해지다 1-1087 (완).txt", None, "퓨판, 시스템"),
        ("퓨판", "말일：아타조무한열차 1-544 (완).txt", None, "퓨판, 종말"),
        ("현대", "서난종명 1-484 (완).txt", None, "현대, 군사, 첩보"),
        ("현대", "아가재료련애유희 (완).txt", None, "현대, 로맨스, 코미디"),
        ("현대", "첨도계통조아위국첨부 1-151 (완).txt", None, "현대, 시스템, 코미디"),
        ("현대", "평범적청천일자 (완).txt", None, "현대, 힐링, 일상"),
        ("현판", "영시세계당신탐 1-2158 (완) + 외전 74.txt", None, "현판, 시스템"),
    ])
    def test_format_genre_tag(self, primary, title, existing_kw, expected_tag):
        formatted = NovelTraitExtractor.format_genre_tag(
            primary_genre=primary,
            title=title,
            existing_keywords=existing_kw
        )
        assert formatted == expected_tag


class TestReferenceExamplesPipeline:

    @pytest.fixture
    def normalizer(self):
        config = PipelineConfig()
        return FilenameNormalizerAdapter(config)

    @pytest.mark.parametrize("raw_filename", [
        "[판타지, 시스템] 새박붕극：아능안장유희모조 1-173 (완).txt",
        "[겜판] 로열페이트 1-26 (완).txt",
        "[언정, 궁정] 궤비：군성귀위자 1-790 (완).txt",
        "[언정, 궁투, 빙의] 아재궁투극리당태의 1-187 (완).txt",
        "[언정, 공간, 농촌] 단총교처：아대공간물자천칠령(70년대로 천월) 1-399 (완).txt",
        "[언정, 책빙의] 천서후，아성료오개대노적마 1-322 (완).txt",
        "[로판] 그오토메 게임의 배드엔딩 1-240 (완).txt",
        "[무협, 시스템] 사조：종피축출도화도개시 1-582 (완).txt",
        "[선협, 시스템] 백 년 수선, 죽기 직전에야 치트가 찾아왔다 1-1308 (완).txt",
        "[스포츠] 프로축구 생존기 1-258 (완).txt",
        "[언정, 가족] 복보유량전、단총소내포，농가복매경시진천금 1-796 (완).txt",
        "[언정, 시스템] 농문수부금리처 1-585 (완).txt",
        "[언정, 연대물, 공간] 칠령공간：교교지청료득조한심전(애교쟁이 지청이 거친 사내의 마음을 흔든다) 1-324 (완).txt",
        "[역사] 고려 흑태자 1-571 (완) + 외전.txt",
        "[현판, 연대물, 재테크] 지가가1990 1-1593 (완).txt",
        "[판타지, 시스템] 반파필수장명백세 1-230 (완).txt",
        "[패러디, 드래곤볼] 내 손오공이 초사이어인 파이브로 변신 베지터를 기절시킴 1-330 (완).txt",
        "[퓨판, 말세, 이세계] 이차원말일도계시 1-1366 (완).txt",
        "[퓨판, 시스템] 탄서성공에서 출석 체크로 강해지다 1-1087 (완).txt",
        "[퓨판, 종말] 말일：아타조무한열차 1-544 (완).txt",
        "[현대, 군사, 첩보] 서난종명 1-484 (완).txt",
        "[현대, 로맨스, 코미디] 아가재료련애유희 (완).txt",
        "[현대, 시스템, 코미디] 첨도계통조아위국첨부 1-151 (완).txt",
        "[현대, 힐링, 일상] 평범적청천일자 (완).txt",
        "[현판, 시스템] 영시세계당신탐 1-2158 (완) + 외전 74.txt",
    ])
    def test_filename_normalization_preserves_reference_examples(self, normalizer, raw_filename):
        stem = Path(raw_filename).stem
        task = NovelTask(
            original_path=Path(raw_filename),
            current_path=Path(raw_filename),
            raw_name=stem
        )
        task = normalizer.normalize(task)
        result_name = task.metadata['normalized_name']
        assert result_name == raw_filename

    def test_underscore_range_normalization(self, normalizer):
        raw_filename = "15 중생2015，고중개시주남신 련재_1_222 완.txt"
        stem = Path(raw_filename).stem
        task = NovelTask(
            original_path=Path(raw_filename),
            current_path=Path(raw_filename),
            raw_name=stem
        )
        task.genre = "언정"
        task = normalizer.normalize(task)
        result_name = task.metadata['normalized_name']
        assert result_name == "[언정] 15 중생2015，고중개시주남신 1-222 (완).txt"
