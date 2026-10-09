"""
==============================================================================
파일: core/adapters/genre_classifier_adapter.py
역할 및 목적:
    파이프라인 Stage 2를 담당하는 Search-First 장르 분류 어댑터 (`GenreClassifierAdapter`).
    캐시(Cache-First) → 웹 검색(Naver/Google Search-First) → 플랫폼 가중치 및 제목 유사도 검증
    → 키워드 사전 폴백(Fallback)의 엄격한 4단계 계층 구조를 거쳐 소설의 장르를 판정합니다.
    소설 특성 추출기(`NovelTraitExtractor`)와 결합하여 세부 태그(예: [언정, 궁투, 빙의])를 합성합니다.
주요 구성 요소:
    - GenreClassifierAdapter: 장르 분류 총괄 어댑터 클래스
    - classify(): 단일 NovelTask에 대한 장르 추론 및 task.genre 필드 확정
    - _search_and_extract(): NaverGenreExtractorV4 / GoogleGenreExtractor 연동 검색 실행
    - _classify_by_keywords(): 검색 실패 시 최종 로컬 키워드 폴백
상호 연관 관계 및 의존성:
    - Caller: core.pipeline_orchestrator.PipelineOrchestrator, scripts.*
    - Callee: modules.classifier.src.core.naver_genre_extractor_v4.NaverGenreExtractorV4,
              modules.classifier.src.core.google_genre_extractor.GoogleGenreExtractor,
              modules.classifier.src.core.genre_classifier.GenreClassifier,
              modules.classifier.api_config_manager.APIConfigManager,
              core.title_anchor_extractor.TitleAnchorExtractor,
              core.utils.genre_cache.GenreCache, core.utils.genre_mapping.GenreMappingLoader,
              core.utils.similarity.TitleSimilarityChecker, core.utils.novel_trait_extractor
수정 시 주의사항:
    - 웹 검색 전에 반드시 캐시와 화이트리스트 검증을 거쳐 불필요한 네트워크 API 호출 및 할당량 소진을 방지해야 합니다.
    - 검색 결과 제목과 원본 제목 간 유사도가 임계치(0.6 등) 미만일 경우 오분류를 방지하기 위해 기각해야 합니다.
==============================================================================
"""
import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, List

# 기존 모듈 경로 추가
_classifier_path = Path(__file__).parent.parent.parent / 'modules' / 'classifier'
_classifier_src_path = _classifier_path / 'src'

from core.novel_task import NovelTask
from core.pipeline_logger import PipelineLogger
from core.title_anchor_extractor import TitleAnchorExtractor
from core.utils.similarity import TitleSimilarityChecker
from core.utils.genre_mapping import GenreMappingLoader, get_mapping_loader
from core.utils.genre_cache import GenreCache, get_genre_cache
from config.pipeline_config import PipelineConfig, GENRE_WHITELIST


class GenreClassifierAdapter:
    """
    Search-First 장르 분류 어댑터
    
    분류 순서:
    1. 캐시 확인 (Cache-First)
    2. TitleAnchorExtractor로 순수 제목 추출
    3. Stage 1: 인터넷 검색 (Search-First) - NaverGenreExtractorV4 사용
    4. Stage 2: 플랫폼 우선순위 적용 + 제목 유사도 검증
    5. Stage 3: 키워드 폴백 (검색 실패 시에만)
    """
    
    def __init__(self, config: PipelineConfig, logger: Optional[PipelineLogger] = None):
        """
        Args:
            config: 파이프라인 설정
            logger: 파이프라인 로거 (없으면 기본 로거 생성)
        """
        self.config = config
        self.logger = logger or PipelineLogger(console_output=False)
        
        # 유틸리티 초기화
        self.title_extractor = TitleAnchorExtractor()
        self.mapping_loader = get_mapping_loader()
        self.cache = get_genre_cache()
        
        # 네이버 검색 추출기 (지연 초기화)
        self._naver_extractor = None
        # 구글 검색 추출기 (지연 초기화)
        self._google_extractor = None
        
        # 키워드 분류기 (지연 초기화)
        self._keyword_classifier = None
        self._initialized = False
        
        self.logger.info("[GenreClassifierAdapter] Search-First 모드로 초기화")
    
    def _ensure_initialized(self):
        """분류기 지연 초기화"""
        if self._initialized:
            return
        
        try:
            # 모듈 경로 설정
            classifier_core_path = _classifier_src_path / 'core'
            
            paths_to_add = [
                str(_classifier_path),
                str(_classifier_src_path),
                str(classifier_core_path),
            ]
            for p in paths_to_add:
                if p not in sys.path:
                    sys.path.insert(0, p)
            
            # APIConfigManager 초기화
            from modules.classifier.api_config_manager import APIConfigManager
            api_manager = APIConfigManager()
            naver_conf = api_manager.load_config()

            # NaverGenreExtractorV4 초기화 (실제 웹/API 검색)
            from modules.classifier.src.core.naver_genre_extractor_v4 import NaverGenreExtractorV4
            self._naver_extractor = NaverGenreExtractorV4(naver_api_config=naver_conf)
            self._naver_extractor.set_logger(self.logger) # 로거 주입 (터미널+파일 로그 동기화)
            self.logger.debug("NaverGenreExtractorV4 초기화 완료")

            # GoogleGenreExtractor 초기화 (Fallback)
            try:
                from modules.classifier.src.core.google_genre_extractor import GoogleGenreExtractor
                
                # APIConfigManager를 통해 키 로드 (Hybrid Security: Env -> Encrypted)
                google_conf = api_manager.load_google_config()
                
                if google_conf:
                    api_key = google_conf['api_key']
                    cse_id = google_conf['cse_id']
                    self.logger.debug("Google API 키를 APIConfigManager(.env/Encrypted)에서 로드했습니다.")
                else:
                    # PipelineConfig에서 폴백 (기존 설정 유지)
                    api_key = self.config.google_api_key
                    cse_id = self.config.google_cse_id
                    self.logger.debug("Google API 키를 PipelineConfig에서 로드했습니다.")

                self._google_extractor = GoogleGenreExtractor(api_key, cse_id)
                self.logger.debug("GoogleGenreExtractor 초기화 완료")
            except ImportError as e:
                self.logger.warning(f"GoogleGenreExtractor 초기화 실패: {e}")
                self._google_extractor = None
            
            # 키워드 분류기 초기화
            from modules.classifier.src.core.genre_classifier import GenreClassifier
            self._keyword_classifier = GenreClassifier(use_db=False)
            self.logger.debug("GenreClassifier 초기화 완료")
            
            self._initialized = True
            
        except Exception as e:
            self.logger.warning(f"분류기 초기화 실패: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            self._initialized = True  # 실패해도 재시도 방지
    
    def classify(self, task: NovelTask) -> NovelTask:
        """
        장르 분류 후 task 업데이트 (Search-First Strategy)
        
        Args:
            task: 분류할 NovelTask
            
        Returns:
            장르와 신뢰도가 업데이트된 NovelTask
        """
        self._ensure_initialized()
        
        # 분류할 텍스트 준비
        raw_text = task.title if task.title else task.raw_name
        
        if not raw_text:
            task.genre = '미분류'
            task.confidence = 'low'
            task.status = 'processing'
            return task
            
        from core.utils.novel_trait_extractor import NovelTraitExtractor
        from core.utils.novel_origin_detector import NovelOriginDetector, OriginResult

        # Step 1 & 1.5: 제목 및 국적 정보 획득 (전처리 단계 선행 완료 시 즉각 재활용, 미완료 시 추출)
        parse_source = task.metadata.get('original_raw_name') or task.raw_name or raw_text
        if task.title and task.metadata.get('country_origin'):
            pure_title = task.title
            author = task.author or ""
            side_story = task.side_story or ""
            foreign_title = task.metadata.get('original_foreign_title', '')
            phonetic_title = task.metadata.get('phonetic_title', '')
            translated_title = task.metadata.get('translated_title', '')
            foreign_title_type = task.metadata.get('foreign_title_type', '')
            origin_country = task.metadata.get('country_origin', 'UNKNOWN')
            is_foreign = task.metadata.get('is_foreign', False)
            origin_reasons = task.metadata.get('origin_reasons', [])

            origin_res = OriginResult(
                country=origin_country,
                confidence="high" if origin_country != "UNKNOWN" else "none",
                reasons=origin_reasons,
                is_foreign=is_foreign
            )
            self.logger.debug(f"  [전처리 연계] 제목: {pure_title}, 국적: {origin_country} ({'해외작' if is_foreign else '국내작'})")
        else:
            # 순수 제목 추출 (전체 파일명 원문 기반)
            parse_result = self.title_extractor.extract(parse_source)
            pure_title = parse_result.title if parse_result.title else (task.title or raw_text)
            author = parse_result.author
            side_story = parse_result.side_story
            foreign_title = parse_result.original_foreign_title or task.metadata.get('original_foreign_title', '')
            phonetic_title = getattr(parse_result, 'phonetic_title', '') or task.metadata.get('phonetic_title', '')
            translated_title = getattr(parse_result, 'translated_title', '') or task.metadata.get('translated_title', '')
            foreign_title_type = getattr(parse_result, 'foreign_title_type', '') or task.metadata.get('foreign_title_type', '')

            task.metadata['original_foreign_title'] = foreign_title
            task.metadata['phonetic_title'] = phonetic_title
            task.metadata['translated_title'] = translated_title
            task.metadata['foreign_title_type'] = foreign_title_type

            # 소설 국적(원산지) 판별 (KR / CN / JP / UNKNOWN) - 모든 리턴 이전에 항시 보장
            origin_res = NovelOriginDetector.detect(
                title=pure_title,
                raw_name=raw_text,
                foreign_title=foreign_title,
                file_path=task.current_path or task.original_path,
                genre=task.genre,
                phonetic_title=phonetic_title,
                translated_title=translated_title
            )
            task.metadata['country_origin'] = origin_res.country
            task.metadata['origin_reasons'] = origin_res.reasons
            task.metadata['is_foreign'] = origin_res.is_foreign

        # [Fix] 이미 유효한 장르가 설정되어 있는 경우 (예: 파일명 태그 추출 결과)
        # 검색이나 추가 추론 없이 기존 장르 유지
        if task.genre and task.genre != '미분류':
            primary_genre, existing_kws = NovelTraitExtractor.parse_existing_tag(task.genre)
            mapped_genre = self.mapping_loader.map_genre(primary_genre, task.title or raw_text, parse_source)
            mapped_genre = self._apply_origin_specific_rules(mapped_genre, task, raw_text)
            
            if mapped_genre in GENRE_WHITELIST:
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=task.title or raw_text,
                    existing_keywords=existing_kws
                )
                if not task.confidence or task.confidence == 'low':
                    task.confidence = 'high'
                if not task.source or task.source == '-':
                    task.source = 'tag'
                
                self.logger.debug(f"  [기존 장르 유지] {task.genre} (API 검색 건너뜀)")
                print(f"  [기존 장르 유지] {task.genre} (API 검색 건너뜀)")
                return self._finalize_task_genre(task, raw_text)
            
        # [첨언 우선 추출] 파일명의 앞 접두사([태그]) 또는 뒤 첨언(#해시태그 등)에서 장르 추출 (웹 검색보다 최우선)
        annotation_genre = NovelTraitExtractor.extract_from_annotations(parse_source)
        if annotation_genre:
            primary_genre, existing_kws = NovelTraitExtractor.parse_existing_tag(annotation_genre)
            mapped_genre = self.mapping_loader.map_genre(primary_genre)
            mapped_genre = self._apply_origin_specific_rules(mapped_genre, task, raw_text)
            if mapped_genre in GENRE_WHITELIST:
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=task.title or raw_text,
                    existing_keywords=existing_kws
                )
                task.confidence = 'high'
                task.source = 'annotation'
                task.status = 'processing'
                
                self.logger.debug(f"  [첨언 태그 감지] 파일명 첨언에서 장르 확정: {task.genre} (웹 검색 건너뜀)")
                print(f"  [첨언 태그 감지] {task.genre} (웹 검색 건너뜀)")
                
                # 캐시에도 저장
                self.cache.set(pure_title, task.genre, 'high', 'annotation')
                return task
        
        self.logger.debug(f"장르 분류 시작: {raw_text}")
        print(f"\n{'='*80}")
        print(f"[분류 시작] {raw_text}")
        
        # [제목 분석] 로그 추가
        import pprint
        analysis_data = {
            'main_title': pure_title,
            'subtitle': side_story,
            'author': author,
            'full_title': raw_text
        }
        formatted_analysis = pprint.pformat(analysis_data, width=120, sort_dicts=False)
        
        self.logger.debug(f"  [순수 제목] {pure_title}")
        print(f"  [순수 제목] {pure_title}")
        
        self.logger.debug(f"  [제목 분석] 원본: '{raw_text}' →\n{formatted_analysis}")
        print(f"  [제목 분석] 원본: '{raw_text}' → {analysis_data}")
        
        if author:
            self.logger.debug(f"  [저자] {author}")
            print(f"  [저자] {author}")
        
        if origin_res.country != "UNKNOWN":
            self.logger.debug(f"  [국적 판별] {origin_res.country} (confidence: {origin_res.confidence}, reasons: {origin_res.reasons})")
            print(f"  [국적 판별] {origin_res.country} ({'해외작' if origin_res.is_foreign else '국내작'}, {origin_res.reasons[0] if origin_res.reasons else ''})")
        
        # Step 2: 캐시 확인 (Cache-First: pure_title -> phonetic_title -> translated_title)
        cached = self.cache.get(pure_title)
        if not cached and phonetic_title:
            cached = self.cache.get(phonetic_title)
        if not cached and translated_title:
            cached = self.cache.get(translated_title)

        if cached:
            cached_genre = cached['genre']
            cached_conf = cached.get('confidence', 'medium')
            
            # 고신뢰도(high) 캐시는 즉시 확정 반환
            if cached_conf == 'high':
                primary_genre, existing_kws = NovelTraitExtractor.parse_existing_tag(cached_genre)
                corrected_genre = self._apply_origin_specific_rules(primary_genre, task, raw_text)
                if corrected_genre != '미분류':
                    task.genre = NovelTraitExtractor.format_genre_tag(
                        primary_genre=corrected_genre,
                        title=raw_text,
                        existing_keywords=existing_kws if corrected_genre == primary_genre else None
                    )
                    if task.genre != cached_genre:
                        self.cache.set(pure_title, task.genre, cached['confidence'], cached.get('source', 'cache'))
                        if phonetic_title and phonetic_title != pure_title:
                            self.cache.set(phonetic_title, task.genre, cached['confidence'], cached.get('source', 'cache'))
                        if translated_title and translated_title != pure_title:
                            self.cache.set(translated_title, task.genre, cached['confidence'], cached.get('source', 'cache'))
                        self.logger.debug(f"  [캐시 갱신] '{pure_title}': {cached_genre} → {task.genre}")

                    task.confidence = cached['confidence']
                    task.source = self._format_source(cached.get('source', 'cache'))
                    task.status = 'processing'
                    self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: cache)")
                    print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: cache)")
                    return self._finalize_task_genre(task, raw_text)

        # Step 2.5: 파일 도입부(헤더/시놉시스) 메타데이터 확인 (Header-First)
        header_result = self._extract_from_content_header(task)
        if header_result:
            mapped_genre = header_result['genre']
            mapped_genre = self._apply_origin_specific_rules(mapped_genre, task, raw_text)
            web_snippet = header_result.get('snippet', '')
            web_tags = header_result.get('tags', [])
            
            task.genre = NovelTraitExtractor.format_genre_tag(
                primary_genre=mapped_genre,
                title=raw_text,
                web_snippet=web_snippet,
                web_tags=web_tags
            )
            task.confidence = 'high'
            task.source = '본문헤더'
            task.status = 'processing'
            
            # 캐시에 저장
            self.cache.set(pure_title, task.genre, 'high', '본문헤더')
            if phonetic_title and phonetic_title != pure_title:
                self.cache.set(phonetic_title, task.genre, 'high', '본문헤더')
            if translated_title and translated_title != pure_title:
                self.cache.set(translated_title, task.genre, 'high', '본문헤더')
            
            self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: 본문헤더)")
            print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: 본문헤더)")
            return self._finalize_task_genre(task, raw_text)

        # Step 2.8: 로컬 고신뢰도 사전/분석기 패스트패스 (High-Confidence Local Fast-Path)
        # 특히 해외 소설(중국/일본)의 경우 불필요하고 실패율 높은 국내 검색(네이버) 지연을 건너뛰고,
        # 고신뢰도 음독 분석기, Syosetu 공식 API, 고가중치 장르 키워드로 즉시 확정하여 속도 및 정확도 극대화
        fast_res = self._fast_local_inference(
            task, pure_title, raw_text, foreign_title, origin_res,
            phonetic_title=phonetic_title, translated_title=translated_title
        )
        if fast_res and fast_res.get('genre') in GENRE_WHITELIST and fast_res.get('genre') != '미분류':
            mapped_genre = fast_res['genre']
            mapped_genre = self._apply_origin_specific_rules(mapped_genre, task, raw_text)
            if mapped_genre in GENRE_WHITELIST and mapped_genre != '미분류':
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=f"{raw_text} {phonetic_title} {translated_title}".strip(),
                    web_snippet=fast_res.get('snippet', ''),
                    web_tags=fast_res.get('tags', [])
                )
                task.confidence = fast_res.get('confidence', 'high')
                task.source = self._format_source(fast_res.get('source', '로컬패스트패스'))
                task.status = 'processing'
                
                # 캐시에 저장하여 이후 중복 처리 0ms 보장 (pure_title, phonetic_title, translated_title 모두 동시 인덱싱)
                self.cache.set(pure_title, task.genre, task.confidence, fast_res.get('source', 'fast_path'))
                if phonetic_title and phonetic_title != pure_title:
                    self.cache.set(phonetic_title, task.genre, task.confidence, fast_res.get('source', 'fast_path'))
                if translated_title and translated_title != pure_title:
                    self.cache.set(translated_title, task.genre, task.confidence, fast_res.get('source', 'fast_path'))
                
                self.logger.debug(f"  [로컬 패스트패스 확정] {task.genre} (confidence: {task.confidence}, source: {task.source})")
                print(f"  [로컬 패스트패스 확정] {task.genre} (confidence: {task.confidence}, source: {task.source})")
                return self._finalize_task_genre(task, raw_text)

        # 만약 고신뢰도 헤더/패스트패스에 해당하지 않지만, 기존 medium/low 캐시가 있는 경우
        # 불필요한 인터넷 검색을 방지하기 위해 캐시된 결과 적용
        if cached:
            cached_genre = cached['genre']
            primary_genre, existing_kws = NovelTraitExtractor.parse_existing_tag(cached_genre)
            corrected_genre = self._apply_origin_specific_rules(primary_genre, task, raw_text)
            if corrected_genre != '미분류':
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=corrected_genre,
                    title=raw_text,
                    existing_keywords=existing_kws if corrected_genre == primary_genre else None
                )
                if task.genre != cached_genre:
                    self.cache.set(pure_title, task.genre, cached['confidence'], cached.get('source', 'cache'))
                    if phonetic_title and phonetic_title != pure_title:
                        self.cache.set(phonetic_title, task.genre, cached['confidence'], cached.get('source', 'cache'))
                    if translated_title and translated_title != pure_title:
                        self.cache.set(translated_title, task.genre, cached['confidence'], cached.get('source', 'cache'))
                    self.logger.debug(f"  [캐시 갱신] '{pure_title}': {cached_genre} → {task.genre}")

                task.confidence = cached['confidence']
                task.source = self._format_source(cached.get('source', 'cache'))
                task.status = 'processing'
                self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: cache)")
                print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: cache)")
                return self._finalize_task_genre(task, raw_text)

        # Step 3: Stage 1 - 인터넷 검색 (Search-First) - Naver / Google / 해외플랫폼 웹 검색 우선 시도
        try:
            search_result = self._search_genre(
                pure_title, author, foreign_title,
                country=origin_res.country,
                phonetic_title=phonetic_title,
                translated_title=translated_title
            )
        except TypeError:
            search_result = self._search_genre(pure_title, author, foreign_title)
        
        if search_result and search_result.get('genre') and search_result.get('genre') != '미분류':
            genre = search_result['genre']
            
            # 장르 매핑 적용
            mapped_genre = self.mapping_loader.map_genre(genre, pure_title, raw_text)
            mapped_genre = self._apply_origin_specific_rules(mapped_genre, task, raw_text)
            
            # 화이트리스트 검증
            if mapped_genre in GENRE_WHITELIST:
                web_snippet = search_result.get('snippet', '')
                web_tags = search_result.get('tags', [])
                
                # 메인 장르 + 특징 키워드 조합 (최대 3개 항목)
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=f"{raw_text} {phonetic_title} {translated_title}".strip(),
                    web_snippet=web_snippet,
                    web_tags=web_tags
                )
                task.confidence = 'high'  # 검색 성공 = high
                task.status = 'processing'
                
                # 캐시에 저장
                source = search_result.get('source', 'search')
                task.source = self._format_source(source)
                self.cache.set(pure_title, task.genre, 'high', source)
                if phonetic_title and phonetic_title != pure_title:
                    self.cache.set(phonetic_title, task.genre, 'high', source)
                if translated_title and translated_title != pure_title:
                    self.cache.set(translated_title, task.genre, 'high', source)
                
                self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: {source})")
                print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: {source})")
                return self._finalize_task_genre(task, raw_text)
        
        # Step 4: Stage 3 - 키워드 및 음독 분석기 폴백 (검색 실패 시에만 안전망으로 실행)
        self.logger.debug(f"  [폴백] 검색 실패, 키워드/음독 매칭 시도")
        print(f"  [폴백] 검색 실패, 키워드/음독 매칭 시도")
        keyword_result = self._keyword_fallback(
            pure_title, raw_text, foreign_title,
            phonetic_title=phonetic_title,
            translated_title=translated_title
        )
        
        if keyword_result and keyword_result.get('genre') != '미분류':
            genre = keyword_result['genre']
            mapped_genre = self.mapping_loader.map_genre(genre, pure_title, raw_text)
            mapped_genre = self._apply_origin_specific_rules(mapped_genre, task, raw_text)
            if mapped_genre not in GENRE_WHITELIST:
                mapped_genre = '미분류'
                
            if mapped_genre != '미분류':
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=f"{raw_text} {phonetic_title} {translated_title}".strip()
                )
                src = keyword_result.get('source', 'keyword')
                task.confidence = 'medium'  # 폴백 매칭 = medium
                task.source = self._format_source(src)
                task.status = 'processing'
                
                # 캐시에 저장 (독음 및 번역명 동시 인덱싱)
                self.cache.set(pure_title, task.genre, 'medium', src)
                if phonetic_title and phonetic_title != pure_title:
                    self.cache.set(phonetic_title, task.genre, 'medium', src)
                if translated_title and translated_title != pure_title:
                    self.cache.set(translated_title, task.genre, 'medium', src)
                
                self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: {task.source})")
                print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: {task.source})")
                return self._finalize_task_genre(task, raw_text)
        
        # Step 5: 모든 방법 실패
        task.genre = '미분류'
        task.confidence = 'low'  # 실패 = low
        task.source = '-'
        task.status = 'processing'
        
        self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: none)")
        print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: none)")
        return task

    def _fast_local_inference(
        self,
        task: NovelTask,
        pure_title: str,
        raw_text: str,
        foreign_title: str,
        origin_res: Any,
        phonetic_title: str = "",
        translated_title: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        고신뢰도 로컬 사전 및 음독 분석기 패스트패스
        
        해외 소설(중국/일본)의 경우 불필요하고 실패율 높은 국내 검색(네이버) 지연을 건너뛰고,
        고신뢰도 음독 분석기, Syosetu 공식 API, 고가중치 장르 키워드로 즉시 확정하여 속도 및 정확도 극대화
        """
        try:
            is_foreign = getattr(origin_res, 'is_foreign', False) or getattr(origin_res, 'country', '') in ('CN', 'JP')
            country = getattr(origin_res, 'country', 'UNKNOWN')
            full_ctx = f"{raw_text} {pure_title} {foreign_title} {phonetic_title} {translated_title}".strip()

            # 1. 중국 소설 음독 분석기 고신뢰도 검사 (phonetic_title 우선 적용)
            from core.utils.chinese_phonetic_analyzer import ChinesePhoneticAnalyzer
            phonetic_res = ChinesePhoneticAnalyzer.analyze(raw_text, pure_title, phonetic_title=phonetic_title)
            if phonetic_res.is_detected and phonetic_res.confidence == 'high' and phonetic_res.genre in GENRE_WHITELIST:
                if is_foreign or phonetic_res.genre in ('선협', '언정', '패러디') or phonetic_res.matched_pattern:
                    return {
                        'genre': phonetic_res.genre,
                        'confidence': 'high',
                        'source': '음독분석기',
                        'snippet': '',
                        'reason': phonetic_res.reason
                    }

            # 2. 일본 소설 공식 Syosetu API 직접 검색 (일본 소설이거나 가나 문자가 포함된 경우)
            has_japanese = country == 'JP' or bool(re.search(r'[぀-ゟ゠-ヿ]', full_ctx))
            if has_japanese:
                try:
                    from modules.classifier.src.core.platform_extractors.foreign_extractors import SyosetuExtractor
                    s_extractor = SyosetuExtractor({}, {})
                    query_jp = foreign_title or phonetic_title or pure_title
                    s_res = s_extractor.direct_search(query_jp)
                    if s_res and s_res.get('genre') in GENRE_WHITELIST and s_res.get('genre') != '미분류':
                        return {
                            'genre': s_res['genre'],
                            'confidence': 'high',
                            'source': 'Syosetu_API',
                            'snippet': s_res.get('snippet', '')
                        }
                except Exception as se:
                    self.logger.debug(f"Syosetu fast search error: {se}")

            # 3. 고신뢰도 서브컬처/원작 패러디 검출 (확실한 고유 팬덤)
            from core.utils.novel_trait_extractor import PARODY_FANDOM_MAP
            for fandom_kw in PARODY_FANDOM_MAP.keys():
                if fandom_kw in full_ctx:
                    if is_foreign or any(pm in full_ctx for pm in ['패러디', '동인', '2차', '팬픽', '빙의', '환생', '트립', '치트', '시스템']) or fandom_kw in [
                        '워해머', '원신', '던만추', '블랙클로버', '엘든링', '오버로드', '이누야샤', '이토준지', '캄피오네',
                        '타입문', '페어리테일', '테니스의 왕자', '실력지상주의', '어과초', '뱅드림', '포켓몬', '나루토',
                        '원피스', '블리치', '주술회전', '귀멸의 칼날', '드래곤볼', '투라대륙', '두라지', '몬스터 헌터', '괴렵'
                    ]:
                        return {
                            'genre': '패러디',
                            'confidence': 'high',
                            'source': '패러디_고유팬덤',
                            'snippet': '',
                            'reason': f"원작/팬덤: {fandom_kw}"
                        }

            # 4. 키워드 사전에서 고가중치(Score >= 10, Conf >= 0.85) 단일/복합 키워드 매칭 및 음독/번역 교차 검증
            if is_foreign and self._keyword_classifier:
                # 4-1. 음독 제목 또는 순수 제목 매칭
                target_cand = phonetic_title or pure_title
                kw_res = self._keyword_classifier.classify_with_confidence(target_cand)
                
                # 4-2. 번역 제목 매칭 (조합형 제목일 경우)
                kw_trans = None
                if translated_title and translated_title != target_cand:
                    kw_trans = self._keyword_classifier.classify_with_confidence(translated_title)

                # 교차 검증: 독음과 번역명 모두 동일한 유효 장르를 가리키는 경우
                if kw_res and kw_trans and kw_res.get('primary_genre') == kw_trans.get('primary_genre'):
                    c_genre = kw_res.get('primary_genre')
                    if c_genre in GENRE_WHITELIST and c_genre != '미분류':
                        return {
                            'genre': c_genre,
                            'confidence': 'high',
                            'source': '키워드사전_교차검증',
                            'snippet': '',
                            'reason': f"독음/번역 일치: {c_genre}"
                        }

                if kw_res and kw_res.get('primary_genre') in GENRE_WHITELIST and kw_res.get('primary_genre') != '미분류':
                    if kw_res.get('score', 0) >= 10 and kw_res.get('confidence', 0) >= 0.85:
                        return {
                            'genre': kw_res['primary_genre'],
                            'confidence': 'high',
                            'source': '키워드사전',
                            'snippet': '',
                            'reason': f"매칭 키워드: {kw_res.get('matched_keywords', [])}"
                        }

                if kw_trans and kw_trans.get('primary_genre') in GENRE_WHITELIST and kw_trans.get('primary_genre') != '미분류':
                    if kw_trans.get('score', 0) >= 10 and kw_trans.get('confidence', 0) >= 0.85:
                        return {
                            'genre': kw_trans['primary_genre'],
                            'confidence': 'high',
                            'source': '번역명_키워드사전',
                            'snippet': '',
                            'reason': f"번역명 매칭 키워드: {kw_trans.get('matched_keywords', [])}"
                        }
        except Exception as e:
            self.logger.debug(f"로컬 고신뢰도 패스트패스 오류 (무시하고 검색 계속): {e}")

        return None

    def _search_genre(
        self,
        title: str,
        author: Optional[str] = None,
        original_foreign_title: str = "",
        country: str = "UNKNOWN",
        phonetic_title: str = "",
        translated_title: str = ""
    ) -> Optional[Dict]:
        """
        Stage 1: 인터넷 검색으로 장르 추출 (Naver / Google / 해외플랫폼 API)
        
        국가별 플랫폼 우선순위 자동 최적화 (KR/CN/JP):
        - JP (일본 소설): Syosetu API 우선 -> Google(일본 쿼리) -> Naver(국내 정발 폴백)
        - CN (중국 소설): Google(중국 플랫폼/원문 쿼리) -> Naver(국내 정발 폴백)
        - KR / UNKNOWN (국내 소설): Naver 우선 -> Google 폴백
        """
        try:
            search_title = f"{title} {author}" if author else title
            has_japanese = country == 'JP' or any(char in search_title for char in ['の', 'は', '를', '에', '～', '・']) or bool(re.search(r'[぀-ゟ゠-ヿ]', f"{search_title} {original_foreign_title} {phonetic_title}"))
            has_chinese = country == 'CN' or bool(re.search(r'[一-鿿]', f"{search_title} {original_foreign_title}")) or bool(phonetic_title)

            # =========================================================================
            # 전략 A: 일본 소설 (JP) 전용 검색 라우팅 (Syosetu API -> Google JP -> Naver)
            # =========================================================================
            if has_japanese:
                # 1. Syosetu API 직접 검색 (가장 빠르고 정확함)
                try:
                    from modules.classifier.src.core.platform_extractors.foreign_extractors import SyosetuExtractor
                    s_extractor = SyosetuExtractor({}, {})
                    s_query = original_foreign_title or phonetic_title or search_title
                    s_res = s_extractor.direct_search(s_query)
                    if s_res and s_res.get('genre') and s_res.get('genre') != '미분류':
                        self.logger.info(f"  [Syosetu API 검색 성공] {s_res['genre']}")
                        return s_res
                except Exception as se:
                    self.logger.debug(f"Syosetu direct search error: {se}")

                # 2. Google 일본어 특화 검색
                if self._google_extractor:
                    jp_query = f"{original_foreign_title} 小説" if original_foreign_title else (f"{phonetic_title} 小説" if phonetic_title else f"{search_title} 小説")
                    google_result = self._google_extractor.extract_genre(jp_query, country='JP')
                    if google_result and google_result.get('genre') and google_result.get('genre') != '미분류':
                        return google_result

                # 3. 국내 정발 라이선스 확인용 Naver 검색 (번역제목 우선 폴백)
                if self._naver_extractor:
                    naver_query = translated_title or search_title
                    naver_res = self._naver_extractor.extract_genre_from_title(naver_query, country='JP')
                    if naver_res and naver_res.get('genre') and naver_res.get('genre') != '미분류':
                        return {
                            'genre': naver_res['genre'],
                            'confidence': naver_res.get('confidence', 0.85),
                            'source': naver_res.get('source', 'naver_search'),
                            'snippet': naver_res.get('snippet', ''),
                            'tags': naver_res.get('tags', [])
                        }

                return None

            # =========================================================================
            # 전략 B: 중국 소설 (CN) 전용 검색 라우팅 (Google CN -> Naver 정발 폴백)
            # =========================================================================
            if has_chinese:
                # 1. Google 중국어/치뎬/바이두 백과 특화 검색 (원문 한자 또는 순수 독음 우선)
                if self._google_extractor:
                    if original_foreign_title:
                        cn_query = f"{original_foreign_title} 小说"
                    elif phonetic_title:
                        cn_query = f"{phonetic_title} 小说"
                    else:
                        cn_query = f"{search_title} 中国小说"

                    google_result = self._google_extractor.extract_genre(cn_query, country='CN')
                    if google_result and google_result.get('genre') and google_result.get('genre') != '미분류':
                        return google_result
                    
                    # 2차 쿼리 (원문 한자 단독 또는 독음 단독)
                    fallback_cn = original_foreign_title or phonetic_title
                    if fallback_cn and cn_query != fallback_cn:
                        google_result = self._google_extractor.extract_genre(fallback_cn, country='CN')
                        if google_result and google_result.get('genre') and google_result.get('genre') != '미분류':
                            return google_result

                # 2. 국내 정발(시리즈/카카오) 확인용 Naver 검색 (번역제목 우선)
                if self._naver_extractor:
                    naver_query = translated_title or search_title
                    naver_res = self._naver_extractor.extract_genre_from_title(naver_query, country='CN')
                    if (not naver_res or not naver_res.get('genre') or naver_res.get('genre') == '미분류') and original_foreign_title:
                        naver_res = self._naver_extractor.extract_genre_from_title(f"{search_title} {original_foreign_title}", country='CN')
                    if naver_res and naver_res.get('genre') and naver_res.get('genre') != '미분류':
                        return {
                            'genre': naver_res['genre'],
                            'confidence': naver_res.get('confidence', 0.88),
                            'source': naver_res.get('source', 'naver_search'),
                            'snippet': naver_res.get('snippet', ''),
                            'tags': naver_res.get('tags', [])
                        }

                return None

            # =========================================================================
            # 전략 C: 국내 소설 (KR / UNKNOWN) 기본 검색 라우팅 (Naver -> Google)
            # =========================================================================
            if self._naver_extractor:
                naver_query = translated_title or search_title
                result = self._naver_extractor.extract_genre_from_title(naver_query, country=country)
                
                # 검색 실패이고 원문 한자 제목이 있으면 재검색
                if (not result or not result.get('genre') or result.get('genre') == '미분류') and original_foreign_title:
                    result = self._naver_extractor.extract_genre_from_title(f"{title} {original_foreign_title}", country=country)
                    if not result or not result.get('genre') or result.get('genre') == '미분류':
                        result = self._naver_extractor.extract_genre_from_title(original_foreign_title, country=country)
                
                # 커뮤니티 소스 필터링 및 Google 공식 확인
                is_community_source = bool(result and any(s in result.get('source', '').lower() for s in ['소설넷', 'novelnet', 'webtoon', 'mrblue']))
                if is_community_source and self._google_extractor:
                    google_res = self._google_extractor.extract_genre(search_title, country=country)
                    if google_res and google_res.get('genre') and google_res.get('genre') != '미분류':
                        if google_res.get('source', '').startswith('Google_Official') or google_res.get('confidence', 0) >= result.get('confidence', 0):
                            self.logger.info(f"  [공식 플랫폼 우선] 커뮤니티('{result['genre']}') 대신 Google 공식 플랫폼 장르('{google_res['genre']}') 채택")
                            result = google_res

                if result and result.get('genre') and result.get('genre') != '미분류':
                    return {
                        'genre': result['genre'],
                        'confidence': result.get('confidence', 0.9),
                        'source': result.get('source', 'naver_search'),
                        'snippet': result.get('snippet', ''),
                        'tags': result.get('tags', [])
                    }

            # Naver 실패 시 Google 폴백
            if self._google_extractor:
                google_result = self._google_extractor.extract_genre(search_title, country=country)
                if google_result and google_result.get('genre') and google_result.get('genre') != '미분류':
                    return google_result

            return None
            
        except Exception as e:
            self.logger.warning(f"검색 중 오류: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    def _apply_origin_specific_rules(self, mapped_genre: str, task: NovelTask, raw_text: str) -> str:
        """
        국적(원산지) 판별 결과에 따른 장르 보정 규칙 적용
        - 중국 소설(CN): 사합원은 기본 '현판' (여성향 클리셰 부재 시), 로맨스/로판은 '언정', 선협 키워드는 '선협'
        - 일본 소설(JP): 악역영애/익애 등은 '로판', 이세계/전생은 '판타지' 보장
        """
        origin = task.metadata.get('country_origin', 'UNKNOWN')
        foreign_title = task.metadata.get('original_foreign_title', '')
        full_ctx = f"{raw_text} {task.title} {foreign_title}".strip()

        # 0. 핵심 제목/클리셰 보장 규칙 (국적 불문 최우선)
        # SF 보장
        if any(kw in full_ctx for kw in ['영능자불사우창화', '영능자', '창화', '사이버펑크']):
            return 'SF'

        # 스포츠 보장
        if any(kw in full_ctx for kw in ['발롱도르', '스트라이커', '좌완파이어볼러', '파이어볼러', '프리미어리그', '챔피언스리그', '손흥민', '메시', '호날두', '미드필더', '구호반', '화오교죽마관선료', '화오교죽마']):
            return '스포츠'

        # 무협 보장
        if any(kw in full_ctx for kw in ['항마신장', '항마장', '언가군림', '인주란', '군림', '검혼기행', '뇌룡검제', '종무', '국술！대종사', '국술!대종사', '국술', '대종사', '횡추궤괴', '극도무성', '횡추무도', '용상반약공', '고룡세계리적끽과검객', '고룡세계']):
            return '무협'

        # 선협 보장
        if any(kw in full_ctx for kw in ['장생요도', '자소도주', '요도', '도주', '주명승도', '주선', '차천', '태일도과', '도과', '할편공법', '풍비사숙', '화장장', '희신', '아시선']):
            return '선협'

        # 패러디 보장 (신비의 제왕 / 서브컬처 동인 / 투라대륙 본체종 / 몬헌 / 왕좌의게임 / 타입문 / 코난 / 해리포터)
        if any(kw in full_ctx for kw in [
            '새로운 흑황제', '흑황제의 강림', '치신세계', '궤비：치신세계', '궤비:치신세계', '두라지', '두라', '斗罗',
            '베이커가', '사신은 순애', '인재탄서', '탄서', '진흥본체종', '본체종',
            '괴렵', '화룡유특성', '권유', '위새리사', '삼두룡', '항종', '타입문', '커쉐', '발짝만큼의 거리', '발짝만큼'
        ]):
            return '패러디'

        # 역사 보장 (삼국지/초한지/만명/장안/대체역사 만반도/출룡/포화호선/명령여징복)
        if any(kw in full_ctx for kw in ['촉한지장가한', '초한지', '대진제국', '장안호', '활재만명', '만명', '장안', '판도충', '만반도', '출룡', '포화호선', '첩영', '명령여징복', '화의금화']):
            return '역사'
        if '촉한' in full_ctx and mapped_genre in ['무협', '판타지', '미분류']:
            return '역사'

        # 언정 보장 (중국 여성향 번역/음독/쾌천/표고양/금욕불자/통고금/허니만장)
        if any(kw in full_ctx for kw in [
            '중생후왕비함어료', '중생후왕비', '함어료', '농가소복녀', '소복녀', '70년대로 천월', '일품용화', '용화', '제일교',
            '쾌천', '표고양', '금욕불자', '앵앵괴', '소조종', '초시통고금', '허니만장광망호', '허니만장', '첨우야', '여배각성후', '여배'
        ]):
            return '언정'

        # 겜판 보장
        if any(kw in full_ctx for kw in ['해상구생', '저유희야태진실료']):
            return '겜판'

        # 판타지 보장 (천도도서관 / 성장 모험 / 구일음락가 / 해도왕권 / 희랍대악인)
        if any(kw in full_ctx for kw in ['천도도서관', '활과 검', '구일음락가', '음락가', '해도왕권', '희랍대악인']):
            return '판타지'

        # 현판 보장 (전문가/학원가/회사/제천무한/생활계/속성점/전민/전직/엔딩요정/아포칼립스/화오/항도/호림원)
        if any(kw in full_ctx for kw in [
            '대치동 클래스', '대치동', '다차원 파견 회사', '파견 회사', '수많은 세계, 쉐임리스', '쉐임리스부터 시작한다', '수많은 세계',
            '시간을 가르는 나의 정체성', '생활계', '생활계직업', '속성점', '일근육', '인재동경', '전민령주', '전민진화', '전직법사', '저정류', '종예',
            '제천', '종극화력', '중회', '중회1980', '중회1981', '소주를 부르는 횟집', '목표는 엔딩 요정', '엔딩 요정', '데드 엔드', '반격',
            '금점층대보', '호림원', '호림', '장악최면지력', '최면지력', '초가전', '령원구', '항도1980', '항도', '화오：', '화오:종', '환불기방대', '매방료', '회당07', '회당', '학신전'
        ]):
            return '현판'
        
        # 중국 소설 또는 중국 특성 감지 시 로맨스/로판 계열은 무조건 '언정'으로 전환
        if mapped_genre in ['로판', '로맨스', '로맨스판타지'] or '로판' in mapped_genre or '로맨스' in mapped_genre:
            if origin == 'CN' or self.mapping_loader.is_chinese_romance(task.title or raw_text, full_ctx):
                task.metadata['country_origin'] = 'CN'
                task.metadata['is_foreign'] = True
                return '언정'

        # 1. 중국 소설 (CN) 규칙
        if origin == 'CN':
            # 사합원 규칙 (최우선): 사합원물은 치뎬 남성향 연대/도시물이 주류이므로 여성향 클리셰가 없으면 무조건 '현판'
            is_sahapwon = any(kw in full_ctx for kw in ['사합원', '四合院', '4합원'])
            if is_sahapwon:
                female_keywords = [
                    '여주', '교처', '낭자', '단총', '복보', '천금', '궁투', '택투',
                    '시어머니', '시집', '포태', '소내포', '아내', '부군', '공간물자', '수신공간'
                ]
                has_female = any(fk in full_ctx for fk in female_keywords)
                return '언정' if has_female else '현판'

            # 로맨스/로판 계열은 언정으로 전환
            if mapped_genre in ['로판', '로맨스', '로맨스판타지'] or '로판' in mapped_genre or '로맨스' in mapped_genre:
                return '언정'
            # 중생(重生) 규칙: 여성향 단서가 없는데 언정으로 분류된 경우, 남성향 도시/경영/일상/창업은 '현판'으로 보정
            if mapped_genre == '언정':
                female_keywords = [
                    '여주', '교처', '낭자', '단총', '복보', '천금', '궁투', '택투',
                    '시어머니', '시집', '포태', '소내포', '부군', '이혼', '리혼'
                ]
                has_female = any(fk in full_ctx for fk in female_keywords)
                if not has_female and any(mk in full_ctx for mk in ['중생', '몰상', '이신', '아진', '아태', '상인', '재벌', '창업', '대학', '도시']):
                    return '현판'
            # 궁투/농가/교처 등이 포함되어 있는데 역사로 잘못 분류된 경우 -> 언정
            if mapped_genre == '역사' and any(kw in full_ctx for kw in ['지청', '知青', '궁투', '宫斗', '농가', '농문', '교처', '복보', '천금', '택투']):
                return '언정'
            # 수선/선협 키워드가 강한데 판타지/무협/퓨판/현판으로 분류된 경우 -> 선협
            if mapped_genre in ['판타지', '무협', '퓨판', '현판', '미분류'] and any(kw in full_ctx for kw in ['대승기', '大乘期', '수선', '修仙', '수진', '修真', '선협', '仙侠', '축기', '원영', '금단', '비승']):
                return '선협'
            # 투라대륙(두라) 패러디 소설
            if any(kw in full_ctx for kw in ['두라지', '두라', '斗罗']):
                return '패러디'
                
        # 2. 일본 소설 (JP) 규칙
        elif origin == 'JP':
            # 악역영애/약혼파기/익애 등 여성향 클리셰는 로판 보장
            if any(kw in full_ctx for kw in ['악역영애', '悪役令嬢', '약혼파기', '婚約破棄', '익애', '溺愛', '영애']):
                return '로판'
            # 이세계/전생/치트/추방 등은 판타지
            if mapped_genre in ['현판', '퓨판'] and any(kw in full_ctx for kw in ['이세계', '異世界', '슬로우라이프', 'スローライフ', '추방', '追放']):
                return '판타지'
                
        return mapped_genre

    def _finalize_task_genre(self, task: NovelTask, raw_text: str = "") -> NovelTask:
        """
        최종 태스크 장르 정합성 보장:
        1. '신무협'은 항상 '무협'으로 통일
        2. '시스템'은 주 장르가 아니므로 부가 키워드로만 취급하고 실제 주 장르로 교정
        3. 중국 소설(CN)의 경우 '로판' 또는 '로맨스'는 예외 없이 '언정'으로 일괄 통일
        """
        if not task.genre or task.genre == '미분류':
            return task

        from core.utils.novel_trait_extractor import NovelTraitExtractor
        primary_g, traits = NovelTraitExtractor.parse_existing_tag(task.genre)

        # 1. 신무협 -> 무협 정규화
        if primary_g in ('신무협', '퓨전무협', '전통무협', '전통 무협') or '신무협' in primary_g or '신무협' in task.genre:
            primary_g = '무협'

        # 2. 시스템 주 장르 배제 및 부가 키워드화
        if primary_g == '시스템' or not primary_g or '시스템' in task.genre:
            if primary_g == '시스템' or not primary_g:
                primary_g = '현판'
            if '시스템' not in traits:
                traits = ['시스템'] + [t for t in traits if t != '시스템']

        task.genre = NovelTraitExtractor.format_genre_tag(
            primary_genre=primary_g,
            title=task.title or raw_text,
            existing_keywords=traits
        )
        primary_g, traits = NovelTraitExtractor.parse_existing_tag(task.genre)

        # 3. 중국 소설 언정 통일
        origin = task.metadata.get('country_origin', 'UNKNOWN')
        foreign_title = task.metadata.get('original_foreign_title', '')
        full_text = f"{raw_text} {task.title} {task.raw_name} {foreign_title}".strip()
        is_cn = origin == 'CN' or self.mapping_loader.is_chinese_romance(task.title or raw_text, full_text)
        
        if is_cn:
            if primary_g in ['로판', '로맨스', '로맨스판타지'] or '로판' in primary_g or '로맨스' in primary_g:
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre='언정',
                    title=task.title or raw_text,
                    existing_keywords=traits
                )
                task.metadata['country_origin'] = 'CN'
                task.metadata['is_foreign'] = True
        return task

    def _extract_from_content_header(self, task: NovelTask) -> Optional[Dict]:
        """
        소설 텍스트 파일(.txt)의 앞부분(2~4KB) 헤더에서 장르/태그/시놉시스/번역제목 메타데이터 추출
        
        Args:
            task: 분류할 NovelTask
            
        Returns:
            {'genre': str, 'confidence': str, 'snippet': str, 'tags': list, 'source': str} 또는 None
        """
        file_path = task.current_path or task.original_path
        if not file_path:
            return None
            
        try:
            from core.utils.content_header_extractor import ContentHeaderGenreExtractor
            header_res = ContentHeaderGenreExtractor.extract_from_file(file_path)
            if not header_res:
                return None

            pure_title = task.title or task.raw_name

            # 1. 명시적 raw_genre가 존재하는 경우
            if header_res.raw_genre:
                mapped_genre = self.mapping_loader.map_genre(header_res.raw_genre, pure_title, task.raw_name)
                if mapped_genre in GENRE_WHITELIST and mapped_genre != '미분류':
                    self.logger.debug(f"  [본문 헤더 감지] 원시 장르: '{header_res.raw_genre}' → 표준 장르: '{mapped_genre}', 태그: {header_res.tags}")
                    return {
                        'genre': mapped_genre,
                        'raw_genre': header_res.raw_genre,
                        'confidence': 'high',
                        'snippet': header_res.snippet,
                        'tags': header_res.tags,
                        'source': '본문헤더'
                    }

            # 2. 태그 목록(tags) 중 유효한 장르 매핑 확인
            if header_res.tags:
                for tag in header_res.tags:
                    mapped_tag = self.mapping_loader.map_genre(tag, pure_title, task.raw_name)
                    if mapped_tag in GENRE_WHITELIST and mapped_tag != '미분류':
                        self.logger.debug(f"  [본문 헤더 태그 감지] 태그: '{tag}' → 표준 장르: '{mapped_tag}'")
                        return {
                            'genre': mapped_tag,
                            'raw_genre': tag,
                            'confidence': 'high',
                            'snippet': header_res.snippet,
                            'tags': header_res.tags,
                            'source': '헤더태그'
                        }

            # 3. 본문 헤더에 번역본 제목(translated_title)이 존재하는 경우 키워드 매칭
            if header_res.translated_title:
                tt_res = self._keyword_fallback(header_res.translated_title, header_res.translated_title, '')
                if tt_res and tt_res.get('genre') in GENRE_WHITELIST and tt_res.get('genre') != '미분류':
                    self.logger.debug(f"  [본문 헤더 번역제목 감지] '{header_res.translated_title}' → 장르: '{tt_res['genre']}'")
                    return {
                        'genre': tt_res['genre'],
                        'raw_genre': header_res.translated_title,
                        'confidence': 'high',
                        'snippet': header_res.snippet,
                        'tags': header_res.tags,
                        'source': '헤더번역제목'
                    }

            # 4. 시놉시스(snippet) 텍스트를 이용한 키워드 매칭 (명시적 작품소개 블록이 존재하는 경우에만 장르 추론)
            if getattr(header_res, 'has_explicit_synopsis', False) and header_res.snippet and len(header_res.snippet.strip()) >= 15:
                syn_res = self._keyword_fallback(header_res.snippet[:400], header_res.snippet[:400], '')
                if syn_res and syn_res.get('genre') in GENRE_WHITELIST and syn_res.get('genre') != '미분류':
                    self.logger.debug(f"  [본문 헤더 시놉시스 감지] 장르: '{syn_res['genre']}'")
                    return {
                        'genre': syn_res['genre'],
                        'raw_genre': 'synopsis',
                        'confidence': 'medium',
                        'snippet': header_res.snippet,
                        'tags': header_res.tags,
                        'source': '헤더시놉시스'
                    }

        except Exception as e:
            self.logger.debug(f"본문 헤더 추출 실패: {e}")
            
        return None

    def _keyword_fallback(
        self,
        title: str,
        raw_text: str = "",
        foreign_title: str = "",
        phonetic_title: str = "",
        translated_title: str = ""
    ) -> Optional[Dict]:
        """
        Stage 3: 키워드 기반 폴백 분류 (CJK 원문 제목 결합 및 독음/번역 분해 지원)
        
        Args:
            title: 순수 제목
            raw_text: 원본 파일명 (선택)
            foreign_title: CJK 원문 제목 (선택)
            phonetic_title: 한국식 독음 제목 (선택)
            translated_title: 한국어 번역 제목 (선택)
            
        Returns:
            {'genre': str, 'confidence': float} 또는 None
        """
        if not self._keyword_classifier:
            return None
        
        try:
            source = 'keyword'
            result = self._keyword_classifier.classify_with_confidence(title)
            genre = result.get('primary_genre', '미분류')
            confidence = result.get('confidence', 0.0)
            
            # 독음 제목 또는 번역 제목으로 재시도
            if genre == '미분류' and phonetic_title and phonetic_title != title:
                p_res = self._keyword_classifier.classify_with_confidence(phonetic_title)
                if p_res.get('primary_genre') != '미분류':
                    genre = p_res.get('primary_genre')
                    confidence = p_res.get('confidence', 0.0)

            if genre == '미분류' and translated_title and translated_title != title:
                t_res = self._keyword_classifier.classify_with_confidence(translated_title)
                if t_res.get('primary_genre') != '미분류':
                    genre = t_res.get('primary_genre')
                    confidence = t_res.get('confidence', 0.0)

            # 순수 제목에서 미분류인 경우 원본 파일명으로 재시도
            if genre == '미분류' and raw_text and raw_text != title:
                raw_result = self._keyword_classifier.classify_with_confidence(raw_text)
                if raw_result.get('primary_genre') != '미분류':
                    genre = raw_result.get('primary_genre')
                    confidence = raw_result.get('confidence', 0.0)

            # CJK 원문 제목이 있는 경우 원문 결합 텍스트로 재시도
            if genre == '미분류' and foreign_title:
                cjk_combo = f"{title} {foreign_title}".strip()
                cjk_result = self._keyword_classifier.classify_with_confidence(cjk_combo)
                if cjk_result.get('primary_genre') != '미분류':
                    genre = cjk_result.get('primary_genre')
                    confidence = cjk_result.get('confidence', 0.0)
                else:
                    # CJK 원문 단독 재시도
                    cjk_single = self._keyword_classifier.classify_with_confidence(foreign_title)
                    if cjk_single.get('primary_genre') != '미분류':
                        genre = cjk_single.get('primary_genre')
                        confidence = cjk_single.get('confidence', 0.0)

            # 중국 소설 음독/번역투 분석기(ChinesePhoneticAnalyzer) 적용 (안전망)
            try:
                from core.utils.chinese_phonetic_analyzer import ChinesePhoneticAnalyzer
                phonetic_res = ChinesePhoneticAnalyzer.analyze(raw_text, title, phonetic_title=phonetic_title)
                if phonetic_res.is_detected and phonetic_res.genre != '미분류':
                    if genre == '미분류' or phonetic_res.confidence == 'high':
                        genre = phonetic_res.genre
                        confidence = 0.95 if phonetic_res.confidence == 'high' else 0.85
                        source = '음독분석기'
                        self.logger.debug(f"  [음독 분석기 감지] {raw_text} -> {genre} ({phonetic_res.reason})")
            except Exception as pe:
                self.logger.debug(f"음독 분석기 오류: {pe}")

            # CJK 번역투 및 클리셰 컨텍스트 기반 장르 추론 (기존 키워드로 미분류일 때 추가 안전망)
            if genre == '미분류':
                full_ctx = f"{raw_text} {title} {foreign_title} {phonetic_title} {translated_title}".strip()

                # 1. 패러디 클리셰 (서브컬처/원작 패러디)
                if any(kw in full_ctx for kw in [
                    '호그와트', '해리포터', '슬리데린', '그리핀도르', '홈랜더', '모리어티',
                    '엘든링', '애이등법환', '두파', '소훈아', '투라대륙', '무혼', '라삼포', '류이룡',
                    '빙여화', '하치만', '내청코', '악타입', '사천왕', '제넨사', '키자루', '호흡법',
                    '귀멸', '탄서성공', '새마낭', '우마무스메', '천룡인', '최면어플',
                    '새로운 흑황제', '흑황제의 강림', '치신세계', '궤비：치신세계', '궤비:치신세계', '신비의 제왕',
                    '두라지', '두라', '斗罗', 'MC계통', '마인크래프트', '포켓몬', '나루토', '원피스', '블리치',
                    '베이커가', '베이커', '사신은 순애', '인재탄서', '탄서', '진흥본체종', '본체종',
                    '워해머', '원신', '던만추', '블랙클로버', '오버로드', '이누야샤', '이토준지', '캄피오네',
                    '페어리테일', '테니스의 왕자', '어과초', '실력지상주의', '뱅드림', '모던패밀리', '서유기',
                    '초사이어인', '손오공', '베지터', '드래곤볼'
                ]):
                    genre = '패러디'
                    confidence = 0.92

                # 2. 선협/수진 클리셰 (대승기, 종문, 선협 명작 등)
                elif any(kw in full_ctx for kw in [
                    '광음지외', '구마', '선역', '무동건곤', '심공피안', '아사형실재태온건료',
                    '대겁주', '선옥', '도가선자', '참요무성', '헌제성신', '수설저정류전', '흑백무제',
                    '군성지자도혼록', '구신지전', '망장천', '선마녀', '대황수야인',
                    '대승기', '大乘期', '수선', '修仙', '선협', '仙侠', '축기', '금단', '원영', '노조', '홍황', '봉신',
                    '자소도주', '도주', '요도', '주명승도', '주선', '차천',
                    '대사저', '수선자', '역근경', '사형제'
                ]):
                    genre = '선협'
                    confidence = 0.92

                # 3. 공포 / 괴담
                elif any(kw in full_ctx for kw in [
                    '444번 병원', '444호', '괴담', '괴이', '흉가', '악령', '퇴마', '오컬트',
                    '괴이관리국', '미제사건', '동경괴담', '폐가'
                ]):
                    genre = '공포'
                    confidence = 0.9

                # 4. 현판 전문가/직업/도시물/말세
                elif any(kw in full_ctx for kw in [
                    '판사', '래퍼', '요리', '알바생', '생화학자', '스트리머', '회장님', '보디가드',
                    '심부름센터', '디자이너', '작곡천재', '공무원', '의원님', '호래오', '할리우드',
                    '오락시대', '만화대사', '건스미스', '파일럿', '미전실', '먹방', '야쿠자',
                    '신시대예술가', '특기가 분신술', '구조 조정', '국민연금', '이능자', '학패',
                    '대치동', '파견 회사', '수많은 세계', '시간을 가르는 나의 정체성',
                    '말세', '末世', '아포칼립스', '좀비', '무한 복제', '복제', '무한류',
                    '생활계', '생활계직업', '속성점', '일근육', '전민령주', '전민진화', '전직법사', '전직', '저정류', '종예', '인재동경',
                    '제천', '종극화력', '중회', '중회1980', '중회1981', '소주를 부르는 횟집', '목표는 엔딩 요정', '엔딩 요정', '데드 엔드', '반격'
                ]):
                    genre = '현판'
                    confidence = 0.88

                # 5. 무협 클리셰
                elif any(kw in full_ctx for kw in [
                    '당문', '세가', '악귀나찰', '무인 이곽', '이곽', '일대종사', '멸문', '자객',
                    '련무태난', '합성계무사', '북산철벽', '신마경천기', '천하를 쥐다', '난세서', '난세',
                    '항마신장', '항마장', '항마', '군림', '언가군림', '인주란', '제룡', '검혼기행', '뇌룡검제', '종무'
                ]):
                    genre = '무협'
                    confidence = 0.9

                # 6. 역사 클리셰
                elif any(kw in full_ctx for kw in [
                    '초한지', '만당', '과거', '위관', '출사', '흥가', '공명로', '관군신조',
                    '국사무쌍', '국자감', '민국', '북송', '촉한', '청천', '탐화', '촉한지장가한', '삼국지',
                    '장안호', '장안', '만명', '활재만명', '판도충', '만반도'
                ]):
                    genre = '역사'
                    confidence = 0.88

                # 7. 언정 및 여성향 연대물
                elif any(kw in full_ctx for kw in [
                    '사합원', '四合院', '여배', '반파', '년대문', '녹차녀', '만급녹차', '도혼', '맹보',
                    '대료', '고낭', '처자', '부인', '교처', '적녀', '서녀', '시집', '계실자',
                    '공부가식', '공부귀식', '과수홍아', '권신', '경야욕전환', '다자다복', '성친불원방',
                    '십리방비', '소농녀', '지청', '천억 물자', '억만 물자', '적장녀', '명문장녀',
                    '서장자', '후문독비', '재입후문', '첩신아환', '아낭사가', '녀제', '후비', '독비',
                    '아기님', '편집태자', '사둔후폐하', '울어봐 빌어도 좋고', '구고양저',
                    '농가소복녀', '소복녀', '중생후왕비', '함어료', '중생후왕비함어료',
                    '일품용화', '용화', '70년대로 천월', '천월', '제일교'
                ]):
                    female_keywords = ['여주', '교처', '낭자', '단총', '복보', '천금', '궁투', '택투', '시집', '부인']
                    if '사합원' in full_ctx:
                        genre = '언정' if any(fk in full_ctx for fk in female_keywords) else '현판'
                    else:
                        genre = '언정'
                    confidence = 0.88

                # 8. 판타지
                elif any(kw in full_ctx for kw in [
                    '성자', '사제', '마갑', '엑스트라 지갑송', '방개나개녀무', '정령', '비륜대륙',
                    '마녀', '권왕마녀', '스켈레톤', '세계수', '최애캐', '용자', '현환', '타람',
                    '숲의 종족', '세모', '恶魔', '감옥', '비아니스', '빌아니시', '천도도서관', '활과 검'
                ]):
                    genre = '판타지'
                    confidence = 0.88

                # 9. 겜판
                elif any(kw in full_ctx for kw in [
                    '속성반', '속성판', '마투', '치트모드', '히든피스', '공로구생', '도생', '무진해양', '랭커'
                ]):
                    genre = '겜판'
                    confidence = 0.88

                # 10. 퓨판: 스팀펑크 / SF / 재변
                elif any(kw in full_ctx for kw in [
                    '스팀펑크', '말일', '말일락원', '증기붕극', '유토피아', '복활전인류', '재변', '제1서열', '제일서렬', '특이점',
                    '가문의 서자', '서자가 돌아왔다'
                ]):
                    genre = '퓨판'
                    confidence = 0.88

                # 11. 스포츠
                elif any(kw in full_ctx for kw in ['좌완파이어볼러', '파이어볼러', '야구', '투수', '홈런', '발롱도르', '스트라이커']):
                    genre = '스포츠'
                    confidence = 0.9

            # 장르 매핑 적용
            mapped_genre = self.mapping_loader.map_genre(genre)
            
            # 화이트리스트 검증
            if mapped_genre not in GENRE_WHITELIST:
                mapped_genre = '미분류'
            
            return {
                'genre': mapped_genre,
                'confidence': confidence,
                'source': source
            }
            
        except Exception as e:
            self.logger.warning(f"키워드 분류 중 오류: {e}")
            return None
    
    def _format_source(self, source: str) -> str:
        """
        source 문자열을 사용자 친화적인 형태로 변환
        
        Args:
            source: 원본 source 문자열 (예: 'naver_문피아_meta_path')
            
        Returns:
            사용자 친화적인 source 문자열 (예: '문피아')
        """
        if not source:
            return '-'
        
        source_lower = source.lower()
        
        # 플랫폼 이름 매핑
        platform_map = {
            '리디북스': '리디북스',
            'ridibooks': '리디북스',
            '문피아': '문피아',
            'munpia': '문피아',
            '네이버시리즈': '네이버시리즈',
            'naver_series': '네이버시리즈',
            '카카오페이지': '카카오페이지',
            'kakaopage': '카카오페이지',
            '소설넷': '소설넷',
            'novelnet': '소설넷',
            '노벨피아': '노벨피아',
            'novelpia': '노벨피아',
            '조아라': '조아라',
            'joara': '조아라',
            '웹툰가이드': '웹툰가이드',
            'webtoonguide': '웹툰가이드',
            '미스터블루': '미스터블루',
            'mrblue': '미스터블루',
            '교보문고': '교보문고',
            'kyobo': '교보문고',
            'yes24': 'YES24',
            '알라딘': '알라딘',
            'aladin': '알라딘',
            '치뎬': '치뎬',
            'qidian': '치뎬',
            '진장문학성': '진장문학성',
            'jjwxc': '진장문학성',
            '바이두백과': '바이두백과',
            'baike': '바이두백과',
            '소설가가되자': '소설가가되자',
            'syosetu': '소설가가되자',
            '카쿠요무': '카쿠요무',
            'kakuyomu': '카쿠요무',
            '하멜른': '하멜른',
            '디시': '디시인사이드',
            'dcinside': '디시인사이드',
            '아카라이브': '아카라이브',
            'arca': '아카라이브',
            '나무위키': '나무위키',
            'namu': '나무위키',
            'websearch': '웹검색',
            'google': 'Google',
            'naver': '네이버',
            '음독분석기': '음독분석기',
            '음독': '음독분석기',
            'keyword': '키워드',
            'cache': '캐시',
            'user': '사용자',
            '본문헤더': '본문헤더',
        }
        
        # 플랫폼 이름 추출 (naver_문피아_meta_path → 문피아)
        for key, value in platform_map.items():
            if key in source_lower or key in source:
                return value
        
        # 매핑되지 않은 경우 원본 반환 (첫 글자 대문자)
        return source.split('_')[0].capitalize() if '_' in source else source
    
    def classify_batch(self, tasks: List[NovelTask]) -> List[NovelTask]:
        """
        여러 태스크 일괄 분류
        
        Args:
            tasks: 분류할 NovelTask 목록
            
        Returns:
            분류된 NovelTask 목록
        """
        return [self.classify(task) for task in tasks]
    
    def get_genre_scores(self, text: str) -> List[tuple]:
        """
        텍스트에 대한 모든 장르 점수 반환 (디버깅/분석용)
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            [(장르, 점수), ...] 형태의 리스트 (점수 내림차순)
        """
        self._ensure_initialized()
        
        if not self._keyword_classifier:
            return []
        
        result = self._keyword_classifier.classify_with_confidence(text)
        all_genres = result.get('all_genres', [])
        
        return [(genre, score) for genre, score, _ in all_genres]
    
    def close(self):
        """리소스 정리 및 캐시 저장"""
        # 캐시 저장
        self.cache.save()
        
        # 키워드 분류기 정리
        if self._keyword_classifier and hasattr(self._keyword_classifier, 'close'):
            self._keyword_classifier.close()
        
        self.logger.info("[GenreClassifierAdapter] 리소스 정리 완료")


# 하위 호환성을 위한 별칭
SearchFirstClassifierAdapter = GenreClassifierAdapter
