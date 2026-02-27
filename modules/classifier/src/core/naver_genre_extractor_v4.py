"""
네이버 검색을 통한 장르 추출기 V4 (리팩토링 버전)

Version: 1.4.0
Last Updated: 2025-11-02

주요 변경사항:
- 플랫폼별 추출 로직을 독립적인 클래스로 분리
- 공통 유틸리티 함수 모듈화
- 검색 전략 패턴 적용
- 설정 관리 분리
- 유지보수성 및 확장성 대폭 개선
"""

__version__ = "1.4.0"

import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import quote
from typing import Dict, List, Optional, Any

# 플랫폼 추출기
from modules.classifier.src.core.platform_extractors import (
    RidibooksExtractor,
    MunpiaExtractor,
    NovelpiaExtractor,
    NaverSeriesExtractor,
    KakaoExtractor,
    NovelnetExtractor,
    MrblueExtractor,
)
from modules.classifier.src.core.platform_extractors.simple_extractors import (
    JoaraExtractor,
    WebtoonguideExtractor,
    Yes24Extractor,
    KyoboExtractor,
    AladinExtractor,
)

# 유틸리티
from modules.classifier.src.core.utils.search_strategy import SearchStrategy


class NaverGenreExtractorV4:
    """네이버 검색 → 플랫폼 링크 → 장르 추출 (리팩토링 버전)"""
    
    # 장르 세분화 레벨 (숫자가 클수록 더 세분화됨)
    GENRE_SPECIFICITY = {
        '소설': 1,
        '판타지': 2,
        '현판': 3,
        '퓨판': 3,
        '겜판': 3,
        '무협': 3,
        '선협': 3,
        '로판': 3,
        '언정': 3,
        'SF': 3,
        '미스터리': 3,
        '밀리터리': 3,
        '패러디': 3,
        '역사': 4,  # 역사는 퓨판보다 더 구체적
        '스포츠': 4,  # 스포츠는 현판보다 더 구체적
    }
    
    def __init__(self, naver_api_config=None):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Referer': 'https://www.naver.com/',
        }
        
        # 네이버 API 설정
        self.naver_api_config = naver_api_config
        self.use_api = naver_api_config is not None and \
                       'client_id' in naver_api_config and \
                       'client_secret' in naver_api_config
        
        # 검색 결과 캐시
        self.search_cache = {}
        
        # 장르 매핑
        self.genre_mapping = self._init_genre_mapping()
        
        # 플랫폼 추출기 초기화
        self.extractors = self._init_extractors()
        
        # 재매핑 키워드
        self.remapping_keywords = self._init_remapping_keywords()
        
        # 로거 (옵션)
        self.logger = None

    def set_logger(self, logger):
        """로거 설정"""
        self.logger = logger
        
    def _log(self, msg: str):
        """로그 출력 (터미널 + 파일)"""
        if self.logger:
            self.logger.debug(msg)
        print(msg)
    
    def _init_genre_mapping(self) -> Dict[str, str]:
        """장르 매핑 초기화"""
        return {
            # 판타지 계열
            '판타지': '판타지',
            '퓨전판타지': '퓨판',
            '퓨전 판타지': '퓨판',
            '퓨전': '퓨판',
            '현대판타지': '현판',
            '현대 판타지': '현판',
            '현판': '현판',
            '게임판타지': '겜판',
            '게임 판타지': '겜판',
            '게임': '겜판',
            
            # 무협/선협
            '무협': '무협',
            '무협 소설': '무협',
            '전통 무협': '무협',
            '선협': '선협',
            
            # 로맨스 계열
            '로맨스': '로판',
            '로맨스판타지': '로판',
            '로맨스 판타지': '로판',
            '로판': '로판',
            'BL': '로판',
            '언정': '언정',
            
            # 기타
            'SF': 'SF',
            '스포츠': '스포츠',
            '스포츠물': '스포츠',
            '역사': '역사',
            '역사물': '역사',
            '대체역사': '역사',
            '대체 역사물': '역사',
            '정통판타지': '판타지',
            '정통 판타지': '판타지',
            '미스터리': '미스터리',
            '소설': '소설',
            '해외 소설': '소설',
            '라이트노벨': '판타지',
            '팬픽': '판타지',
            '팬픽션': '판타지',
            '패러디': '패러디',  # v1.3.12: 패러디 장르 독립
            '밀리터리': '밀리터리',
            '전쟁 밀리터리': '밀리터리',
            '전쟁': '밀리터리',
            '현대': '현판',
        }
    
    def _init_extractors(self) -> List[Any]:
        """플랫폼 추출기 초기화 (우선순위 순)"""
        # 우선순위: 리디북스 > 문피아 > 네이버시리즈 > 카카오페이지 > 소설넷 > 노벨피아 > 조아라 > 웹툰가이드 > 미스터블루 > 교보문고 > YES24 > 알라딘
        extractors = [
            RidibooksExtractor(self.genre_mapping, self.headers),
            MunpiaExtractor(self.genre_mapping, self.headers),
            NaverSeriesExtractor(self.genre_mapping, self.headers),
            KakaoExtractor(self.genre_mapping, self.headers),
            NovelnetExtractor(self.genre_mapping, self.headers),
            NovelpiaExtractor(self.genre_mapping, self.headers),
            JoaraExtractor(self.genre_mapping, self.headers),
            WebtoonguideExtractor(self.genre_mapping, self.headers),
            MrblueExtractor(self.genre_mapping, self.headers),
            KyoboExtractor(self.genre_mapping, self.headers),
            Yes24Extractor(self.genre_mapping, self.headers),
            AladinExtractor(self.genre_mapping, self.headers),
        ]
        
        # 우선순위로 정렬
        return sorted(extractors, key=lambda x: x.priority)
    
    def _init_remapping_keywords(self) -> Dict[str, Dict]:
        """재매핑 키워드 초기화 (엄격한 조건)"""
        return {
            '스포츠': {
                'keywords': ['축구', '야구', '농구', '배구', '테니스', '골프', '선수', '코치', '감독', '호타', '준족'],
                'exclude': ['영화', '드라마', '연극', '공연', '마왕', '용사', '마법'],
                'from_genres': ['현판', '판타지'],
                'min_keywords': 2  # 최소 2개 키워드 필요
            },
            '역사': {
                'keywords': ['조선', '고려', '삼국시대', '삼국지', '왕조', '황제', '제국', '전쟁', '임진왜란', '병자호란', '외교관', '봉건', '이성계', '인조반정'],
                'exclude': ['사이버펑크', '네오', '미래', 'SF', '우주', '마왕', '용사', '마법', '던전', '게이트'],
                'from_genres': ['판타지', '현판'],  # 현판도 역사로 재분류 가능
                'min_keywords': 2  # 최소 2개 키워드 필요
            },
            '겜판': {
                'keywords': ['게임', 'VR', '가상현실', '레벨업', '스킬', '아이템', 'NPC', '플레이어'],
                'exclude': [],
                'from_genres': ['판타지', '퓨판'],
                'min_keywords': 2  # 최소 2개 키워드 필요
            },
            '퓨판': {
                'keywords': ['회귀', '환생', '빙의', '차원', '이계', '전이', '귀환'],
                'exclude': [],
                'from_genres': ['판타지'],
                'min_keywords': 1  # 1개만 있어도 OK
            },
        }
    
    def extract_genre_from_title(self, title: str) -> Dict[str, Any]:
        """제목으로 장르 추출 (메인 진입점)"""
        # 검색 전략 생성
        strategy = SearchStrategy(title)
        strategy.log_info()
        
        # 캐시 확인
        main_title = strategy.main_title
        if main_title in self.search_cache:
            print(f"  [캐시 사용] 이전 검색 결과 재사용")
            return self.search_cache[main_title].copy()
        
        # API 사용 여부 로그
        if self.use_api:
            print(f"  [검색 방식] 네이버 검색 API 사용")
        else:
            print(f"  [검색 방식] 웹 크롤링 사용")
        
        # 검색 쿼리 목록 가져오기
        queries = strategy.get_search_queries()
        
        # 각 쿼리로 검색 시도
        for query_info in queries:
            query = query_info['query']
            description = query_info['description']
            
            print(f"  [검색 {query_info['priority']}차] {description}: {query}")
            
            result = self._search_with_query(query, main_title, strategy)
            
            if result and result.get('genre'):
                # 캐시에 저장
                self.search_cache[main_title] = result
                return result
        
        # 최종 실패
        print(f"  [최종 실패] 장르를 찾을 수 없습니다")
        print()
        
        result = {
            'genre': None,
            'confidence': 0.0,
            'source': 'none',
            'raw_genre': None,
            'url': None
        }
        
        self.search_cache[main_title] = result
        return result
    
    def _search_with_query(self, query: str, title: str, strategy) -> Optional[Dict[str, Any]]:
        """쿼리로 검색 및 장르 추출"""
        if self.use_api:
            return self._search_with_api(query, title, strategy)
        else:
            return self._search_with_web(query, title, strategy)
    
    def _search_with_api(self, query: str, title: str, strategy) -> Optional[Dict[str, Any]]:
        """네이버 검색 API 사용"""
        try:
            client_id = self.naver_api_config['client_id']
            client_secret = self.naver_api_config['client_secret']
            
            api_url = "https://openapi.naver.com/v1/search/webkr.json"
            
            headers = {
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret
            }
            
            params = {
                "query": query,
                "display": 10,
                "start": 1,
                "sort": "sim"
            }
            
            response = requests.get(api_url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"  [API 오류] 상태 코드: {response.status_code}")
                return None
            
            data = response.json()
            items = data.get('items', [])
            
            print(f"  [API 응답] {len(items)}개 결과")
            
            # API 결과가 0개인 경우 웹 크롤링으로 폴백
            if len(items) == 0:
                print(f"  [API 폴백] 결과 없음 → 웹 크롤링 시도")
                return self._search_with_web(query, title, strategy)
            
            # 플랫폼 링크 추출
            platform_links = self._extract_platform_links(items)
            
            # 플랫폼별로 장르 추출 시도
            return self._extract_from_platforms(platform_links, title, strategy)
            
        except Exception as e:
            # 인코딩 오류 방지
            error_msg = str(e)[:100].encode('utf-8', errors='ignore').decode('utf-8')
            print(f"  [API 오류] {type(e).__name__}: {error_msg}")
            return None
    
    def _search_with_web(self, query: str, title: str, strategy) -> Optional[Dict[str, Any]]:
        """웹 크롤링 사용"""
        try:
            encoded_query = quote(query)
            url = f"https://search.naver.com/search.naver?query={encoded_query}"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code != 200:
                print(f"  [HTTP 오류] 상태 코드: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            all_links = soup.find_all('a', href=True)
            
            print(f"  [전체 링크] {len(all_links)}개")
            
            # 플랫폼 링크 추출
            platform_links = self._extract_platform_links_from_soup(all_links)
            
            # 플랫폼별로 장르 추출 시도
            return self._extract_from_platforms(platform_links, title, strategy)
            
        except Exception as e:
            # 인코딩 오류 방지
            error_msg = str(e)[:100].encode('utf-8', errors='ignore').decode('utf-8')
            # 인코딩 오류 방지
            error_msg = str(e)[:100].encode('utf-8', errors='ignore').decode('utf-8')
            self._log(f"  [웹 크롤링 오류] {type(e).__name__}: {error_msg}")
            return None
            return None
    
    def _extract_platform_links(self, items: List[Dict]) -> Dict[str, List]:
        """API 응답에서 플랫폼 링크 추출"""
        platform_links = {
            'ridibooks': [],
            'munpia': [],
            'novelpia': [],
            'joara': [],
            'naver_series': [],
            'kakao': [],
            'novelnet': [],
            'webtoonguide': [],
            'mrblue': [],
            'yes24': [],
            'kyobo': [],
            'aladin': []
        }
        
        for item in items:
            link = item.get('link', '')
            
            if 'ridibooks.com/books/' in link:
                platform_links['ridibooks'].append(link)
            elif 'munpia.com/novel/' in link or 'novel.munpia.com' in link:
                platform_links['munpia'].append(link)
            elif 'novelpia.com/novel/' in link:
                platform_links['novelpia'].append(link)
            elif 'joara.com' in link and '/book/' in link:
                platform_links['joara'].append(link)
            elif 'series.naver.com' in link:
                platform_links['naver_series'].append(link)
            elif 'page.kakao.com/content/' in link:
                platform_links['kakao'].append(link)
            elif 'novelnet.co.kr' in link or 'novel.naver.com' in link or 'ssn.so' in link:
                platform_links['novelnet'].append(link)
            elif 'webtoonguide.com' in link:
                platform_links['webtoonguide'].append(link)
            elif 'mrblue.com' in link:
                platform_links['mrblue'].append(link)
            elif 'yes24.com/product/goods/' in link:
                platform_links['yes24'].append(link)
            elif 'kyobobook.co.kr' in link and '/detail/' in link:
                platform_links['kyobo'].append(link)
            elif 'aladin.co.kr' in link:
                platform_links['aladin'].append(link)
        
        return platform_links
    
    def _extract_platform_links_from_soup(self, links: List) -> Dict[str, List]:
        """BeautifulSoup 링크에서 플랫폼 링크 추출 (URL만 추출, 중복 제거)"""
        platform_links = {
            'ridibooks': [],
            'munpia': [],
            'novelpia': [],
            'joara': [],
            'naver_series': [],
            'kakao': [],
            'novelnet': [],
            'webtoonguide': [],
            'mrblue': [],
            'yes24': [],
            'kyobo': [],
            'aladin': []
        }
        
        # 중복 제거를 위한 set
        seen_urls = {
            'ridibooks': set(),
            'munpia': set(),
            'novelpia': set(),
            'joara': set(),
            'naver_series': set(),
            'kakao': set(),
            'novelnet': set(),
            'webtoonguide': set(),
            'mrblue': set(),
            'yes24': set(),
            'kyobo': set(),
            'aladin': set()
        }
        
        for link in links:
            href = link.get('href', '')
            
            # URL 정규화 (쿼리 파라미터 기준으로 중복 판단)
            # 예: https://series.naver.com/novel/detail.nhn?originalProductId=466209
            normalized_url = href.split('?')[0] if '?' in href else href
            
            # URL만 추출 (BeautifulSoup 객체가 아닌 문자열로 저장, 중복 제거)
            if 'ridibooks.com/books/' in href and normalized_url not in seen_urls['ridibooks']:
                platform_links['ridibooks'].append(href)
                seen_urls['ridibooks'].add(normalized_url)
            elif ('munpia.com/novel/' in href or 'novel.munpia.com' in href) and normalized_url not in seen_urls['munpia']:
                platform_links['munpia'].append(href)
                seen_urls['munpia'].add(normalized_url)
            elif 'novelpia.com/novel/' in href and normalized_url not in seen_urls['novelpia']:
                platform_links['novelpia'].append(href)
                seen_urls['novelpia'].add(normalized_url)
            elif 'joara.com' in href and '/book/' in href and normalized_url not in seen_urls['joara']:
                platform_links['joara'].append(href)
                seen_urls['joara'].add(normalized_url)
            elif 'series.naver.com' in href and normalized_url not in seen_urls['naver_series']:
                # 검색 페이지는 제외
                if '/search/' not in href:
                    platform_links['naver_series'].append(href)
                    seen_urls['naver_series'].add(normalized_url)
            elif 'page.kakao.com/content/' in href and normalized_url not in seen_urls['kakao']:
                platform_links['kakao'].append(href)
                seen_urls['kakao'].add(normalized_url)
            elif ('novelnet.co.kr' in href or 'novel.naver.com' in href or 'ssn.so' in href) and normalized_url not in seen_urls['novelnet']:
                platform_links['novelnet'].append(href)
                seen_urls['novelnet'].add(normalized_url)
            elif 'webtoonguide.com' in href and normalized_url not in seen_urls['webtoonguide']:
                platform_links['webtoonguide'].append(href)
                seen_urls['webtoonguide'].add(normalized_url)
            elif 'mrblue.com' in href and normalized_url not in seen_urls['mrblue']:
                platform_links['mrblue'].append(href)
                seen_urls['mrblue'].add(normalized_url)
            elif 'yes24.com/product/goods/' in href and normalized_url not in seen_urls['yes24']:
                platform_links['yes24'].append(href)
                seen_urls['yes24'].add(normalized_url)
            elif 'kyobobook.co.kr' in href and '/detail/' in href and normalized_url not in seen_urls['kyobo']:
                platform_links['kyobo'].append(href)
                seen_urls['kyobo'].add(normalized_url)
            elif 'aladin.co.kr' in href and normalized_url not in seen_urls['aladin']:
                platform_links['aladin'].append(href)
                seen_urls['aladin'].add(normalized_url)
        
        return platform_links
    
    def _extract_from_platforms(self, platform_links: Dict[str, List], title: str, strategy) -> Optional[Dict[str, Any]]:
        """플랫폼별로 장르 추출 시도 (우선순위 순)"""
        # 링크 개수 및 URL 로깅
        link_counts = []
        platform_name_map = {
            'ridibooks': '리디북스',
            'munpia': '문피아',
            'novelpia': '노벨피아',
            'joara': '조아라',
            'naver_series': '네이버시리즈',
            'kakao': '카카오페이지',
            'novelnet': '소설넷',
            'webtoonguide': '웹툰가이드',
            'mrblue': '미스터블루',
            'yes24': 'YES24',
            'kyobo': '교보문고',
            'aladin': '알라딘'
        }
        
        for platform, links in platform_links.items():
            if links:
                name = platform_name_map.get(platform, platform)
                # 실제 표시되는 개수 (최대 3개)
                display_count = min(len(links), 3)
                link_counts.append(f"{name}({display_count}개)")
        
        if link_counts:
            self._log(f"  [관련 링크] {', '.join(link_counts)}")
            
            # 각 플랫폼별 URL 상세 로깅 (인코딩 오류 방지)
            for platform, links in platform_links.items():
                if links:
                    name = platform_name_map.get(platform, platform)
                    # 실제 표시할 링크 개수 (최대 3개)
                    display_count = min(len(links), 3)
                    for idx in range(display_count):
                        link = links[idx]
                        # URL 추출 (dict 또는 문자열)
                        if isinstance(link, dict):
                            url = link.get('link', '')
                        else:
                            url = str(link)
                        
                        if url:
                            try:
                                # URL 정리 (쿼리 파라미터 제거하여 깔끔하게)
                                # 예: https://series.naver.com/novel/detail.nhn?originalProductId=466209&...
                                # → https://series.naver.com/novel/detail.nhn?originalProductId=466209
                                if '?' in url:
                                    base_url, query_string = url.split('?', 1)
                                    # 주요 파라미터만 유지
                                    import urllib.parse
                                    params = urllib.parse.parse_qs(query_string)
                                    
                                    # 플랫폼별 주요 파라미터
                                    key_params = []
                                    if 'series.naver.com' in url:
                                        if 'productNo' in params:
                                            key_params.append(f"productNo={params['productNo'][0]}")
                                        elif 'originalProductId' in params:
                                            key_params.append(f"originalProductId={params['originalProductId'][0]}")
                                    elif 'page.kakao.com' in url:
                                        # 카카오페이지는 쿼리 파라미터 없음
                                        url = base_url
                                    else:
                                        # 기타 플랫폼은 첫 번째 파라미터만 유지
                                        if params:
                                            first_key = list(params.keys())[0]
                                            key_params.append(f"{first_key}={params[first_key][0]}")
                                    
                                    if key_params:
                                        url = f"{base_url}?{'&'.join(key_params)}"
                                    else:
                                        url = base_url
                                
                                self._log(f"    [{name} {idx + 1}] {url}")
                            except UnicodeEncodeError:
                                # 인코딩 오류 시 ASCII로 변환
                                url_safe = url.encode('ascii', errors='ignore').decode('ascii')
                                self._log(f"    [{name} {idx + 1}] {url_safe}")
                            except Exception:
                                # 파싱 오류 시 원본 URL 표시
                                self._log(f"    [{name} {idx + 1}] {url}")
        else:
            self._log(f"  [관련 링크 없음]")
            return None
        
        # 리디북스와 문피아가 함께 있는지 확인
        has_ridibooks = bool(platform_links.get('ridibooks'))
        has_munpia = bool(platform_links.get('munpia'))
        
        if has_ridibooks and has_munpia:
            self._log(f"  [다중 플랫폼] 리디북스와 문피아 모두 확인하여 세분화된 장르 추론")
        
        # 각 추출기로 시도 (우선순위 순)
        fallback_result = None  # "소설" 같은 일반적인 장르를 임시 저장
        hyunpan_result = None  # 네이버시리즈/카카오페이지의 "현판" 결과 임시 저장
        fantasy_result = None  # 네이버시리즈/카카오페이지의 "판타지" 결과 임시 저장
        ridibooks_result = None  # 리디북스 결과 임시 저장
        munpia_result = None  # 문피아 결과 임시 저장
        
        for extractor in self.extractors:
            platform_key = self._get_platform_key(extractor.platform_name)
            links = platform_links.get(platform_key, [])
            
            if not links:
                continue
            
            # 저자명 전달 (예외 처리 추가)
            try:
                result = extractor.extract_genre(links, title, author=strategy.author)
            except Exception as e:
                # 개별 플랫폼 오류는 무시하고 다음 플랫폼 시도
                error_msg = str(e)[:100].encode('utf-8', errors='ignore').decode('utf-8')
                self._log(f"  [{extractor.platform_name}] 추출 오류: {type(e).__name__}: {error_msg}")
                continue
            
            if result and result.get('genre'):
                # 리디북스와 문피아가 함께 있는 경우, 두 플랫폼 결과를 모두 저장
                if has_ridibooks and has_munpia:
                    if extractor.platform_name == '리디북스':
                        ridibooks_result = result
                        self._log(f"  [리디북스] '{result['genre']}' 추출 → 문피아도 확인")
                        continue
                    elif extractor.platform_name == '문피아':
                        munpia_result = result
                        self._log(f"  [문피아] '{result['genre']}' 추출")
                        
                        # 두 플랫폼 결과를 비교하여 더 세분화된 장르 선택
                        if ridibooks_result:
                            final_result = self._compare_and_select_genre(ridibooks_result, munpia_result, title)
                            self._log(f"  [최종선택] {final_result['source']}: {final_result['genre']}")
                            print()
                            return final_result
                        else:
                            # 리디북스 결과가 없으면 문피아 결과 사용
                            self._log(f"  [최종선택] 문피아: {result['genre']}")
                            print()
                            return result
                
                # 네이버시리즈/카카오페이지에서 "현판"이고 스포츠 체크가 필요한 경우
                if result.get('needs_sports_check') and result['genre'] == '현판':
                    hyunpan_result = result
                    self._log(f"  [{extractor.platform_name}] '현판' 추출 → 다른 플랫폼에서 스포츠 여부 확인")
                    continue
                
                # 네이버시리즈/카카오페이지에서 "판타지"이고 세분화가 필요한 경우
                if result.get('needs_fantasy_refinement') and result['genre'] == '판타지':
                    fantasy_result = result
                    self._log(f"  [{extractor.platform_name}] '판타지' 추출 → 다른 플랫폼에서 세분화 확인 (역사/겜판/퓨판)")
                    continue
                
                # 현판 체크 중이고 스포츠 또는 역사를 발견한 경우 (재매핑 전에 체크)
                if hyunpan_result and result['genre'] in ['스포츠', '역사']:
                    self._log(f"  [{extractor.platform_name}] '{result['genre']}' 확인됨 → 현판 대신 {result['genre']} 선택")
                    self._log(f"  [최종선택] {extractor.platform_name}: {result['genre']}")
                    print()
                    return result
                
                # 판타지 세분화 체크 중이고 역사/겜판/퓨판/스포츠를 발견한 경우
                if fantasy_result and result['genre'] in ['역사', '겜판', '퓨판', '스포츠']:
                    print(f"  [{extractor.platform_name}] '{result['genre']}' 확인됨 → 판타지 대신 {result['genre']} 선택")
                    print(f"  [최종선택] {extractor.platform_name}: {result['genre']}")
                    print()
                    return result
                
                # [Fix] fantasy_result 대기 중인데 동일한 '판타지'가 또 나오면 스킵
                if fantasy_result and result['genre'] == '판타지':
                    self._log(f"  [{extractor.platform_name}] '판타지' 중복 → 스킵")
                    continue
                
                # [Fix] ridibooks_result(고우선순위)가 이미 세분화된 장르를 갖고 있으면
                # 낮은 우선순위 플랫폼의 덜 세분화된 결과는 스킵
                if ridibooks_result and ridibooks_result['genre'] != '소설':
                    current_specificity = self.GENRE_SPECIFICITY.get(result['genre'], 2)
                    ridi_specificity = self.GENRE_SPECIFICITY.get(ridibooks_result['genre'], 2)
                    if ridi_specificity >= current_specificity:
                        self._log(f"  [{extractor.platform_name}] '{result['genre']}' ≤ 리디북스 '{ridibooks_result['genre']}' → 스킵")
                        continue
                
                # 재매핑 적용
                remapped_genre = self._remap_genre_by_keywords(result['genre'], title)
                if remapped_genre != result['genre']:
                    print(f"  [재매핑] {result['genre']} → {remapped_genre}")
                    result['genre'] = remapped_genre
                    result['confidence'] = max(0.85, result.get('confidence', 0.95) - 0.03)
                    
                    # 재매핑 후에도 스포츠/역사 체크
                    if hyunpan_result and result['genre'] in ['스포츠', '역사']:
                        print(f"  [{extractor.platform_name}] '{result['genre']}' 확인됨 (재매핑 후) → 현판 대신 {result['genre']} 선택")
                        print(f"  [최종선택] {extractor.platform_name}: {result['genre']}")
                        print()
                        return result
                    
                    # 재매핑 후에도 판타지 세분화 체크
                    if fantasy_result and result['genre'] in ['역사', '겜판', '퓨판', '스포츠']:
                        print(f"  [{extractor.platform_name}] '{result['genre']}' 확인됨 (재매핑 후) → 판타지 대신 {result['genre']} 선택")
                        print(f"  [최종선택] {extractor.platform_name}: {result['genre']}")
                        print()
                        return result
                
                # "소설"은 너무 일반적이므로 다음 플랫폼 확인
                if result['genre'] == '소설':
                    if not fallback_result:
                        fallback_result = result
                        print(f"  [{extractor.platform_name}] 장르 '소설' 추출 → 더 구체적인 장르 찾기 위해 다음 플랫폼 확인")
                    continue
                
                print(f"  [최종선택] {extractor.platform_name}: {result['genre']}")
                print()
                return result
        
        # 리디북스만 있고 문피아가 없는 경우
        if ridibooks_result and not munpia_result:
            print(f"  [최종선택] 리디북스: {ridibooks_result['genre']}")
            print()
            return ridibooks_result
        
        # 현판만 있고 다른 플랫폼에서 스포츠를 찾지 못한 경우
        if hyunpan_result:
            print(f"  [스포츠 미확인] 다른 플랫폼에서 스포츠 없음 → 현판 사용")
            print(f"  [최종선택] 현판")
            print()
            return hyunpan_result
        
        # 판타지만 있고 다른 플랫폼에서 세분화를 찾지 못한 경우
        if fantasy_result:
            print(f"  [세분화 미확인] 다른 플랫폼에서 역사/겜판/퓨판 없음 → 판타지 사용")
            print(f"  [최종선택] 판타지")
            print()
            return fantasy_result
        
        # 모든 플랫폼 확인 후 "소설"만 있으면 그것 사용
        if fallback_result:
            print(f"  [최종선택] 다른 장르 없음, '소설' 사용")
            print()
            return fallback_result
        
        return None
    
    def _compare_and_select_genre(self, ridibooks_result: Dict, munpia_result: Dict, title: str) -> Dict:
        """리디북스와 문피아 결과를 비교하여 더 세분화된 장르 선택"""
        ridi_genre = ridibooks_result['genre']
        munpia_genre = munpia_result['genre']
        
        ridi_level = self.GENRE_SPECIFICITY.get(ridi_genre, 2)
        munpia_level = self.GENRE_SPECIFICITY.get(munpia_genre, 2)
        
        # 두 장르가 같으면 리디북스 우선 (우선순위가 높음)
        if ridi_genre == munpia_genre:
            print(f"  [장르 비교] 리디북스와 문피아 모두 '{ridi_genre}' → 리디북스 선택")
            return ridibooks_result
        
        # 더 세분화된 장르 선택
        if munpia_level > ridi_level:
            print(f"  [장르 비교] 리디북스 '{ridi_genre}' vs 문피아 '{munpia_genre}' → 문피아가 더 세분화됨")
            return munpia_result
        elif ridi_level > munpia_level:
            print(f"  [장르 비교] 리디북스 '{ridi_genre}' vs 문피아 '{munpia_genre}' → 리디북스가 더 세분화됨")
            return ridibooks_result
        else:
            # 세분화 레벨이 같으면 리디북스 우선
            print(f"  [장르 비교] 리디북스 '{ridi_genre}' vs 문피아 '{munpia_genre}' → 세분화 레벨 동일, 리디북스 선택")
            return ridibooks_result
    
    def _get_platform_key(self, platform_name: str) -> str:
        """플랫폼 이름 → 키 변환"""
        mapping = {
            '리디북스': 'ridibooks',
            '문피아': 'munpia',
            '노벨피아': 'novelpia',
            '조아라': 'joara',
            '네이버시리즈': 'naver_series',
            '카카오페이지': 'kakao',
            '소설넷': 'novelnet',
            '웹툰가이드': 'webtoonguide',
            '미스터블루': 'mrblue',
            'YES24': 'yes24',
            '교보문고': 'kyobo',
            '알라딘': 'aladin'
        }
        return mapping.get(platform_name, platform_name.lower())
    
    def _remap_genre_by_keywords(self, genre: str, title: str) -> str:
        """제목 키워드를 기반으로 장르 재매핑 (엄격한 조건)"""
        if not genre or not title:
            return genre
        
        title_lower = title.lower()
        title_no_space = title_lower.replace(' ', '')
        
        for target_genre, config in self.remapping_keywords.items():
            keywords = config['keywords']
            exclude_keywords = config['exclude']
            from_genres = config.get('from_genres', [])
            min_keywords = config.get('min_keywords', 1)  # 최소 키워드 개수
            
            # 현재 장르가 재매핑 대상이 아니면 스킵
            if from_genres and genre not in from_genres:
                continue
            
            # 제외 키워드가 있으면 스킵
            if any(exclude.lower() in title_lower for exclude in exclude_keywords):
                continue
            
            # 매칭된 키워드 개수 세기
            matched_count = 0
            for keyword in keywords:
                keyword_lower = keyword.lower()
                keyword_no_space = keyword_lower.replace(' ', '')
                
                if keyword_lower in title_lower or keyword_no_space in title_no_space:
                    matched_count += 1
            
            # 최소 키워드 개수 이상이면 재매핑
            if matched_count >= min_keywords:
                if genre != target_genre:
                    return target_genre
        
        return genre
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total = len(self.search_cache)
        success = sum(1 for v in self.search_cache.values() if v.get('genre'))
        failed = total - success
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'hit_rate': success / total if total > 0 else 0
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self.search_cache.clear()


# 테스트
if __name__ == "__main__":
    extractor = NaverGenreExtractorV4()
    
    test_titles = [
        "그 고아가 가디언이라고",
        "나만 아는 히든 엔딩",
    ]
    
    for title in test_titles:
        print("="*80)
        print(f"테스트: {title}")
        print("="*80)
        
        result = extractor.extract_genre_from_title(title)
        
        print()
        print(f"결과: {result['genre']} ({result['confidence']:.0%}, {result['source']})")
        print()
