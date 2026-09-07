"""
==============================================================================
파일: tests/test_annotation_and_normalization.py
역할 및 목적:
    사용자 요구사항에 맞춘 첨언 우선 장르/특성 추론 및 완결+외전(完外) 파일명 정규화 검증 테스트.
주요 테스트 항목:
    1. 完外(완결+외전 복합 표기) 정규화: '궁투불여양조구 完外.txt' -> '궁투불여양조구 (완) + 외전.txt'
    2. 해시태그 첨언 우선 추출: '... 1-267 完 (AI번역) #패러디 #해리포터.txt' -> '[패러디, 해리포터] ... (완).txt'
    3. 다중 브래킷 단일 장르 추출: '[언정][AI번역] 중생낭자전 1~1466(완).txt' -> '[언정] 중생낭자전 1-1466 (완).txt'
    4. 다중 브래킷 특성(연대물) 추출: '[언정][AI번역][연대] 중생낭자재종전 1~1466(완).txt' -> '[언정, 연대물] 중생낭자재종전 1-1466 (완).txt'
    5. 복합 브래킷(패러디+소재+시스템) 추출: '[나루토패러디 시스템 AI번역] 푸른 용 1-633 완결.txt' -> '[패러디, 나루토, 시스템] 푸른 용 1-633 (완).txt'
    6. GenreClassifierAdapter에서 첨언 감지 시 웹 검색을 건너뛰고 즉시 확정하는 동작 검증
상호 연관 관계 및 의존성:
    - Callee: core.title_anchor_extractor, core.utils.novel_trait_extractor, core.adapters.*
==============================================================================
"""
from pathlib import Path
import pytest
from core.novel_task import NovelTask
from core.title_anchor_extractor import TitleAnchorExtractor
from core.utils.novel_trait_extractor import NovelTraitExtractor
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter
from config.pipeline_config import PipelineConfig


class TestAnnotationAndNormalization:
    """첨언 우선 장르 추출 및 完外 정규화 종합 테스트"""

    def setup_method(self):
        self.config = PipelineConfig()
        self.title_extractor = TitleAnchorExtractor()
        self.normalizer = FilenameNormalizerAdapter(self.config)
        self.classifier = GenreClassifierAdapter(self.config)

    def test_wan_wai_normalization(self):
        """1. 完外 복합 완결+외전 마커 처리 검증"""
        raw_name = "궁투불여양조구 完外.txt"
        res = self.title_extractor.extract(raw_name)
        assert res.title == "궁투불여양조구"
        assert res.is_completed is True
        assert "외전" in res.side_story
        
        normalized = res.to_normalized_filename()
        assert normalized == "궁투불여양조구 (완) + 외전.txt"

        # 변형 패턴 테스트: 完+外
        res_plus = self.title_extractor.extract("궁투불여양조구 完+外.txt")
        assert res_plus.is_completed is True
        assert "외전" in res_plus.side_story
        assert res_plus.to_normalized_filename() == "궁투불여양조구 (완) + 외전.txt"

    def test_hashtag_parody_harry_potter(self):
        """2. 해시태그 첨언(#패러디 #해리포터) 추출 및 정규화 검증"""
        raw_name = "아도성곽격옥자교수료, 계통재래 1-267 完 (AI번역) #패러디 #해리포터.txt"
        
        # 장르 및 특성 추출 검증
        extracted_genre = NovelTraitExtractor.extract_from_annotations(raw_name)
        assert extracted_genre == "패러디, 해리포터"

        # 제목 및 상태 파싱 검증
        parse_res = self.title_extractor.extract(raw_name)
        assert parse_res.title == "아도성곽격옥자교수료, 계통재래"
        assert parse_res.range_info == "1-267"
        assert parse_res.is_completed is True
        assert "#" not in parse_res.title

        # 최종 정규화 검증
        normalized = parse_res.to_normalized_filename(genre=extracted_genre)
        assert normalized == "[패러디, 해리포터] 아도성곽격옥자교수료, 계통재래 1-267 (완).txt"

    def test_hashtag_conan_parody(self):
        """2.1 다중 단어 해시태그(#패러디 #명탐정 코난) 추출 및 정규화 검증"""
        raw_name = "가남：개국절호명미，와저주창 1-740 完 (AI번역) #패러디 #명탐정 코난.txt"

        # 장르 및 특성 추출 검증
        extracted_genre = NovelTraitExtractor.extract_from_annotations(raw_name)
        assert extracted_genre == "패러디, 명탐정 코난"

        # 제목 및 상태 파싱 검증
        parse_res = self.title_extractor.extract(raw_name)
        assert parse_res.title == "가남：개국절호명미，와저주창"
        assert parse_res.range_info == "1-740"
        assert parse_res.is_completed is True
        assert "#" not in parse_res.title
        assert "코난" not in parse_res.title
        assert "코난" not in parse_res.side_story

        # 최종 정규화 검증
        normalized = parse_res.to_normalized_filename(genre=extracted_genre)
        assert normalized == "[패러디, 명탐정 코난] 가남：개국절호명미，와저주창 1-740 (완).txt"

        # 기본 정규화(인자 미전달 시에도 동일하게 작동)
        assert parse_res.to_normalized_filename() == "[패러디, 명탐정 코난] 가남：개국절호명미，와저주창 1-740 (완).txt"

    def test_conan_parody_variations(self):
        """2.2 코난 패러디 변형 표기(#명탐정코난, #코난, [명탐정 코난패러디]) 파싱 검증"""
        cases = [
            ("가남：개국절호명미，와저주창 1-740 完 (AI번역) #패러디 #명탐정코난.txt", "패러디, 명탐정 코난"),
            ("가남：개국절호명미，와저주창 1-740 完 (AI번역) #패러디 #코난.txt", "패러디, 명탐정 코난"),
            ("[명탐정 코난패러디][AI번역] 가남：개국절호명미，와저주창 1-740 (완).txt", "패러디, 명탐정 코난"),
            ("[코난패러디] 가남：개국절호명미，와저주창 1-740 (완).txt", "패러디, 명탐정 코난"),
            ("[패러디, 명탐정 코난] 가남：개국절호명미，와저주창 1-740 (완).txt", "패러디, 명탐정 코난"),
        ]
        for raw, expected_genre in cases:
            genre = NovelTraitExtractor.extract_from_annotations(raw)
            assert genre == expected_genre, f"Failed for {raw}: got {genre}, expected {expected_genre}"

    def test_prefix_brackets_eonjeong(self):
        """3. 다중 브래킷 [언정][AI번역] 추출 및 정규화 검증"""
        raw_name = "[언정][AI번역] 중생낭자전 1~1466(완).txt"
        
        extracted_genre = NovelTraitExtractor.extract_from_annotations(raw_name)
        assert extracted_genre == "언정"

        parse_res = self.title_extractor.extract(raw_name)
        assert parse_res.title == "중생낭자전"
        assert parse_res.range_info == "1-1466"
        assert parse_res.is_completed is True

        normalized = parse_res.to_normalized_filename(genre=extracted_genre)
        assert normalized == "[언정] 중생낭자전 1-1466 (완).txt"

    def test_prefix_brackets_eonjeong_yeondae(self):
        """4. 다중 브래킷 [언정][AI번역][연대] 추출 및 연대물 정규화 검증"""
        raw_name = "[언정][AI번역][연대] 중생낭자재종전 1~1466(완).txt"
        
        extracted_genre = NovelTraitExtractor.extract_from_annotations(raw_name)
        assert extracted_genre == "언정, 연대물"

        parse_res = self.title_extractor.extract(raw_name)
        assert parse_res.title == "중생낭자재종전"
        assert parse_res.range_info == "1-1466"
        assert parse_res.is_completed is True

        normalized = parse_res.to_normalized_filename(genre=extracted_genre)
        assert normalized == "[언정, 연대물] 중생낭자재종전 1-1466 (완).txt"

    def test_compound_bracket_naruto_parody_system(self):
        """5. 복합 브래킷 [나루토패러디 시스템 AI번역] 분해 및 정규화 검증"""
        raw_name = "[나루토패러디 시스템 AI번역] 푸른 용 1-633 완결.txt"
        
        extracted_genre = NovelTraitExtractor.extract_from_annotations(raw_name)
        assert extracted_genre == "패러디, 나루토, 시스템"

        parse_res = self.title_extractor.extract(raw_name)
        assert parse_res.title == "푸른 용"
        assert parse_res.range_info == "1-633"
        assert parse_res.is_completed is True

        normalized = parse_res.to_normalized_filename(genre=extracted_genre)
        assert normalized == "[패러디, 나루토, 시스템] 푸른 용 1-633 (완).txt"

    def test_pipeline_adapter_integration(self):
        """6. GenreClassifierAdapter 및 FilenameNormalizerAdapter 통합 파이프라인 검증"""
        # (1) 장르 없는 단순 파일명의 정규화 검증
        task1 = NovelTask(
            original_path=Path("궁투불여양조구 完外.txt"),
            current_path=Path("궁투불여양조구 完外.txt"),
            raw_name="궁투불여양조구 完外.txt"
        )
        norm_task1 = self.normalizer.normalize(task1)
        assert norm_task1.metadata.get("normalized_name") == "궁투불여양조구 (완) + 외전.txt"

        # (2) 첨언 우선 추출 및 정규화 통합 검증
        annotated_test_cases = [
            (
                "아도성곽격옥자교수료, 계통재래 1-267 完 (AI번역) #패러디 #해리포터.txt",
                "[패러디, 해리포터] 아도성곽격옥자교수료, 계통재래 1-267 (완).txt",
                "패러디, 해리포터"
            ),
            (
                "가남：개국절호명미，와저주창 1-740 完 (AI번역) #패러디 #명탐정 코난.txt",
                "[패러디, 명탐정 코난] 가남：개국절호명미，와저주창 1-740 (완).txt",
                "패러디, 명탐정 코난"
            ),
            (
                "[언정][AI번역] 중생낭자전 1~1466(완).txt",
                "[언정] 중생낭자전 1-1466 (완).txt",
                "언정"
            ),
            (
                "[언정][AI번역][연대] 중생낭자재종전 1~1466(완).txt",
                "[언정, 연대물] 중생낭자재종전 1-1466 (완).txt",
                "언정, 연대물"
            ),
            (
                "[나루토패러디 시스템 AI번역] 푸른 용 1-633 완결.txt",
                "[패러디, 나루토, 시스템] 푸른 용 1-633 (완).txt",
                "패러디, 나루토, 시스템"
            ),
        ]

        for filename, expected_normalized, expected_genre in annotated_test_cases:
            task = NovelTask(
                original_path=Path(filename),
                current_path=Path(filename),
                raw_name=filename
            )
            classified_task = self.classifier.classify(task)
            
            assert classified_task.genre == expected_genre
            assert classified_task.source == "annotation"
            assert classified_task.confidence == "high"

            normalized_task = self.normalizer.normalize(classified_task)
            assert normalized_task.metadata.get("normalized_name") == expected_normalized

    def test_extra_review_normalization(self):
        """7. '나는 엑스트라를 원한다 1-320 + 후기.txt' -> '나는 엑스트라를 원한다 1-320 (완) + 후기.txt' 검증"""
        raw_name = "나는 엑스트라를 원한다 1-320 + 후기.txt"
        res = self.title_extractor.extract(raw_name)
        assert res.title == "나는 엑스트라를 원한다"
        assert res.range_info == "1-320"
        assert res.is_completed is True
        assert "후기" in res.side_story
        assert res.to_normalized_filename() == "나는 엑스트라를 원한다 1-320 (완) + 후기.txt"

    def test_samgukji_main_and_side_normalization(self):
        """8. '삼국지 유현덕의 천재아들 165본편 및 외전 (완).txt' -> '삼국지 유현덕의 천재아들 1-165 (완) + 외전.txt' 검증"""
        raw_name = "삼국지 유현덕의 천재아들 165본편 및 외전 (완).txt"
        res = self.title_extractor.extract(raw_name)
        assert res.title == "삼국지 유현덕의 천재아들"
        assert res.range_info == "1-165"
        assert res.is_completed is True
        assert "외전" in res.side_story
        assert res.to_normalized_filename() == "삼국지 유현덕의 천재아들 1-165 (완) + 외전.txt"

    def test_normalization_first_pipeline_flow(self):
        """9. 파일명 정규화(Stage 1.5)가 장르 추론(Stage 2)보다 먼저 수행되어도 첨언 장르가 유지되는지 검증"""
        annotated_test_cases = [
            (
                "아도성곽격옥자교수료, 계통재래 1-267 完 (AI번역) #패러디 #해리포터.txt",
                "[패러디, 해리포터] 아도성곽격옥자교수료, 계통재래 1-267 (완).txt",
                "패러디, 해리포터"
            ),
            (
                "가남：개국절호명미，와저주창 1-740 完 (AI번역) #패러디 #명탐정 코난.txt",
                "[패러디, 명탐정 코난] 가남：개국절호명미，와저주창 1-740 (완).txt",
                "패러디, 명탐정 코난"
            ),
            (
                "[언정][AI번역] 중생낭자전 1~1466(완).txt",
                "[언정] 중생낭자전 1-1466 (완).txt",
                "언정"
            ),
            (
                "[언정][AI번역][연대] 중생낭자재종전 1~1466(완).txt",
                "[언정, 연대물] 중생낭자재종전 1-1466 (완).txt",
                "언정, 연대물"
            ),
            (
                "[나루토패러디 시스템 AI번역] 푸른 용 1-633 완결.txt",
                "[패러디, 나루토, 시스템] 푸른 용 1-633 (완).txt",
                "패러디, 나루토, 시스템"
            ),
        ]

        for filename, expected_normalized, expected_genre in annotated_test_cases:
            task = NovelTask(
                original_path=Path(filename),
                current_path=Path(filename),
                raw_name=filename
            )
            # 1. 파일명 정규화(Stage 1.5) 선행 실행 (parse_only)
            task = self.normalizer.parse_only(task)
            assert task.genre == expected_genre
            assert task.source == "annotation"

            # 1.1 미리보기 이름 검증 (장르 태그가 포함되어야 함)
            preview_name = self.normalizer.preview_normalized_name(task)
            assert preview_name == expected_normalized

            # 1.2 소스 폴더에 즉시 저장되어 파일명이 변경되는 상황 시뮬레이션
            task.current_path = task.current_path.with_name(preview_name)

            # 2. 장르 추론(Stage 2) 후행 실행 (classify)
            classified_task = self.classifier.classify(task)
            assert classified_task.genre == expected_genre
            assert classified_task.source == "annotation"
            assert classified_task.confidence == "high"

            # 3. 최종 정규화(Stage 3) 검증
            normalized_task = self.normalizer.normalize(classified_task)
            assert normalized_task.metadata.get("normalized_name") == expected_normalized

    def test_user_reported_cases(self):
        """사용자가 보고한 4가지 오류 케이스 검증"""
        test_cases = [
            # Case 1: #패러디 #마블 해시태그 보존
            (
                "만위세계적맹왕 1-373 完 (AI번역) #패러디 #마블.txt",
                "[패러디, 마블] 만위세계적맹왕 1-373 (완).txt",
                "패러디, 마블"
            ),
            # Case 2: CJK 괄호 내 숫자/문장부호(중생54년) 원문 보존 및 공백 유지 (반각 및 전각 괄호)
            (
                "사합원 중생54년, 인거사주(四合院：重生54年，邻居傻柱) 1-668 완.txt",
                "사합원 중생54년, 인거사주(四合院：重生54年，邻居傻柱) 1-668 (완).txt",
                ""
            ),
            (
                "사합원 중생54년, 인거사주（四合院：重生54年，邻居傻柱） 1-668 완.txt",
                "사합원 중생54년, 인거사주(四合院：重生54年，邻居傻柱) 1-668 (완).txt",
                ""
            ),
            # Case 3: (19N) 에디션/등급 태그 순서 및 CJK 괄호 밀착 보존 (반각 및 전각 괄호)
            (
                "절세신기(绝世神器) (19N) 1-1053 완.txt",
                "절세신기(绝世神器) (19N) 1-1053 (완).txt",
                ""
            ),
            (
                "절세신기（绝世神器） (19N) 1-1053 완.txt",
                "절세신기(绝世神器) (19N) 1-1053 (완).txt",
                ""
            ),
            # Case 4: #패러디 #포켓몬스터 해시태그 보존
            (
                "저차부당훈련가료 1-698 完 (AI번역) #패러디 #포켓몬스터.txt",
                "[패러디, 포켓몬스터] 저차부당훈련가료 1-698 (완).txt",
                "패러디, 포켓몬스터"
            ),
        ]

        for filename, expected_normalized, expected_genre in test_cases:
            # 1. TitleAnchorExtractor 단독 정규화 검증
            parse_res = self.title_extractor.extract(filename)
            assert parse_res.to_normalized_filename() == expected_normalized, f"to_normalized_filename failed for {filename}"

            # 2. FilenameNormalizerAdapter 파이프라인 정규화 검증
            task = NovelTask(
                original_path=Path(filename),
                current_path=Path(filename),
                raw_name=filename
            )
            task = self.normalizer.parse_only(task)
            if expected_genre:
                assert task.genre == expected_genre
            preview = self.normalizer.preview_normalized_name(task)
            assert preview == expected_normalized, f"preview_normalized_name failed for {filename}"

            task = self.normalizer.normalize(task)
            assert task.metadata.get("normalized_name") == expected_normalized, f"normalize failed for {filename}"


