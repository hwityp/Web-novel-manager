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
        '스포츠': [r'스포츠'],
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
                'num': 3,  # 상위 3개 결과만 확인 (스크래핑 부하 고려)
                'fields': 'items(title,snippet,link)'  # link 필드 추가
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            # 403/429 체크 (할당량 초과)
            if response.status_code in [403, 429]:
                self.logger.error(f"Google API Quota Error: {response.status_code}. Further requests blocked.")
                print(f"CRITICAL: GOOGLE_QUOTA_EXCEEDED ({response.status_code})") # 배치 스크립트 감지용
                self.quota_blocked = True # 차단 모드 활성화
                return {'error': 'quota_exceeded'}

            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                self.logger.info("Google 검색 결과 없음")
                return None
                
            # 검색 결과 분석
            genre_scores = {}
            
            for item in items:
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                link = item.get('link', '')
                
                # [Logic Restoration] 소설넷(ssn.so) 필터링 강화
                # 잘못된 페이지(프로필, 댓글 등)가 검색되어 제목 불일치 야기하는 문제 해결
                if 'ssn.so' in link:
                    # Blacklist: 무의미한 페이지 제외
                    if any(x in link for x in ['/profile/', '/author/', '/notifications/', '/comments/']):
                        self.logger.debug(f"Skipping NovelNet invalid page: {link}")
                        continue
                    
                    # Whitelist: 오직 소설 상세 페이지만 허용 (ex: https://ssn.so/novel/...)
                    if '/novel/' not in link:
                        self.logger.debug(f"Skipping NovelNet non-novel page: {link}")
                        continue

                
                # 1차: 스니펫 분석
                text = f"{title} {snippet}"
                found_genres = self._analyze_text(text)
                
                # 2차: 본문 스크래핑 (스니펫만으로 부족하거나 확실한 검증 필요 시)
                # 우선순위: 본문 > 스니펫
                if link and len(found_genres) == 0: 
                     # 스니펫에서 못 찾았을 때만 접속 (효율성)
                     scraped_genres = self._scrape_url(link)
                     if scraped_genres:
                         found_genres.extend(scraped_genres)
                         print(f"  [Scraping Success] {link} -> {scraped_genres}")
                
                for genre in found_genres:
                    genre_scores[genre] = genre_scores.get(genre, 0) + 1
            
            if not genre_scores:
                return None
                
            best_genre = max(genre_scores.items(), key=lambda x: x[1])[0]
            confidence = 0.6 + (min(genre_scores[best_genre], 3) * 0.1)
            
            return {
                'genre': best_genre,
                'confidence': min(confidence, 0.95), # 스크래핑 성공 시 신뢰도 상향
                'source': 'Google_Scraping'
            }
            
        except Exception as e:
            self.logger.error(f"Google 검색 중 오류 발생: {e}")
            return None

    def _scrape_url(self, url: str) -> List[str]:
        """URL 접속하여 본문 장르 키워드 추출"""
        # URL 유효성 검사 (Relative URL 방지)
        if not url or not url.startswith('http'):
            return []
            
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            resp = requests.get(url, headers=headers, timeout=3)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 본문 텍스트 추출 (Script/Style 제외)
                for script in soup(["script", "style"]):
                    script.extract()
                text = soup.get_text()
                # 텍스트 앞부분 2000자만 분석 (효율성)
                return self._analyze_text(text[:2000])
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
                    break
        return found
