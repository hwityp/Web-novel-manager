"""
Google Custom Search Engine (CSE) 기반 장르 추출기

네이버 검색 실패 시 Fallback으로 사용되는 Google 검색 모듈입니다.
Google Custom Search JSON API를 사용하여 웹 검색 결과를 가져오고,
제목과 스니펫에서 장르 정보를 추출합니다.
"""
import re
import requests
import logging
from typing import Dict, Optional, List, Tuple

class GoogleGenreExtractor:
    """
    Google Custom Search JSON API를 이용한 장르 추출기
    
    Attributes:
        api_key (str): Google API Key
        cse_id (str): Google Custom Search Engine ID
    """
    
    # 텍스트에서 장르를 추출하기 위한 키워드 패턴
    GENRE_PATTERNS = {
        '판타지': [r'판타지', r'fantasy', r'#판타지'],
        '무협': [r'무협', r'武侠', r'wuxia', r'#무협'],
        '현대판타지': [r'현대\s*판타지', r'현판', r'어반\s*판타지', r'#현판'],
        '로맨스판타지': [r'로맨스\s*판타지', r'로판', r'#로판'],
        '게임판타지': [r'게임\s*판타지', r'겜판', r'#겜판'],
        '퓨전판타지': [r'퓨전\s*판타지', r'퓨판', r'#퓨판'],
        '선협': [r'선협', r'수선', r'수진', r'선도', r'仙侠', r'修真', r'修仙', r'xianxia'],
        '언정': [r'언정', r'言情', r'고대\s*언정', r'현대\s*언정', r'궁투', r'택투', r'소복녀', r'복보', r'여주물', r'중국\s*로맨스', r'중생후'],
        '스포츠': [r'스포츠', r'바둑', r'야구', r'축구', r'농구', r'격투기', r'권투', r'복싱', r'골프', r'배구', r'테니스', r'스트라이커', r'발롱도르', r'골키퍼', r'미드필더', r'공격수', r'득점왕', r'투수', r'홈런'],
        '대체역사': [r'대체\s*역사', r'대체역사물', r'(?<!문서\s)(?<!수정\s)역사\s*소설', r'#역사', r'#대체역사'],
        'SF': [r'SF', r'공상과학', r'사이파이'],
        '공포': [r'공포', r'호러', r'미스터리', r'스릴러'],
        '로맨스': [r'로맨스', r'순정'],
        '라이트노벨': [r'라이트\s*노벨', r'라노벨'],
        '드라마': [r'드라마'],
        '패러디': [r'패러디', r'팬픽', r'2차\s*창작', r'fanfic', r'신비의\s*제왕', r'동인']
    }

    def __init__(self, api_key: str, cse_id: str):
        """
        초기화
        
        Args:
            api_key: Google Cloud Console에서 발급받은 API Key
            cse_id: Programmable Search Engine ID
        """
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.cse_id = cse_id
        
        # API 설정 확인
        if not self.api_key or not self.cse_id:
            self.logger.warning("Google API Key 또는 CSE ID가 설정되지 않았습니다. Google 검색이 비활성화됩니다.")
        
        # 쿼터 차단 플래그 (Circuit Breaker)
        self.quota_blocked = False

    def extract_genre(self, query: str, country: str = "UNKNOWN") -> Optional[Dict]:
        """
        Google 검색을 통해 장르 추출
        
        Args:
            query: 검색어 (소설 제목)
            country: 소설 국적 (KR / CN / JP / UNKNOWN)
            
        Returns:
            {'genre': str, 'confidence': float, 'source': str} 또는 None
        """
        if not self.api_key or not self.cse_id:
            return None
            
        # Circuit Breaker: 할당량 초과 시 API 호출 차단
        if self.quota_blocked:
            return None
            
        try:
            self.logger.info(f"Google 검색 시도: {query}")
            
            # Google Custom Search API 호출
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.api_key,
                'cx': self.cse_id,
                'q': query,
                'num': 10,  # 상위 10개 결과 확인 (공식 플랫폼 누락 방지)
                'fields': 'items(title,snippet,link)'
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            # 403/429 체크 (할당량 초과)
            if response.status_code in [403, 429]:
                self.logger.error(f"Google API Quota Error: {response.status_code}. Further requests blocked.")
                print(f"CRITICAL: GOOGLE_QUOTA_EXCEEDED ({response.status_code})")
                self.quota_blocked = True
                return {'error': 'quota_exceeded'}

            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                self.logger.info("Google 검색 결과 없음")
                return None
                
            # 검색 결과 분석
            all_found_genres = []
            official_genres = []
            
            for item in items:
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                link = item.get('link', '')
                found_genres = []
                
                # [Logic Restoration] 소설넷(ssn.so) 필터링 강화
                if 'ssn.so' in link:
                    if any(x in link for x in ['/profile/', '/author/', '/notifications/', '/comments/']):
                        self.logger.debug(f"Skipping NovelNet invalid page (profile/author/etc): {link}")
                        continue
                    if '/novel/' not in link:
                        self.logger.debug(f"Skipping NovelNet non-novel page: {link}")
                        continue

                # [백과사전/어학사전 등 소설과 무관한 도메인 필터링]
                excluded_domains = ['encykorea.aks.ac.kr', 'terms.naver.com', 'ko.wikipedia.org', 'dict.naver.com', 'dict.daum.net', 'theguru.co.kr']
                if any(ed in link for ed in excluded_domains):
                    self.logger.debug(f"Skipping encyclopedia/news domain: {link}")
                    continue
                
                # [해외 웹소설 플랫폼 링크 직접 확인]
                foreign_platforms = {
                    'qidian.com': ('치뎬', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'QidianExtractor', 'CN'),
                    'jjwxc.net': ('진장문학성', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'JJWXCExtractor', 'CN'),
                    'jjwxc.com': ('진장문학성', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'JJWXCExtractor', 'CN'),
                    'baike.baidu.com': ('바이두백과', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'BaiduBaikeExtractor', 'CN'),
                    'syosetu.com': ('소설가가되자', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'SyosetuExtractor', 'JP'),
                    'syosetu.org': ('하멜른', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'SyosetuExtractor', 'JP'),
                    'kakuyomu.jp': ('카쿠요무', 'modules.classifier.src.core.platform_extractors.foreign_extractors', 'KakuyomuExtractor', 'JP'),
                }
                # 국가 일치 플랫폼 우선 검사
                fp_items = list(foreign_platforms.items())
                if country in ('CN', 'JP'):
                    fp_items.sort(key=lambda item: 0 if item[1][3] == country else 1)

                for dom, (pname, mod_path, cls_name, p_country) in fp_items:
                    if dom in link:
                        try:
                            import importlib
                            mod = importlib.import_module(mod_path)
                            extractor_cls = getattr(mod, cls_name)
                            extractor = extractor_cls({}, {})
                            f_res = extractor.extract_genre([link], query)
                            if f_res and f_res.get('genre'):
                                print(f"  [Google Foreign Direct] {pname}: {f_res['genre']}")
                                return {
                                    'genre': f_res['genre'],
                                    'confidence': f_res.get('confidence', 0.92),
                                    'source': f_res.get('source', f"Google_{pname}"),
                                    'snippet': snippet
                                }
                        except Exception as fe:
                            self.logger.debug(f"Foreign extractor direct error: {fe}")

                # [국내 웹소설 주요 플랫폼 스니펫/링크 정밀 분석]
                # 1. 네이버 시리즈 해시태그 (#현판, #판타지, #무협, #로판, #퓨판 등)
                if 'series.naver.com' in link:
                    for h_tag, g_name in [('#현판', '현대판타지'), ('#판타지', '판타지'), ('#무협', '무협'), ('#정통무협', '무협'), ('#로판', '로맨스판타지'), ('#퓨판', '퓨전판타지'), ('#대체역사', '대체역사'), ('#스포츠', '스포츠')]:
                        if h_tag in snippet or h_tag in title:
                            found_genres.extend([g_name, g_name, g_name])
                            official_genres.append(g_name)
                            self.logger.debug(f"  [Google Series Tag] {h_tag} -> {g_name}")

                # 2. 문피아 카테고리 (예: '총 201화. 완결. 현대판타지.', '총 263화. 완결. 판타지.')
                if 'munpia.com' in link:
                    for m_tag, g_name in [('현대판타지', '현대판타지'), ('판타지', '판타지'), ('무협', '무협'), ('로맨스판타지', '로맨스판타지'), ('퓨전판타지', '퓨전판타지'), ('대체역사', '대체역사'), ('스포츠', '스포츠')]:
                        if re.search(rf'(?:완결|연재)\.\s*{m_tag}', snippet) or f'. {m_tag}.' in snippet or f'. {m_tag} ' in snippet:
                            found_genres.extend([g_name, g_name, g_name])
                            official_genres.append(g_name)
                            self.logger.debug(f"  [Google Munpia Tag] {m_tag} -> {g_name}")

                # 3. 리디북스 (예: '판타지 웹소설', '판타지 e북', '현대 판타지', '퓨전 판타지', '무협 소설', '로맨스판타지')
                if 'ridibooks.com' in link:
                    for r_tag, g_name in [('퓨전 판타지', '퓨전판타지'), ('현대 판타지', '현대판타지'), ('무협 소설', '무협'), ('로맨스판타지', '로맨스판타지'), ('판타지 웹소설', '판타지'), ('판타지 e북', '판타지')]:
                        if r_tag in title or r_tag in snippet:
                            found_genres.extend([g_name, g_name, g_name])
                            official_genres.append(g_name)
                            self.logger.debug(f"  [Google Ridi Tag] {r_tag} -> {g_name}")

                # 4. 소설넷 (예: '무협 웹소설 리뷰', '판타지 웹소설 리뷰', '현대판타지 웹소설 리뷰')
                if 'ssn.so' in link:
                    for s_tag, g_name in [('무협 웹소설', '무협'), ('퓨전판타지 웹소설', '퓨전판타지'), ('현대판타지 웹소설', '현대판타지'), ('판타지 웹소설', '판타지'), ('로맨스판타지 웹소설', '로맨스판타지')]:
                        if s_tag in title or s_tag in snippet:
                            found_genres.extend([g_name, g_name, g_name])
                            self.logger.debug(f"  [Google NovelNet Tag] {s_tag} -> {g_name}")

                # 5. 카카오페이지 (예: '웹소설 메타데이터 구분점 판타지', '웹소설 메타데이터 구분점 현대판타지')
                if 'page.kakao.com' in link:
                    for k_tag, g_name in [('판타지', '판타지'), ('현대판타지', '현대판타지'), ('무협', '무협'), ('로맨스판타지', '로맨스판타지'), ('퓨전판타지', '퓨전판타지')]:
                        if f'구분점 {k_tag}' in snippet or f'메타데이터 {k_tag}' in snippet or f'- {k_tag}' in title:
                            found_genres.extend([g_name, g_name, g_name])
                            official_genres.append(g_name)
                            self.logger.debug(f"  [Google Kakao Tag] {k_tag} -> {g_name}")

                # 1차: 일반 스니펫 분석
                text = f"{title} {snippet}"
                found_genres.extend(self._analyze_text(text))
                
                # 2차: 스크래핑 결정 및 수행 (공식 플랫폼 발견 시 스크래핑 생략)
                if not official_genres and self._should_scrape(link, found_genres, query=query, item_title=title): 
                    scraped_genres = self._scrape_url(link)
                    if scraped_genres:
                        found_genres.extend(scraped_genres)
                        print(f"  [Scraping Success] {link} -> {scraped_genres}")
                
                all_found_genres.extend(found_genres)
            
            combined_snippets = " ".join([f"{item.get('title', '')} {item.get('snippet', '')}" for item in items])
            
            # 공식 플랫폼 태그가 직접 감지된 경우 공식 플랫폼 우선
            if official_genres:
                best_genre, score = self._resolve_genre_priority(official_genres, country=country)
                if best_genre:
                    return {
                        'genre': best_genre,
                        'confidence': 0.95,
                        'source': 'Google_Official',
                        'snippet': combined_snippets
                    }

            if not all_found_genres:
                return None
            
            # 장르 우선순위 결정
            best_genre, score = self._resolve_genre_priority(all_found_genres, country=country)
            if not best_genre:
                return None
            
            # 신뢰도 계산 (0.75 ~ 0.95)
            confidence = 0.75 + (min(score, 5) * 0.04)
            
            return {
                'genre': best_genre,
                'confidence': min(confidence, 0.95),
                'source': 'Google_Scraping',
                'snippet': combined_snippets
            }
            
        except Exception as e:
            self.logger.error(f"Google 검색 오류: {e}")
            return None

    def _should_scrape(self, url: str, current_genres: List[str], query: str = "", item_title: str = "") -> bool:
        """
        URL 스크래핑 여부 결정
        
        전략:
        1. 백과사전/어학사전/개인블로그는 스크래핑 제외 (노이즈 방지)
        2. 작품 제목 키워드가 검색 결과 제목에 전혀 없으면 스크래핑 제외
        3. 공인 플랫폼 및 위키/커뮤니티 정보성 페이지만 스크래핑
        """
        # 백과사전/어학사전/위키백과/뉴스 등은 스크래핑 제외
        excluded_domains = ['encykorea.aks.ac.kr', 'terms.naver.com', 'ko.wikipedia.org', 'dict.naver.com', 'theguru.co.kr']
        if any(ed in url for ed in excluded_domains):
            return False

        # 개인 블로그는 목록 추천 글 등으로 인해 노이즈가 극심하므로 스크래핑 제외
        if any(b_dom in url for b_dom in ['blog.naver.com', 'tistory.com', 'post.naver.com']):
            return False

        # 검색 쿼리와 검색 결과 제목의 연관성 검사
        if query and item_title:
            query_words = [w for w in re.split(r'\s+', query) if len(w) >= 2]
            if query_words and not any(w in item_title for w in query_words):
                return False

        # 허용된 커뮤니티, 위키, 플랫폼만 스크래핑 허용
        allowed_scrape_domains = [
            'series.naver.com', 'page.kakao.com',
            'dcinside.com', 'namu.wiki', 'arca.live', 'instiz.net', 'theqoo.net',
            'ridibooks.com', 'munpia.com', 'novelpia.com', 'joara.com', 'ssn.so', 'mrblue.com',
            'qidian.com', 'jjwxc.net', 'syosetu.com', 'kakuyomu.jp'
        ]
        if not any(dom in url for dom in allowed_scrape_domains):
            return False

        # 1. 장르 미발견 시 시도
        if not current_genres:
            return True
            
        # 2. 정보가 풍부한 사이트 목록 (디시, 나무위키, 아카라이브 등)
        rich_info_sites = ['dcinside.com', 'namu.wiki', 'arca.live', 'instiz.net', 'theqoo.net']
        is_rich_site = any(site in url for site in rich_info_sites)
        
        # 3. 발견된 장르가 너무 일반적인 경우 (더 구체적인 장르를 찾기 위해 스크래핑)
        generic_genres = ['소설', '판타지', '미스터리', '드라마']
        only_generic = all(g in generic_genres for g in current_genres)
        
        if is_rich_site and only_generic:
            return True
            
        return False

    def _resolve_genre_priority(self, genres: List[str], country: str = "UNKNOWN") -> Tuple[str, int]:
        """
        발견된 장르 목록에서 최적의 장르 결정
        
        우선순위:
        패러디 > 스포츠 > (CN일 때 선협/언정) > 무협/현판/겜판/로판/퓨판 > 역사/SF > 판타지 > 소설
        """
        if not genres:
            return "", 0

        from collections import Counter
        counts = Counter(genres)
        
        # 우선순위 정의 (높을수록 우선)
        # 한국 소설의 경우 선협/언정이 현판/판타지/무협/퓨판을 오탐하지 않도록 국적 고려
        priority_map = {
            '패러디': 100,      # 팬픽/패러디 최우선 (오분류 방지)
            '스포츠': 95,       # 스포츠 고유 어휘 매칭 시 최우선
            '선협': 90 if country == 'CN' else 60,
            '언정': 88 if country == 'CN' else 50,
            '무협': 85,
            '현대판타지': 82,
            '게임판타지': 80,
            '로맨스판타지': 80,
            '퓨전판타지': 78,
            '대체역사': 70,
            'SF': 65,
            '라이트노벨': 60,
            '공포': 50,
            '로맨스': 40,
            '판타지': 35,
            '소설': 10,
            '드라마': 10
        }
        
        best_genre = ""
        max_score = -1
        total_count = 0
        
        for genre, count in counts.items():
            base_priority = priority_map.get(genre, 0)
            score = base_priority + (count * 5)
            if score > max_score:
                max_score = score
                best_genre = genre
                total_count = count
            elif score == max_score and count > counts.get(best_genre, 0):
                best_genre = genre
                total_count = count
        
        return best_genre, total_count

    def _scrape_url(self, url: str) -> List[str]:
        """URL 접속하여 본문 장르 키워드 추출"""
        # URL 유효성 검사 (Relative URL 방지)
        if not url or not url.startswith('http'):
            return []
            
        try:
            # 헤더에 일반 브라우저 User-Agent 추가 (디시 등 차단 방지)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            resp = requests.get(url, headers=headers, timeout=5) # 타임아웃 약간 증가
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 본문 텍스트 추출 (Script/Style/Navigation/Sidebar 카테고리 제외)
                for unwanted in soup(["script", "style", "header", "footer", "nav", "aside", "ul", "ol"]):
                    unwanted.extract()
                text = soup.get_text()
                
                # 텍스트 전처리 (연속 공백 제거)
                text = ' '.join(text.split())
                
                # 텍스트 앞부분 3000자만 분석 (본문 앞부분에 중요 정보 집중됨)
                return self._analyze_text(text[:3000])
        except Exception:
            pass
        return []

    def _analyze_text(self, text: str) -> List[str]:
        """텍스트에서 장르 키워드 매칭"""
        found = []
        for genre, patterns in self.GENRE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    found.append(genre)
                    # 한 텍스트에서 같은 장르 중복 방지? 아니오, 빈도수가 중요하므로 중복 허용해야 함?
                    # 현재 호출부는 analyze_text 결과를 list로 받음
                    # 하지만 여기서 break하면 패턴 하나만 찾아도 그 장르 1회 인정
                    break 
        return found
