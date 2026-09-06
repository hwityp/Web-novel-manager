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

        # [Fix] 이미 유효한 장르가 설정되어 있는 경우 (예: 파일명 태그 추출 결과)
        # 검색이나 추가 추론 없이 기존 장르 유지
        if task.genre and task.genre != '미분류':
            primary_genre, existing_kws = NovelTraitExtractor.parse_existing_tag(task.genre)
            mapped_genre = self.mapping_loader.map_genre(primary_genre)
            
            if mapped_genre in GENRE_WHITELIST:
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=task.title or raw_text,
                    existing_keywords=existing_kws
                )
                # confidence가 설정되어 있지 않다면 high로 설정
                if not task.confidence or task.confidence == 'low':
                    task.confidence = 'high'
                # source가 설정되어 있지 않다면 tag로 설정
                if not task.source or task.source == '-':
                    task.source = 'tag'
                
                self.logger.debug(f"  [기존 장르 유지] {task.genre} (API 검색 건너뜀)")
                print(f"  [기존 장르 유지] {task.genre} (API 검색 건너뜀)")
                return task
            
        # [최적화] 원본 파일명에 이미 장르 태그가 있는 경우 API 검색 건너뛰기
        # 예: "[SF, 시스템] 제목..." -> [SF, 시스템] (API 절약)
        import re
        tag_match = re.search(r'^\[(.+?)\]', raw_text)
        if tag_match:
            potential_tag = tag_match.group(1).strip()
            primary_genre, existing_kws = NovelTraitExtractor.parse_existing_tag(potential_tag)
            mapped_genre = self.mapping_loader.map_genre(primary_genre)
            
            # 화이트리스트에 있는 유효한 장르인 경우만 확정
            if mapped_genre in GENRE_WHITELIST:
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=raw_text,
                    existing_keywords=existing_kws
                )
                task.confidence = 'high'
                task.source = 'tag' # 기존 태그
                task.status = 'processing'
                
                self.logger.debug(f"  [태그 감지] 원본 파일명에서 장르 확인: {task.genre}")
                print(f"  [태그 감지] {task.genre} (API 검색 건너뜀)")
                
                # 캐시에도 저장
                if not task.title: # 순수 제목 추출 전일 수 있음
                    parse_result = self.title_extractor.extract(raw_text)
                    pure_title = parse_result.title if parse_result.title else raw_text
                else:
                    pure_title = task.title
                    
                self.cache.set(pure_title, task.genre, 'high', 'tag')
                return task
        
        self.logger.debug(f"장르 분류 시작: {raw_text}")
        print(f"\n{'='*80}")
        print(f"[분류 시작] {raw_text}")
        
        # Step 1: 순수 제목 추출
        parse_result = self.title_extractor.extract(raw_text)
        pure_title = parse_result.title if parse_result.title else raw_text
        author = parse_result.author
        
        # [제목 분석] 로그 추가 (사용자 요청 반영 & 포맷팅 개선)
        import pprint
        analysis_data = {
            'main_title': pure_title,
            'subtitle': parse_result.side_story,
            'author': author,
            'full_title': raw_text
        }
        formatted_analysis = pprint.pformat(analysis_data, width=120, sort_dicts=False)
        
        self.logger.debug(f"  [순수 제목] {pure_title}")
        print(f"  [순수 제목] {pure_title}")
        
        self.logger.debug(f"  [제목 분석] 원본: '{raw_text}' →\n{formatted_analysis}")
        print(f"  [제목 분석] 원본: '{raw_text}' → {analysis_data}") # 터미널엔 한줄로 (사용자가 익숙한 형태)
        
        if author:
            self.logger.debug(f"  [저자] {author}")
            print(f"  [저자] {author}")
        
        # Step 2: 캐시 확인 (Cache-First)
        cached = self.cache.get(pure_title)
        if cached:
            task.genre = cached['genre']
            task.confidence = cached['confidence']
            task.source = self._format_source(cached.get('source', 'cache'))
            task.status = 'processing'
            self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: cache)")
            print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: cache)")
            return task
        
        # Step 3: Stage 1 - 인터넷 검색 (Search-First) - NaverGenreExtractorV4 직접 사용
        search_result = self._search_genre(pure_title, author, parse_result.original_foreign_title)
        
        if search_result and search_result.get('genre') and search_result.get('genre') != '미분류':
            genre = search_result['genre']
            
            # 장르 매핑 적용
            mapped_genre = self.mapping_loader.map_genre(genre, pure_title, raw_text)
            
            # 화이트리스트 검증
            if mapped_genre in GENRE_WHITELIST:
                web_snippet = search_result.get('snippet', '')
                web_tags = search_result.get('tags', [])
                
                # 메인 장르 + 특징 키워드 조합 (최대 3개 항목)
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=raw_text,
                    web_snippet=web_snippet,
                    web_tags=web_tags
                )
                task.confidence = 'high'  # 검색 성공 = high
                task.status = 'processing'
                
                # 캐시에 저장
                source = search_result.get('source', 'search')
                task.source = self._format_source(source)
                self.cache.set(pure_title, task.genre, 'high', source)
                
                self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: {source})")
                print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: {source})")
                return task
        
        # Step 4: Stage 3 - 키워드 폴백 (검색 실패 시에만)
        self.logger.debug(f"  [폴백] 검색 실패, 키워드 매칭 시도")
        print(f"  [폴백] 검색 실패, 키워드 매칭 시도")
        keyword_result = self._keyword_fallback(pure_title, raw_text)
        
        if keyword_result and keyword_result.get('genre') != '미분류':
            genre = keyword_result['genre']
            mapped_genre = self.mapping_loader.map_genre(genre, pure_title, raw_text)
            if mapped_genre not in GENRE_WHITELIST:
                mapped_genre = '미분류'
                
            if mapped_genre != '미분류':
                task.genre = NovelTraitExtractor.format_genre_tag(
                    primary_genre=mapped_genre,
                    title=raw_text
                )
                task.confidence = 'medium'  # 키워드 매칭 = medium
                task.source = '키워드'
                task.status = 'processing'
                
                # 캐시에 저장
                self.cache.set(pure_title, task.genre, 'medium', 'keyword')
                
                self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: keyword)")
                print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: keyword)")
                return task
        
        # Step 5: 모든 방법 실패
        task.genre = '미분류'
        task.confidence = 'low'  # 실패 = low
        task.source = '-'
        task.status = 'processing'
        
        self.logger.debug(f"  [결과] {task.genre} (confidence: {task.confidence}, source: none)")
        print(f"  [결과] {task.genre} (confidence: {task.confidence}, source: none)")
        return task
    
    def _search_genre(self, title: str, author: Optional[str] = None, original_foreign_title: str = "") -> Optional[Dict]:
        """
        Stage 1: 인터넷 검색으로 장르 추출 (NaverGenreExtractorV4 직접 사용)
        
        플랫폼 우선순위:
        리디북스 > 문피아 > 네이버시리즈 > 카카오페이지 > 소설넷 > 노벨피아 > 
        조아라 > 웹툰가이드 > 미스터블루 > 교보문고 > YES24 > 알라딘
        
        Args:
            title: 순수 제목
            author: 저자명 (선택)
            original_foreign_title: 원문 한자/가나 제목 (선택)
            
        Returns:
            {'genre': str, 'confidence': float, 'source': str} 또는 None
        """
        if not self._naver_extractor:
            self.logger.warning("NaverGenreExtractorV4가 초기화되지 않음")
            return None
        
        try:
            # 저자명이 있으면 제목에 포함
            search_title = f"{title} {author}" if author else title
            
            # NaverGenreExtractorV4로 실제 웹 검색 수행
            result = self._naver_extractor.extract_genre_from_title(search_title)
            
            # 검색 실패이고 원문 한자 제목이 있으면 원문 제목으로 재검색
            if (not result or not result.get('genre') or result.get('genre') == '미분류') and original_foreign_title:
                self.logger.debug(f"한글 제목 검색 실패, 원문 한자 제목으로 검색 시도: {original_foreign_title}")
                result = self._naver_extractor.extract_genre_from_title(f"{title} {original_foreign_title}")
                if not result or not result.get('genre') or result.get('genre') == '미분류':
                    result = self._naver_extractor.extract_genre_from_title(original_foreign_title)
            
            if result and result.get('genre'):
                genre = result['genre']
                confidence = result.get('confidence', 0.9)
                source = result.get('source', 'naver_search')
                
                # None이 아닌 유효한 장르인 경우
                if genre and genre != '미분류':
                    return {
                        'genre': genre,
                        'confidence': confidence,
                        'source': source,
                        'snippet': result.get('snippet', ''),
                        'tags': result.get('tags', [])
                    }
            
            # Naver 실패 시 Google 검색 시도 (Hybrid Sequence)
            if self._google_extractor:
                self.logger.debug(f"Naver 검색 실패, Google 검색 시도: {search_title}")
                google_result = self._google_extractor.extract_genre(search_title)
                
                if (not google_result or google_result.get('genre') == '미분류') and original_foreign_title:
                    google_result = self._google_extractor.extract_genre(original_foreign_title)
                
                if google_result:
                    return google_result
            
            return None
            
        except Exception as e:
            self.logger.warning(f"검색 중 오류: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def _keyword_fallback(self, title: str, raw_text: str = "") -> Optional[Dict]:
        """
        Stage 3: 키워드 기반 폴백 분류
        
        Args:
            title: 순수 제목
            raw_text: 원본 파일명 (선택)
            
        Returns:
            {'genre': str, 'confidence': float} 또는 None
        """
        if not self._keyword_classifier:
            return None
        
        try:
            result = self._keyword_classifier.classify_with_confidence(title)
            genre = result.get('primary_genre', '미분류')
            confidence = result.get('confidence', 0.0)
            
            # 순수 제목에서 미분류인 경우 원본 파일명으로 재시도
            if genre == '미분류' and raw_text and raw_text != title:
                raw_result = self._keyword_classifier.classify_with_confidence(raw_text)
                if raw_result.get('primary_genre') != '미분류':
                    genre = raw_result.get('primary_genre')
                    confidence = raw_result.get('confidence', 0.0)

            # 장르 매핑 적용
            mapped_genre = self.mapping_loader.map_genre(genre)
            
            # 화이트리스트 검증
            if mapped_genre not in GENRE_WHITELIST:
                mapped_genre = '미분류'
            
            return {
                'genre': mapped_genre,
                'confidence': confidence
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
            'keyword': '키워드',
            'cache': '캐시',
            'user': '사용자',
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
