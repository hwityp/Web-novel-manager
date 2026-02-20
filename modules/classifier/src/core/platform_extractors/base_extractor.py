"""
플랫폼 추출기 기본 클래스
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import time
import requests
from bs4 import BeautifulSoup
from modules.classifier.src.core.utils.fuzzy_match import is_similar_title, calculate_similarity


class BasePlatformExtractor(ABC):
    """플랫폼별 장르 추출기 기본 클래스"""
    
    def __init__(self, genre_mapping: Dict[str, str], headers: Dict[str, str]):
        """
        Args:
            genre_mapping: 플랫폼 장르 → 내부 장르 매핑
            headers: HTTP 요청 헤더
        """
        self.genre_mapping = genre_mapping
        self.headers = headers
        self.last_request_time = 0
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """플랫폼 이름"""
        pass
    
    @property
    @abstractmethod
    def confidence(self) -> float:
        """신뢰도 (0.0 ~ 1.0)"""
        pass
    
    @property
    def priority(self) -> int:
        """우선순위 (낮을수록 우선, 기본값: 100)"""
        return 100
    
    def rate_limit(self, min_interval: float = 0.5):
        """요청 간격 제한"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def fetch_page(self, url: str, timeout: int = 10) -> Optional[BeautifulSoup]:
        """페이지 가져오기"""
        try:
            self.rate_limit()
            response = requests.get(url, headers=self.headers, timeout=timeout)
            
            if response.status_code == 200:
                return BeautifulSoup(response.text, 'html.parser')
            else:
                print(f"  [{self.platform_name}] HTTP {response.status_code}: {url[:60]}")
                return None
        except Exception as e:
            print(f"  [{self.platform_name}] 네트워크 오류: {str(e)[:50]}")
            return None
    
    @abstractmethod
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        장르 추출 (각 플랫폼에서 구현)
        
        Args:
            links: 플랫폼 링크 리스트
            title: 검색 제목
            author: 저자명 (선택)
        
        Returns:
            {
                'genre': str,
                'confidence': float,
                'source': str,
                'raw_genre': str,
                'url': str
            } or None
        """
        pass
    
    def is_title_match(self, search_title: str, platform_title: str, threshold: float = 0.85) -> bool:
        """제목 매칭 여부 확인 (유사도 기반)
        
        Args:
            search_title: 검색 제목
            platform_title: 플랫폼 제목
            threshold: 유사도 임계값 (기본값: 0.85)
            
        Returns:
            매칭 여부
        """
        # 조사 차이만 있는 경우 매칭 (v1.3.12) - 정규화 전에 확인
        # 예: "신세계의 사령술사" vs "신세계 사령술사 - 판타지 웹소설 - 리디"
        if self._is_josa_only_difference(search_title, platform_title):
            return True
        
        # 정규화된 제목으로 비교
        norm_search = self.normalize_title(search_title)
        norm_platform = self.normalize_title(platform_title)
        
        # 정확 매칭
        if norm_search == norm_platform:
            return True
        
        # 유사도 매칭 (v1.3.9)
        return is_similar_title(search_title, platform_title, threshold)
    
    def _is_josa_only_difference(self, title1: str, title2: str) -> bool:
        """두 제목이 조사 1개만 다른지 확인
        
        Args:
            title1: 첫 번째 제목
            title2: 두 번째 제목
            
        Returns:
            조사 1개만 다른 경우 True
        """
        import re
        
        # 조사 목록 (긴 것부터 확인)
        josa_list = ['으로', '에서', '에게', '한테', '부터', '까지', '은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '로', '도', '만']
        
        # 플랫폼 정보 제거 (간단한 전처리)
        def clean_platform_info(text):
            # "- 판타지 웹소설 - 리디" 같은 접미사 제거
            text = re.sub(r'\s*[-:]\s*(판타지|로맨스|무협|BL|GL).*$', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*[-:]\s*(웹소설|e북|전자책|소설).*$', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*[-:]\s*(리디|조아라|문피아|노벨피아|카카오페이지|네이버).*$', '', text, flags=re.IGNORECASE)
            return text.strip()
        
        # 플랫폼 정보 제거
        t1_clean = clean_platform_info(title1)
        t2_clean = clean_platform_info(title2)
        
        # 공백 제거하고 비교
        t1_no_space = t1_clean.replace(' ', '')
        t2_no_space = t2_clean.replace(' ', '')
        
        # 길이 차이가 조사 1개 범위 내인지 확인 (1~2글자)
        len_diff = abs(len(t1_no_space) - len(t2_no_space))
        if len_diff == 0:
            # 길이가 같으면 조사 차이가 아님 (띄어쓰기만 다른 경우)
            return t1_no_space == t2_no_space
        
        if len_diff > 2:
            return False
        
        # 더 긴 제목과 짧은 제목 구분
        if len(t1_no_space) > len(t2_no_space):
            longer = t1_no_space
            shorter = t2_no_space
        else:
            longer = t2_no_space
            shorter = t1_no_space
        
        # 차이나는 부분 추출
        # 예: "신세계의사령술사" vs "신세계사령술사" → 차이: "의"
        for josa in josa_list:
            # 조사를 제거한 버전과 비교
            longer_without_josa = longer.replace(josa, '', 1)  # 첫 번째 발견만 제거
            
            if longer_without_josa == shorter:
                # 조사 위치 확인 (단어 경계에 있는지)
                josa_pos = longer.find(josa)
                if josa_pos > 0:  # 제목 시작이 아닌 경우
                    # 조사 앞뒤가 한글인지 확인
                    before_char = longer[josa_pos - 1] if josa_pos > 0 else ''
                    after_char = longer[josa_pos + len(josa)] if josa_pos + len(josa) < len(longer) else ''
                    
                    # 조사 앞은 한글이어야 하고, 뒤는 한글이거나 끝이어야 함
                    if before_char and '가' <= before_char <= '힣':
                        if not after_char or '가' <= after_char <= '힣':
                            return True
        
        return False
    
    def normalize_title(self, text: str) -> str:
        """제목 정규화 (공통 로직)
        
        플랫폼별 제목 형식 차이를 통일하여 매칭 정확도 향상
        """
        import re
        
        # 전각/반각 문자 통일
        text = text.replace('？', '?').replace('！', '!').replace('～', '~')
        text = text.replace('（', '(').replace('）', ')').replace('【', '[').replace('】', ']')
        text = text.replace('ː', ':').replace('˙', '.').replace('‧', '·')
        text = text.replace('：', ':').replace('；', ';')
        
        # 검색 키워드 "소설" 제거 (검색 시 추가된 것)
        text = re.sub(r'^소설\s+', '', text, flags=re.IGNORECASE)
        
        # 작가명 제거
        text = re.sub(r'\s+[-/|]\s+[가-힣]{2,5}(?:,[가-힣]{2,5})*\s*$', '', text)
        
        # 권수 표시 제거 (서점용) - 제목 끝에서만 제거
        # 띄어쓰기 있는 경우: "마왕 1", "마왕 2권", "마왕 제1권", "마왕 (상)", "마왕 [1]"
        text = re.sub(r'\s+제?\d+권\s*$', '', text)
        text = re.sub(r'\s+\d+\s*$', '', text)
        text = re.sub(r'\s+[상중하]\s*$', '', text)
        text = re.sub(r'\s+\(?\s*[상중하]\s*\)?\s*$', '', text)
        text = re.sub(r'\s+\[?\s*\d+\s*\]?\s*$', '', text)
        text = re.sub(r'\s+\(?\s*\d+\s*\)?\s*$', '', text)
        text = re.sub(r'\s+[상중하]/[상중하]\s*$', '', text)
        
        # 띄어쓰기 없는 경우: "말괄량이프린세스4", "말괄량이프린세스11", "매직스쿨캘라드리안11"
        # 한글 뒤에 바로 숫자가 오는 경우만 제거
        text = re.sub(r'([가-힣])제?\d+권$', r'\1', text)
        text = re.sub(r'([가-힣])\d+$', r'\1', text)
        text = re.sub(r'([가-힣])[상중하]$', r'\1', text)
        text = re.sub(r'([가-힣])\(?\s*[상중하]\s*\)?$', r'\1', text)
        text = re.sub(r'([가-힣])\[?\s*\d+\s*\]?$', r'\1', text)
        text = re.sub(r'([가-힣])\(?\s*\d+\s*\)?$', r'\1', text)
        
        # 플랫폼 접미사 제거 (조아라, 네이버 시리즈 등)
        # "마법교육기관 유그드라실 unlimited - 조아라 : 스토리 본능을 깨우다" → "마법교육기관 유그드라실 unlimited"
        text = re.sub(r'\s*[-:]\s*조아라\s*[:：].*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-:]\s*네이버\s*시리즈.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-:]\s*네이버.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-:]\s*문피아.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-:]\s*노벨피아.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-:]\s*카카오페이지.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-:]\s*리디북스.*$', '', text, flags=re.IGNORECASE)
        
        # 부가 정보 제거 (접두사 + 접미사 모두 처리)
        # 접두사: [개정판], [완결], [19금] 등
        text = re.sub(r'^\s*\[(단행본|완결|연재중|개정판|합본|개정|특별판|19N|19n|19금|15금)\]\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\((단행본|완결|연재중|개정판|합본|개정|특별판|19N|19n|19금|15금)\)\s*', '', text, flags=re.IGNORECASE)
        
        # 접미사: 제목 끝의 부가 정보
        text = re.sub(r'\s*\[(단행본|완결|연재중|개정판|합본|개정|특별판|19N|19n|19금|15금)\]\s*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\((완결|연재중|개정판|합본|개정|특별판|완|19금|19|15금|15|19N|19n)\)\s*$', '', text, flags=re.IGNORECASE)
        
        # 중간에 있는 부가 정보
        text = re.sub(r'\s*[\(\[]?\s*(외전|증보판|개정판|합본|특별판|완전판|무삭제판|리마스터판)\s*[\)\]]?\s*', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*[-]\s*(BL|bl|GL|gl)\s*(소설|웹소설|e북|전자책)?\s*', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*(BL|bl|GL|gl)\s*(소설|웹소설|e북|전자책)\s*', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*(e북|웹소설|전자책)\s*', ' ', text, flags=re.IGNORECASE)
        
        # 대괄호 내용 제거 (조아라: "[월야환담] 마월야" → "마월야")
        # 단, 제목의 일부인 경우는 제외 (예: "Re:제로부터 시작하는 이세계 생활")
        text = re.sub(r'^\s*\[[^\]]+\]\s*', '', text)  # 접두사만
        
        # 괄호 안의 한자/영문 제거 (조아라: "용마(龍馬) 성주록(城主錄)" → "용마 성주록")
        # 소괄호 (), 대괄호 [], 중괄호 {}, 특수괄호 【】 모두 제거
        text = re.sub(r'[(\[{【]([^)\]}】]+)[)\]}】]', '', text)
        
        # 접미사 괄호 제거 (위에서 처리 안 된 경우)
        text = re.sub(r'\s*\([^\)]+\)\s*$', '', text)
        
        # 버전 표기 정규화 (Ver3.0, Ver 3.0, v3.0 등)
        # "인류의 적, 히어로 Ver 3.0" → "인류의 적, 히어로 Ver3.0"
        text = re.sub(r'(Ver|ver|V|v)\s+(\d+(?:\.\d+)?)', r'\1\2', text, flags=re.IGNORECASE)
        
        # 부가 정보 영문 단어 제거 (조아라: "마법교육기관 유그드라실 unlimited" → "마법교육기관 유그드라실")
        # 한글 뒤에 오는 영문 단어 제거 (띄어쓰기 있는 경우, 특수문자 제거 전에 처리)
        # 단, Ver/Version 같은 버전 표기는 제외
        text = re.sub(r'([가-힣])\s+(?!Ver|ver|V|v\d)[a-zA-Z]+(?:\s+[a-zA-Z]+)*(?:\s|[-:;,.]|$)', r'\1 ', text)
        
        # 특수문자 제거 및 띄어쓰기 제거
        text = re.sub(r'[^\w\s가-힣]', '', text)
        text = ''.join(text.split())
        
        return text.lower()
    
    def parse_authors(self, authors_string: str) -> List[str]:
        """
        저자명 파싱 (콤마로 구분)
        
        Args:
            authors_string: "저자1, 저자2" 형식
        
        Returns:
            저자명 리스트
        """
        if not authors_string:
            return []
        
        # 콤마로 분리
        authors = [a.strip() for a in authors_string.split(',') if a.strip()]
        return authors
    
    def generate_author_variants(self, author: str) -> List[str]:
        """
        저자명 변형 생성 (별명 처리)
        
        Args:
            author: 저자명 (예: "요도김남재", "요도 김남재")
        
        Returns:
            변형 리스트 (우선순위 순)
        """
        # 공백 제거
        author_clean = author.replace(' ', '')
        
        variants = []
        length = len(author_clean)
        
        # 1순위: 원본 (정확 매칭)
        variants.append(author_clean)
        
        # 2순위: 끝 3글자 (본명 추정)
        if length >= 4:
            variants.append(author_clean[-3:])
        
        # 3순위: 끝 2글자 (보조)
        if length >= 4:
            last_2 = author_clean[-2:]
            # 너무 일반적인 단어는 제외
            if last_2 not in ['작가', '선생', '님', '씨']:
                variants.append(last_2)
        elif length == 3:
            # 3글자인 경우 끝 2글자만
            variants.append(author_clean[-2:])
        
        # length <= 2: 원본만 사용 (정확 매칭만)
        
        return variants
    
    def match_author(self, search_author: str, page_text: str) -> tuple[bool, str]:
        """
        저자명 매칭 (부분 매칭 지원)
        
        Args:
            search_author: 검색 저자명 ("저자1, 저자2" 형식 가능)
            page_text: 페이지 텍스트
        
        Returns:
            (matched, matched_variant)
        """
        if not search_author:
            return False, ""
        
        # 저자 파싱
        authors = self.parse_authors(search_author)
        
        # 각 저자에 대해 매칭 시도
        for author in authors:
            variants = self.generate_author_variants(author)
            
            for variant in variants:
                if variant in page_text:
                    return True, variant
        
        return False, ""
    
    def match_title(self, search_title: str, page_title: str, 
                   search_author: Optional[str] = None,
                   strict_short: bool = True) -> tuple[bool, Dict[str, Any]]:
        """
        제목 매칭 (저자명 포함, 유사도 검증 강화)
        
        Args:
            search_title: 검색 제목
            page_title: 페이지 제목
            search_author: 검색 저자명 (선택, "저자1, 저자2" 형식 가능)
            strict_short: 짧은 제목(6자 이하)에 엄격한 매칭 적용
        
        Returns:
            (matched, match_info)
        """
        # 조사 차이만 있는 경우 매칭 (v1.3.12) - 정규화 전에 확인
        # 예: "신세계의 사령술사" vs "신세계 사령술사 - 판타지 웹소설 - 리디"
        if self._is_josa_only_difference(search_title, page_title):
            return True, {'type': 'josa_diff', 'len_diff_ratio': 0.0}
        
        normalized_search = self.normalize_title(search_title)
        normalized_page = self.normalize_title(page_title)
        
        # 정확히 일치 (최우선)
        if normalized_search == normalized_page:
            return True, {'type': 'exact', 'len_diff_ratio': 0.0}
        
        # 짧은 제목(6자 이하)은 정확 일치만 허용 (v1.3.12 개선)
        # 포함 관계 불허: "대제국" vs "대제국조선" → 불일치
        # 조사 차이는 이미 위에서 처리됨
        if strict_short and len(normalized_search) <= 6:
            # 저자명이 있는 경우만 예외 허용
            if search_author:
                # 제목이 페이지에 포함되어 있고 저자명도 일치하는 경우
                if normalized_search in normalized_page:
                    # 저자명 매칭 (부분 매칭 지원)
                    author_matched, matched_variant = self.match_author(search_author, normalized_page)
                    if author_matched:
                        return True, {
                            'type': 'short_with_author', 
                            'len_diff_ratio': 0.0,
                            'matched_author': matched_variant
                        }
            
            # 저자명 없이 짧은 제목은 정확 일치만 허용 (조사 차이는 이미 처리됨)
            return False, {}
        
        # 긴 제목: 포함 관계 확인
        if normalized_search in normalized_page or normalized_page in normalized_search:
            len_diff = abs(len(normalized_search) - len(normalized_page))
            len_diff_ratio = len_diff / max(len(normalized_search), len(normalized_page), 1)
            
            # 길이 차이가 30% 이상이면 불일치 (오판 방지)
            # 예: "마왕은 싫어"(5자) vs "사냥꾼은마왕이되기싫다"(11자) → NG (차이 54%)
            if len_diff_ratio > 0.3:
                return False, {}
            
            return True, {'type': 'contains', 'len_diff_ratio': len_diff_ratio}
        
        # 저자명이 있는 경우: 제목 부분 매칭 + 저자명 확인 (긴 제목만)
        if search_author and len(normalized_search) > 6:
            # 검색 제목의 핵심 키워드가 페이지에 포함되어 있는지 확인
            # 예: "아르카디아 대륙" in "아르카디아 대륙기행"
            if len(normalized_search) >= 2 and normalized_search in normalized_page:
                author_matched, matched_variant = self.match_author(search_author, normalized_page)
                if author_matched:
                    len_diff = abs(len(normalized_search) - len(normalized_page))
                    len_diff_ratio = len_diff / max(len(normalized_search), len(normalized_page), 1)
                    
                    # 길이 차이가 50% 이하인 경우만 허용
                    if len_diff_ratio <= 0.5:
                        return True, {
                            'type': 'partial_with_author',
                            'len_diff_ratio': len_diff_ratio,
                            'matched_author': matched_variant
                        }
        
        return False, {}

    def _extract_urls(self, links: List[Any]) -> List[str]:
        """URL 공통 추출 로직"""
        urls = []
        seen = set()
        
        for link in links:
            href = link.get('href', '') if hasattr(link, 'get') else str(link)
            if href and href not in seen:
                seen.add(href)
                urls.append(href)
        
        return urls

    def _extract_from_text_common(self, soup, url: str, confidence: float = 0.80) -> Optional[Dict[str, Any]]:
        """본문에서 장르 공통 추출 로직"""
        text_content = soup.get_text()
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for genre_key in sorted_genres:
            if genre_key in text_content:
                mapped_genre = self.genre_mapping[genre_key]
                print(f"  [{self.platform_name}] 본문 장르: {genre_key} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': confidence,
                    'source': f'{self.platform_name.lower()}_page',
                    'raw_genre': genre_key,
                    'url': url
                }
        
        return None
