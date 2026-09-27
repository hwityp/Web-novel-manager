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
        '판타지': [r'판타지', r'fantasy', r'#판타지', r'음락가', r'희랍', r'해도왕권', r'크툴루'],
        '무협': [r'무협', r'武侠', r'wuxia', r'#무협', r'국술', r'대종사', r'용상반약공', r'극도무성', r'고룡', r'강호', r'무림'],
        '현대판타지': [r'현대\s*판타지', r'현판', r'어반\s*판타지', r'#현판', r'화오', r'항도', r'호림원', r'호림', r'초가전', r'영원구', r'최면', r'방대', r'회당', r'학신', r'재벌', r'연예계'],
        '로맨스판타지': [r'로맨스\s*판타지', r'로판', r'#로판'],
        '게임판타지': [r'게임\s*판타지', r'겜판', r'#겜판', r'해상구생'],
        '퓨전판타지': [r'퓨전\s*판타지', r'퓨판', r'#퓨판'],
        '선협': [r'선협', r'수선', r'수진', r'선도', r'도과', r'공법', r'선종', r'종문', r'화장장', r'선협물', r'仙侠', r'修真', r'修仙', r'xianxia', r'아시선', r'희신'],
        '언정': [r'언정', r'言情', r'고대\s*언정', r'현대\s*언정', r'궁투', r'택투', r'소복녀', r'복보', r'여주물', r'중국\s*로맨스', r'중생후', r'쾌천', r'표고양', r'금욕불자', r'초시통고금', r'허니만장광망호', r'여배'],
        '스포츠': [r'스포츠', r'바둑', r'야구', r'축구', r'농구', r'격투기', r'권투', r'복싱', r'골프', r'배구', r'테니스', r'피겨', r'구호반', r'스트라이커', r'발롱도르', r'골키퍼', r'미드필더', r'공격수', r'득점왕', r'투수', r'홈런'],
        '대체역사': [r'대체\s*역사', r'대체역사물', r'출룡', r'(?<!문서\s)(?<!수정\s)역사\s*소설', r'#역사', r'#대체역사'],
        '밀리터리': [r'밀리터리', r'전쟁', r'군사', r'첩보', r'스파이', r'포병', r'기갑', r'포화호선', r'포화', r'명령여징복', r'첩영'],
        'SF': [r'SF', r'공상과학', r'사이파이', r'사이버펑크', r'영능자', r'창화', r'초능력'],
        '공포': [r'공포', r'호러', r'미스터리', r'스릴러'],
        '로맨스': [r'로맨스', r'순정'],
        '라이트노벨': [r'라이트\s*노벨', r'라노벨'],
        '드라마': [r'드라마'],
        '패러디': [r'패러디', r'팬픽', r'2차\s*창작', r'fanfic', r'신비의\s*제왕', r'동인', r'하멜른', r'ハーメルン', r'二次創作', r'포켓몬', r'괴렵', r'권유', r'해리포터', r'코난', r'타입문', r'페이트', r'커쉐', r'항종']
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
            self.logger.warning("Google API Key 또는 CSE ID가 설정되지 않았습니다. Google API 대신 Web Search Fallback을 사용합니다.")
        
        # 쿼터 차단 플래그 (Circuit Breaker)
        self.quota_blocked = False

    def extract_genre(self, query: str, country: str = "UNKNOWN") -> Optional[Dict]:
        """
        Google 검색(또는 웹 검색 폴백)을 통해 장르 추출
        
        Args:
            query: 검색어 (소설 제목)
            country: 소설 국적 (KR / CN / JP / UNKNOWN)
            
        Returns:
            {'genre': str, 'confidence': float, 'source': str} 또는 None
        """
        # API 키 부재 또는 쿼터 초과 시 웹 검색 폴백 바로 실행
        if not self.api_key or not self.cse_id or self.quota_blocked:
            return self._search_via_web(query, country=country)
            
        try:
            self.logger.info(f"Google API 검색 시도: {query}")
            
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
            
            # 403/429 체크 (할당량 초과 시 Circuit Breaker 작동 및 웹 검색 폴백)
            if response.status_code in [403, 429]:
                self.logger.warning(f"Google API Quota Error: {response.status_code} → 웹 검색 폴백으로 전환")
                self.quota_blocked = True
                return self._search_via_web(query, country=country)

            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                self.logger.info("Google API 검색 결과 없음 → 웹 검색 폴백")
                return self._search_via_web(query, country=country)
                
            return self._process_search_items(items, query=query, country=country, source_prefix="Google")
            
        except Exception as e:
            self.logger.error(f"Google API 검색 오류: {e} → 웹 검색 폴백")
            return self._search_via_web(query, country=country)

    def _search_via_web(self, query: str, country: str = "UNKNOWN") -> Optional[Dict]:
        """Google API 쿼터 소진 시 Bing 및 모바일 네이버 웹 검색 스크래핑 폴백"""
        try:
            from bs4 import BeautifulSoup
            import urllib.parse

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
            }

            clean_q = re.sub(r'[\(\[\{].*?[\)\]\}]', '', query).strip()
            clean_q = re.sub(r'\s*\d+[-~]\d+.*$', '', clean_q).strip()

            items = []
            # 1. Bing 검색 시도
            try:
                b_url = f"https://www.bing.com/search?q={urllib.parse.quote(clean_q + ' 소설')}"
                resp = requests.get(b_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    resp.encoding = 'utf-8'
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for li in soup.find_all('li', class_='b_algo')[:10]:
                        h2 = li.find('h2')
                        a = h2.find('a') if h2 else None
                        snippet_el = li.find('div', class_='b_caption')
                        t = a.get_text().strip() if a else ''
                        href = a.get('href', '') if a else ''
                        s = snippet_el.get_text().strip() if snippet_el else ''
                        if t or s:
                            items.append({'title': t, 'snippet': s, 'link': href})
            except Exception as be:
                self.logger.debug(f"Bing search error: {be}")

            # 2. 모바일 네이버 검색 시도
            try:
                m_headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                m_url = f"https://m.search.naver.com/search.naver?query={urllib.parse.quote(clean_q + ' 소설')}"
                m_resp = requests.get(m_url, headers=m_headers, timeout=5)
                if m_resp.status_code == 200:
                    m_soup = BeautifulSoup(m_resp.text, 'html.parser')
                    for cont in m_soup.find_all(['li', 'div', 'section'])[:15]:
                        txt = cont.get_text(separator=' ', strip=True)
                        if txt and 20 < len(txt) <= 600:
                            a_tag = cont.find('a', href=True)
                            href = a_tag['href'] if a_tag else ''
                            items.append({'title': txt[:80], 'snippet': txt, 'link': href})
            except Exception as ne:
                self.logger.debug(f"Mobile Naver search error: {ne}")

            if not items:
                return None

            return self._process_search_items(items, query=clean_q, country=country, source_prefix="WebSearch")

        except Exception as e:
            self.logger.error(f"Web search fallback error: {e}")
            return None

    def _process_search_items(self, items: List[Dict], query: str, country: str = "UNKNOWN", source_prefix: str = "Google") -> Optional[Dict]:
        """검색 결과 아이템 목록에서 플랫폼 직접 크롤링 및 텍스트/스니펫 분석"""
        all_found_genres = []
        official_genres = []
        
        for item in items:
            title = item.get('title', '')
            snippet = item.get('snippet', '')
            link = item.get('link', '')
            found_genres = []
            
            # [소설넷 필터링]
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
            fp_items = list(foreign_platforms.items())
            if country in ('CN', 'JP'):
                fp_items.sort(key=lambda it: 0 if it[1][3] == country else 1)

            for dom, (pname, mod_path, cls_name, p_country) in fp_items:
                if dom in link:
                    try:
                        import importlib
                        mod = importlib.import_module(mod_path)
                        extractor_cls = getattr(mod, cls_name)
                        extractor = extractor_cls({}, {})
                        f_res = extractor.extract_genre([link], query)
                        if f_res and f_res.get('genre'):
                            print(f"  [{source_prefix} Foreign Direct] {pname}: {f_res['genre']}")
                            return {
                                'genre': f_res['genre'],
                                'confidence': f_res.get('confidence', 0.92),
                                'source': f_res.get('source', f"{source_prefix}_{pname}"),
                                'snippet': snippet
                            }
                    except Exception as fe:
                        self.logger.debug(f"Foreign extractor direct error: {fe}")

            # [국내 웹소설 주요 플랫폼 스니펫/링크 정밀 분석]
            if 'series.naver.com' in link:
                for h_tag, g_name in [('#현판', '현대판타지'), ('#판타지', '판타지'), ('#무협', '무협'), ('#정통무협', '무협'), ('#로판', '로맨스판타지'), ('#퓨판', '퓨전판타지'), ('#대체역사', '대체역사'), ('#스포츠', '스포츠')]:
                    if h_tag in snippet or h_tag in title:
                        found_genres.extend([g_name, g_name, g_name])
                        official_genres.append(g_name)

            if 'munpia.com' in link:
                for m_tag, g_name in [('현대판타지', '현대판타지'), ('판타지', '판타지'), ('무협', '무협'), ('로맨스판타지', '로맨스판타지'), ('퓨전판타지', '퓨전판타지'), ('대체역사', '대체역사'), ('스포츠', '스포츠')]:
                    if re.search(rf'(?:완결|연재)\.\s*{m_tag}', snippet) or f'. {m_tag}.' in snippet or f'. {m_tag} ' in snippet:
                        found_genres.extend([g_name, g_name, g_name])
                        official_genres.append(g_name)

            if 'ridibooks.com' in link:
                for r_tag, g_name in [('퓨전 판타지', '퓨전판타지'), ('현대 판타지', '현대판타지'), ('무협 소설', '무협'), ('로맨스판타지', '로맨스판타지'), ('판타지 웹소설', '판타지'), ('판타지 e북', '판타지')]:
                    if r_tag in title or r_tag in snippet:
                        found_genres.extend([g_name, g_name, g_name])
                        official_genres.append(g_name)

            # 1차: 일반 스니펫 분석
            text = f"{title} {snippet}"
            found_genres.extend(self._analyze_text(text))
            
            # 2차: 스크래핑 결정 및 수행 (공식 플랫폼 발견 시 스크래핑 생략)
            if not official_genres and self._should_scrape(link, found_genres, query=query, item_title=title): 
                scraped_genres = self._scrape_url(link)
                if scraped_genres:
                    found_genres.extend(scraped_genres)
            
            all_found_genres.extend(found_genres)
        
        combined_snippets = " ".join([f"{item.get('title', '')} {item.get('snippet', '')}" for item in items])
        
        if official_genres:
            best_genre, score = self._resolve_genre_priority(official_genres, country=country)
            if best_genre:
                return {
                    'genre': best_genre,
                    'confidence': 0.95,
                    'source': f'{source_prefix}_Official',
                    'snippet': combined_snippets
                }

        if not all_found_genres:
            return None
        
        best_genre, score = self._resolve_genre_priority(all_found_genres, country=country)
        if not best_genre:
            return None
        
        confidence = 0.75 + (min(score, 5) * 0.04)
        
        return {
            'genre': best_genre,
            'confidence': min(confidence, 0.95),
            'source': f'{source_prefix}_Scraping',
            'snippet': combined_snippets
        }

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
            '밀리터리': 72,
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
