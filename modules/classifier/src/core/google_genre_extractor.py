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
        '판타지': [r'판타지', r'fantasy'],
        '무협': [r'무협'],
        '현대판타지': [r'현대\s*판타지', r'현판', r'어반\s*판타지'],
        '로맨스판타지': [r'로맨스\s*판타지', r'로판'],
        '게임판타지': [r'게임\s*판타지', r'겜판'],
        '퓨전판타지': [r'퓨전\s*판타지', r'퓨판'],
        '선협': [r'선협'],
        '스포츠': [r'스포츠', r'바둑', r'야구', r'축구', r'농구', r'격투기', r'권투', r'복싱', r'골프', r'배구', r'테니스'],
        '대체역사': [r'대체\s*역사', r'역사'],
        'SF': [r'SF', r'공상과학', r'사이파이'],
        '공포': [r'공포', r'호러', r'미스터리', r'스릴러'],
        '로맨스': [r'로맨스', r'순정'],
        '라이트노벨': [r'라이트\s*노벨', r'라노벨'],
        '드라마': [r'드라마'],
        '패러디': [r'패러디', r'팬픽', r'2차\s*창작', r'fanfic']
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

    def extract_genre(self, query: str) -> Optional[Dict]:
        """
        Google 검색을 통해 장르 추출
        
        Args:
            query: 검색어 (소설 제목)
            
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
                'num': 3,  # 상위 3개 결과만 확인
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
            
            for item in items:
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                link = item.get('link', '')
                
                # [Logic Restoration] 소설넷(ssn.so) 필터링 강화
                if 'ssn.so' in link:
                    if any(x in link for x in ['/profile/', '/author/', '/notifications/', '/comments/']):
                        continue
                    if '/novel/' not in link:
                        continue
                
                # 1차: 스니펫 분석
                text = f"{title} {snippet}"
                found_genres = self._analyze_text(text)
                
                # 2차: 스크래핑 결정 및 수행
                # 스니펫에서 장르를 못 찾았거나, 찾았어도 '일반적인 장르'이고 '리뷰 사이트'인 경우 정밀 확인
                if self._should_scrape(link, found_genres): 
                    scraped_genres = self._scrape_url(link)
                    if scraped_genres:
                        found_genres.extend(scraped_genres)
                        print(f"  [Scraping Success] {link} -> {scraped_genres}")
                
                all_found_genres.extend(found_genres)
            
            if not all_found_genres:
                return None
            
            # 장르 우선순위 결정
            best_genre, score = self._resolve_genre_priority(all_found_genres)
            
            # [Fix] Google은 단일 키워드 매칭 오류 빈도 높음
            # total_score(빈도) 1이면 근거가 너무 약함 → 미분류 반환
            # '판타지'/'소설'은 일반적이므로 1회도 허용
            if score <= 1 and best_genre not in ['판타지', '소설', '드라마']:
                self.logger.info(f"Google 결과 근거 부족 (score={score}, genre={best_genre}) → 미분류")
                return None
            
            # 신뢰도 계산 (0.6 ~ 0.95)
            # 점수가 높을수록(많이 발견될수록) 신뢰도 상승
            confidence = 0.6 + (min(score, 5) * 0.07)
            
            return {
                'genre': best_genre,
                'confidence': min(confidence, 0.95),
                'source': 'Google_Scraping'
            }
            
        except Exception as e:
            self.logger.error(f"Google 검색 중 오류 발생: {e}")
            return None

    def _should_scrape(self, url: str, current_genres: List[str]) -> bool:
        """
        URL 스크래핑 여부 결정
        
        전략:
        1. 장르를 전혀 못 찾았으면 스크래핑 (기존 로직)
        2. '일반적 장르(판타지/소설)'만 찾았는데, URL이 '정보/리뷰 사이트'면 스크래핑 (정밀도 향상)
        """
        # 1. 장르 미발견 시 무조건 시도
        if not current_genres:
            return True
            
        # 2. 정보가 풍부한 사이트 목록 (디시, 나무위키, 아카라이브 등)
        rich_info_sites = ['dcinside.com', 'namu.wiki', 'arca.live', 'instiz.net', 'theqoo.net']
        is_rich_site = any(site in url for site in rich_info_sites)
        
        # 3. 발견된 장르가 너무 일반적인 경우 (더 구체적인 장르를 찾기 위해 스크래핑)
        # 예: '소설', '판타지'만 발견됨 -> 본문에서 '선협'이나 '팬픽' 찾기 시도
        generic_genres = ['소설', '판타지', '미스터리', '드라마']
        only_generic = all(g in generic_genres for g in current_genres)
        
        if is_rich_site and only_generic:
            return True
            
        return False

    def _resolve_genre_priority(self, genres: List[str]) -> Tuple[str, int]:
        """
        발견된 장르 목록에서 최적의 장르 결정
        
        우선순위:
        패러디 > 선협/무협 > 현판/겜판/로판 > 퓨판 > 스포츠/역사 > SF > 판타지 > 소설
        """
        from collections import Counter
        counts = Counter(genres)
        
        # 우선순위 정의 (높을수록 우선)
        # 구체적이고 특징적인 장르일수록 높은 점수
        priority_map = {
            '패러디': 100,      # 팬픽/패러디 최우선 (오분류 방지)
            '선협': 90,        # 선협 (무협보다 구체적)
            '무협': 85,
            '스포츠': 95,      # 스포츠 구체적 키워드(바둑/야구/축구)가 매칭되면 최우선
            '게임판타지': 75,
            '로맨스판타지': 75,
            '현대판타지': 75,
            '대체역사': 70,
            'SF': 65,
            '라이트노벨': 60,
            '공포': 60,
            '퓨전판타지': 50,
            '로맨스': 40,
            '판타지': 20,      # 가장 일반적
            '소설': 10,        # 가장 일반적
            '드라마': 10
        }
        
        best_genre = None
        max_priority = -1
        total_score = 0
        
        for genre, count in counts.items():
            # 기본 우선순위 점수 + 빈도 가산점 (빈도 * 1)
            # 즉, 많이 언급되면 약간 유리하지만, 태생적 우선순위를 뒤집기는 힘듦
            # 예: 판타지(20) 10번 언급 = 30점 vs 선협(90) 1번 언급 = 91점 -> 선협 승리
            base_priority = priority_map.get(genre, 0)
            if base_priority > max_priority:
                max_priority = base_priority
                best_genre = genre
            
            # 같은 우선순위일 경우 빈도수 고려 (구현 생략, 단순화)
            if base_priority == max_priority and counts[genre] > counts.get(best_genre, 0):
                best_genre = genre
                
            if genre == best_genre:
                total_score = count # 반환할 점수 (신뢰도 계산용)
        
        return best_genre, total_score

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
                # 본문 텍스트 추출 (Script/Style 제외)
                for script in soup(["script", "style", "header", "footer", "nav"]):
                    script.extract()
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
