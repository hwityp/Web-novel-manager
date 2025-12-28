"""
간단한 플랫폼 추출기들 (조아라, 웹툰가이드, 서점들)
"""

import re
import time
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class JoaraExtractor(BasePlatformExtractor):
    """조아라 장르 추출기 (Selenium 필요)"""
    
    @property
    def platform_name(self) -> str:
        return "조아라"
    
    @property
    def confidence(self) -> float:
        return 0.85
    
    @property
    def priority(self) -> int:
        return 7  # 우선순위 하향 (6 → 7, 노벨피아 다음)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """조아라에서 장르 추출 (Selenium 사용)"""
        print(f"  [{self.platform_name}] Selenium으로 추출 시작 (링크 {len(links)}개)")
        
        # Selenium WebDriver 생성
        driver = self._get_selenium_driver()
        if not driver:
            print(f"  [{self.platform_name}] Selenium 사용 불가, 건너뛰기")
            return None
        
        try:
            urls = [link.get('href', '') if hasattr(link, 'get') else str(link) for link in links]
            
            for idx, href in enumerate(urls[:2], 1):  # 최대 2개만
                if not href.startswith('http'):
                    href = 'https://www.joara.com' + href
                
                print(f"  [{self.platform_name}] 링크 {idx}/{min(2, len(urls))} 확인 중: {href[:60]}...")
                
                try:
                    driver.get(href)
                    
                    # 빠른 성인 인증 감지
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    # body 로딩 대기
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                    except:
                        print(f"  [{self.platform_name}] 페이지 로딩 실패")
                        continue
                    
                    # 성인 인증 페이지 감지
                    time.sleep(1)
                    html = driver.page_source
                    from bs4 import BeautifulSoup
                    page_soup = BeautifulSoup(html, 'html.parser')
                    
                    page_title = page_soup.find('title')
                    if page_title:
                        page_title_text = page_title.get_text(strip=True)
                        adult_keywords = ['로그인', '인증', '성인', '19세', '본인확인', 'adult', 'login']
                        if any(keyword in page_title_text.lower() for keyword in adult_keywords):
                            print(f"  [{self.platform_name}] 성인 인증 필요, 건너뛰기")
                            continue
                    
                    # div.items 로딩 대기
                    try:
                        WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.items"))
                        )
                        print(f"  [{self.platform_name}] div.items 로딩 완료")
                        
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.items span"))
                        )
                        print(f"  [{self.platform_name}] span 태그 로딩 완료")
                    except:
                        print(f"  [{self.platform_name}] div.items 대기 실패")
                        continue
                    
                    # 페이지 소스 다시 가져오기
                    html = driver.page_source
                    page_soup = BeautifulSoup(html, 'html.parser')
                    
                    # 제목 확인
                    if not self._verify_title_joara(page_soup, title):
                        continue
                    
                    # 장르 추출
                    items_div = page_soup.find('div', class_='items')
                    if items_div:
                        genre_spans = items_div.find_all('span')
                        print(f"  [{self.platform_name}] div.items 발견, span 태그 {len(genre_spans)}개")
                        
                        if genre_spans:
                            first_span = genre_spans[0]
                            genre_text = first_span.get_text(strip=True)
                            print(f"  [{self.platform_name}] 첫 번째 span (장르): '{genre_text}'")
                            
                            if genre_text in self.genre_mapping:
                                mapped_genre = self.genre_mapping[genre_text]
                                print(f"  [{self.platform_name}] 장르 매핑 성공: {genre_text} → {mapped_genre}")
                                return {
                                    'genre': mapped_genre,
                                    'confidence': self.confidence,
                                    'source': f'{self.platform_name.lower()}_selenium',
                                    'raw_genre': genre_text,
                                    'url': href
                                }
                            else:
                                print(f"  [{self.platform_name}] '{genre_text}'는 매핑 테이블에 없음")
                    
                except Exception as e:
                    print(f"  [{self.platform_name}] 링크 처리 오류: {str(e)[:50]}")
                    continue
            
            print(f"  [{self.platform_name}] 장르를 찾지 못함")
            return None
            
        finally:
            driver.quit()
    
    def _get_selenium_driver(self):
        """Selenium WebDriver 생성"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            import os
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--log-level=3")
            
            # ChromeDriver 경로 찾기
            driver_path = os.getenv('CHROMEDRIVER_PATH')
            if not driver_path:
                possible_paths = [
                    r"C:\Users\hwity\.wdm\drivers\chromedriver\win64\137.0.7151.119\chromedriver-win32\chromedriver.exe",
                    "chromedriver.exe",
                    "/usr/local/bin/chromedriver",
                    "/usr/bin/chromedriver"
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        driver_path = path
                        break
            
            if driver_path and os.path.exists(driver_path):
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
            
            return driver
        except Exception as e:
            print(f"  [{self.platform_name}] WebDriver 생성 실패: {str(e)[:100]}")
            return None
    
    def _verify_title_joara(self, soup, title: str) -> bool:
        """제목 확인"""
        page_title = soup.find('title')
        if not page_title:
            return False
        
        page_title_text = page_title.get_text()
        
        # base_extractor의 match_title 사용 (짧은 제목 엄격 매칭)
        matched, _ = self.match_title(title, page_title_text, strict_short=True)
        
        if matched:
            print(f"  [{self.platform_name}] 제목 일치: {page_title_text[:50]}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title_text[:50]}")
            return False


class WebtoonguideExtractor(BasePlatformExtractor):
    """웹툰가이드 장르 추출기 (Selenium 필요)"""
    
    @property
    def platform_name(self) -> str:
        return "웹툰가이드"
    
    @property
    def confidence(self) -> float:
        return 0.75  # 신뢰도 하향 (90% → 75%, 웹툰 중심 플랫폼)
    
    @property
    def priority(self) -> int:
        return 8  # 우선순위 하향 (7 → 8)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """웹툰가이드에서 장르 추출 (Selenium 사용)"""
        print(f"  [{self.platform_name}] 처리 시작 (링크 {len(links)}개)")
        
        # Selenium WebDriver 생성
        driver = self._get_selenium_driver()
        if not driver:
            print(f"  [{self.platform_name}] Selenium 사용 불가, 건너뛰기")
            return None
        
        try:
            urls = [link if isinstance(link, str) else link.get('href', '') for link in links]
            
            for idx, url in enumerate(urls[:2], 1):  # 최대 2개만
                print(f"  [{self.platform_name}] 링크 {idx}/{min(2, len(urls))} 확인 중: {url[:60]}...")
                
                try:
                    driver.get(url)
                    time.sleep(2)  # 페이지 로딩 대기
                    
                    html = driver.page_source
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 제목 확인
                    if not self._verify_title_selenium(soup, title):
                        continue
                    
                    # 장르 추출
                    genre_result = self._extract_genre_from_page(soup, url)
                    if genre_result:
                        return genre_result
                
                except Exception as e:
                    print(f"  [{self.platform_name}] 링크 처리 오류: {str(e)[:50]}")
                    continue
            
            print(f"  [{self.platform_name}] 장르 추출 실패")
            return None
            
        finally:
            driver.quit()
    
    def _get_selenium_driver(self):
        """Selenium WebDriver 생성"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            import os
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--log-level=3")
            
            # ChromeDriver 경로 찾기
            driver_path = os.getenv('CHROMEDRIVER_PATH')
            if not driver_path:
                possible_paths = [
                    r"C:\Users\hwity\.wdm\drivers\chromedriver\win64\137.0.7151.119\chromedriver-win32\chromedriver.exe",
                    "chromedriver.exe",
                    "/usr/local/bin/chromedriver",
                    "/usr/bin/chromedriver"
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        driver_path = path
                        break
            
            if driver_path and os.path.exists(driver_path):
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
            
            return driver
        except Exception as e:
            print(f"  [{self.platform_name}] WebDriver 생성 실패: {str(e)[:100]}")
            return None
    
    def _verify_title_selenium(self, soup, title: str) -> bool:
        """제목 확인"""
        page_title = soup.find('title')
        if not page_title:
            return False
        
        page_title_text = page_title.get_text()
        
        # 웹툰가이드 특수 패턴 정리
        # "[웹소설/소설] <마신 여포> 세트" → "마신 여포"
        # "[웹소설/소설] 마신 여포 [단행본]" → "마신 여포"
        cleaned_page = page_title_text
        cleaned_page = re.sub(r'\[웹소설/소설\]', '', cleaned_page)
        cleaned_page = re.sub(r'<([^>]+)>', r'\1', cleaned_page)  # <제목> → 제목
        cleaned_page = re.sub(r'\[단행본\]', '', cleaned_page)
        cleaned_page = re.sub(r'\[세트\]', '', cleaned_page)
        cleaned_page = re.sub(r'\s*세트\s*$', '', cleaned_page)
        cleaned_page = re.sub(r'\s*단행본\s*$', '', cleaned_page)
        cleaned_page = re.sub(r'\s*-\s*웹툰의 모든 것!.*$', '', cleaned_page)
        cleaned_page = cleaned_page.strip()
        
        # base_extractor의 match_title 사용 (짧은 제목 엄격 매칭)
        matched, _ = self.match_title(title, cleaned_page, strict_short=True)
        
        if matched:
            print(f"  [{self.platform_name}] 제목 일치: {page_title_text[:80]}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title_text[:80]}")
            return False
    
    def _extract_genre_from_page(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """페이지에서 장르 추출
        
        HTML 구조:
        <div class="sc-gEvEer sc-jlZhew brirUa iWCsZr">
            <b>웹소설/소설</b>
            <div class="sc-cwHptR gKqaMv">판타지/무협</div>
            <div class="sc-cwHptR gKqaMv fantasy">퓨전 판타지</div>
        </div>
        """
        # 장르 루트 찾기
        genre_root = soup.find('div', class_=lambda x: x and any(
            cls in str(x) for cls in ['sc-gEvEer', 'sc-geveer', 'sc-jlZhew', 'brirUa']
        ))
        
        if not genre_root:
            print(f"  [{self.platform_name}] 장르 루트를 찾지 못함")
            return None
        
        genres = []
        
        # b 태그 (웹소설/소설)
        b_tag = genre_root.find('b')
        if b_tag:
            genres.append(b_tag.get_text(strip=True))
        
        # sc-cwHptR 또는 gKqaMv 클래스의 div들 (장르 정보)
        sub_genres = genre_root.find_all('div', class_=lambda x: x and (
            'sc-cwhptr' in str(x).lower() or 
            'sc-cwHptR' in str(x) or 
            'gKqaMv' in str(x)
        ))
        
        for sub in sub_genres:
            genre_text = sub.get_text(strip=True)
            if genre_text and len(genre_text) < 30:
                genres.append(genre_text)
        
        print(f"  [{self.platform_name}] 추출된 장르: {genres}")
        
        if not genres:
            return None
        
        # 장르 매핑 (우선순위 순서)
        genre_priority = [
            ('로맨스 판타지', '로판'),
            ('로맨스판타지', '로판'),
            ('퓨전 판타지', '퓨판'),
            ('퓨전판타지', '퓨판'),
            ('현대 판타지', '현판'),
            ('현대판타지', '현판'),
            ('현판', '현판'),
            ('게임 판타지', '겜판'),
            ('게임판타지', '겜판'),
            ('겜판', '겜판'),
            ('무협 판타지', '무협'),
            ('무협판타지', '무협'),
            ('무협', '무협'),
            ('로맨스', '로판'),
            ('로판', '로판'),
            ('BL', '로판'),
            ('bl', '로판'),
            ('역사', '역사'),
            ('액션', '액션'),
            ('스릴러', '스릴러'),
            ('미스터리', '미스터리'),
            ('공포', '공포'),
            ('코미디', '코미디'),
            ('판타지', '판타지'),
        ]
        
        # 우선순위 기반 장르 선택
        for keyword, mapped in genre_priority:
            for genre_text in genres:
                if keyword in genre_text or keyword.lower() in genre_text.lower():
                    print(f"  [{self.platform_name}] 장르: {genre_text} → {mapped}")
                    return {
                        'genre': mapped,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_selenium',
                        'raw_genre': genre_text,
                        'url': url
                    }
        
        return None


class Yes24Extractor(BasePlatformExtractor):
    """YES24 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "YES24"
    
    @property
    def confidence(self) -> float:
        return 0.70  # 신뢰도 하향 (75% → 70%)
    
    @property
    def priority(self) -> int:
        return 10  # 우선순위 하향 (8 → 10)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """YES24에서 장르 추출 (JSON-LD 우선, 카테고리 링크 폴백)"""
        urls = [link if isinstance(link, str) else link.get('href', '') for link in links]
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            if not self._verify_title(soup, title, author):
                continue
            
            # 방법 1: JSON-LD 구조화된 데이터에서 장르 추출 (우선)
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    
                    # Book 타입이고 genre 필드가 있는 경우
                    if data.get('@type') == 'Book' and 'genre' in data:
                        genres = data['genre']
                        if isinstance(genres, list):
                            print(f"  [{self.platform_name}] JSON-LD 장르: {' > '.join(genres)}")
                            
                            # 우선순위: 구체적인 장르 키워드 먼저 매칭
                            sorted_genre_keys = sorted(self.genre_mapping.keys(), key=len, reverse=True)
                            
                            # 역순으로 확인 (더 구체적인 것부터)
                            for genre_text in reversed(genres):
                                for genre_key in sorted_genre_keys:
                                    if genre_key in genre_text:
                                        mapped_genre = self.genre_mapping[genre_key]
                                        print(f"  [{self.platform_name}] 장르 매핑: {genre_text} → {mapped_genre}")
                                        return {
                                            'genre': mapped_genre,
                                            'confidence': self.confidence,
                                            'source': f'{self.platform_name.lower()}_jsonld',
                                            'raw_genre': genre_text,
                                            'url': url
                                        }
                except Exception as e:
                    print(f"  [{self.platform_name}] JSON-LD 파싱 오류: {str(e)[:50]}")
                    continue
            
            # 방법 2: 카테고리 링크에서 장르 추출 (폴백)
            category_links = soup.find_all('a', href=lambda x: x and 'CategoryNumber' in str(x))
            
            if category_links:
                # 모든 카테고리 텍스트 수집
                category_texts = [cat_link.get_text(strip=True) for cat_link in category_links]
                category_path = ' > '.join(category_texts)
                
                print(f"  [{self.platform_name}] 카테고리 경로: {category_path}")
                
                # 우선순위: 구체적인 장르 키워드 먼저 매칭
                sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
                
                # 개별 카테고리 텍스트에서 장르 찾기 (역순으로, 더 구체적인 것부터)
                for cat_text in reversed(category_texts):
                    for genre_key in sorted_genres:
                        if genre_key in cat_text:
                            mapped_genre = self.genre_mapping[genre_key]
                            print(f"  [{self.platform_name}] 카테고리 장르: {cat_text} → {mapped_genre}")
                            return {
                                'genre': mapped_genre,
                                'confidence': self.confidence,
                                'source': f'{self.platform_name.lower()}_category',
                                'raw_genre': cat_text,
                                'url': url
                            }
            
            print(f"  [{self.platform_name}] 장르를 찾지 못함")
        
        return None
    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함) - YES24"""
        page_title = soup.find('title')
        if not page_title:
            return False
        
        page_title_text = page_title.get_text()
        print(f"  [{self.platform_name}] 페이지 제목: {page_title_text[:80]}")
        
        # YES24 플랫폼 접미사 제거
        # "마이언 전기 1 | 임달영 | 프로넷(서울창작) - 예스24" → "마이언 전기 1 | 임달영 | 프로넷(서울창작)"
        import re
        cleaned = re.sub(r'\s*-\s*예스24.*$', '', page_title_text, flags=re.IGNORECASE)
        
        # "제목 | 저자 | 출판사" 형식 파싱
        page_title_only = cleaned
        page_author = None
        if '|' in cleaned:
            parts = [p.strip() for p in cleaned.split('|')]
            if len(parts) >= 2:
                page_title_only = parts[0]  # 제목
                page_author = parts[1]  # 저자
        
        # 제목 매칭
        matched, match_info = self.match_title(title, page_title_only, search_author=None)
        if not matched:
            print(f"  [{self.platform_name}] 제목 불일치")
            return False
        
        # 짧은 제목(6자 이하)이고 저자명이 있는 경우 저자명도 확인
        normalized_title = self.normalize_title(title)
        if len(normalized_title) <= 6 and author and page_author:
            # 저자명 매칭
            author_matched, matched_variant = self.match_author(author, page_author)
            if author_matched:
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{matched_variant}')")
                return True
            else:
                print(f"  [{self.platform_name}] 제목 일치하나 저자명 불일치 (검색: '{author}', 페이지: '{page_author}')")
                return False
        
        # 긴 제목이거나 저자명 없으면 제목만으로 판정
        print(f"  [{self.platform_name}] 제목 일치")
        return True


class KyoboExtractor(BasePlatformExtractor):
    """교보문고 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "교보문고"
    
    @property
    def confidence(self) -> float:
        return 0.85  # 공식 서점 신뢰도 상향 (75% → 85%)
    
    @property
    def priority(self) -> int:
        return 9  # 우선순위 유지
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """교보문고에서 장르 추출"""
        urls = [link if isinstance(link, str) else link.get('href', '') for link in links]
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            if not self._verify_title(soup, title, author):
                continue
            
            # 카테고리 경로 추출 (개선)
            category_area = soup.find(['div', 'ul'], 
                                     class_=lambda x: x and ('category' in str(x).lower() or 'breadcrumb' in str(x).lower()))
            
            if not category_area:
                print(f"  [{self.platform_name}] 카테고리 영역을 찾지 못함")
                continue
            
            cat_text = category_area.get_text()
            
            # 카테고리 경로 파싱 (예: "HOME > 국내도서 > 소설 > 한국소설 > 판타지소설")
            # 구체적인 장르(판타지소설)를 우선 추출
            category_parts = [p.strip() for p in cat_text.split('>') if p.strip()]
            
            print(f"  [{self.platform_name}] 카테고리 장르: {' > '.join(category_parts)}")
            
            # 우선순위: 구체적 장르 키워드 (판타지소설, 무협소설 등)
            specific_genres = ['판타지소설', '무협소설', '로맨스소설', '역사소설', 'SF소설', '추리소설', '미스터리소설']
            for part in reversed(category_parts):  # 뒤에서부터 (더 구체적)
                for specific in specific_genres:
                    if specific in part:
                        # 매핑
                        if '판타지' in specific:
                            mapped_genre = '판타지'
                        elif '무협' in specific:
                            mapped_genre = '무협'
                        elif '로맨스' in specific:
                            mapped_genre = '로판'
                        elif '역사' in specific:
                            mapped_genre = '역사'
                        elif 'SF' in specific:
                            mapped_genre = 'SF'
                        elif '추리' in specific or '미스터리' in specific:
                            mapped_genre = '미스터리'
                        else:
                            continue
                        
                        print(f"  [{self.platform_name}] 구체적 장르: {part} → {mapped_genre}")
                        return {
                            'genre': mapped_genre,
                            'confidence': self.confidence,
                            'source': f'{self.platform_name.lower()}_category',
                            'raw_genre': part,
                            'url': url
                        }
            
            # 일반 장르 매핑 (폴백)
            sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
            for genre_key in sorted_genres:
                if genre_key in cat_text:
                    mapped_genre = self.genre_mapping[genre_key]
                    
                    # "한국소설일반" 같은 일반 카테고리는 낮은 신뢰도
                    if '일반' in cat_text or '기타' in cat_text:
                        confidence = 0.60  # 신뢰도 낮춤
                    else:
                        confidence = self.confidence
                    
                    print(f"  [{self.platform_name}] 일반 장르: {cat_text[:50]} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': confidence,
                        'source': f'{self.platform_name.lower()}_category',
                        'raw_genre': genre_key,
                        'url': url
                    }
            
            print(f"  [{self.platform_name}] 카테고리에서 매핑 가능한 장르를 찾지 못함")
        
        return None
    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함) - 교보문고"""
        page_title = soup.find('title')
        if not page_title:
            return False
        
        page_title_text = page_title.get_text()
        print(f"  [{self.platform_name}] 페이지 제목: {page_title_text[:80]}")
        
        # 교보문고 플랫폼 접미사 제거
        # "말괄량이프린세스 4 | 은서휘 - 교보문고" → "말괄량이프린세스 4 | 은서휘"
        import re
        cleaned = re.sub(r'\s*-\s*교보문고.*$', '', page_title_text, flags=re.IGNORECASE)
        
        # 추가 정리: "제목 | 저자" 형식에서 제목만 추출
        # "말괄량이프린세스 4 | 은서휘" → "말괄량이프린세스 4"
        if '|' in cleaned:
            parts = cleaned.split('|')
            if len(parts) >= 1:
                cleaned = parts[0].strip()
        
        # 권수 및 부가 정보 제거
        # "최강을 꿈꾸다 7(1부 완결)" → "최강을 꿈꾸다"
        cleaned = re.sub(r'\s+\d+\s*\([^)]+\)\s*$', '', cleaned)  # " 7(1부 완결)" 제거
        cleaned = re.sub(r'\s+\d+권?\s*$', '', cleaned)  # " 7권", " 7" 제거
        cleaned = re.sub(r'\s*\([^)]*(?:완결|완|부)\s*[^)]*\)\s*$', '', cleaned)  # "(1부 완결)" 제거
        
        # 특수문자 정규화 (느낌표, 물음표 등)
        cleaned = cleaned.rstrip('!?')
        
        # 저자명 포함 매칭
        matched, match_info = self.match_title(title, cleaned, search_author=author)
        if matched:
            if match_info.get('type') == 'short_with_author':
                matched_author = match_info.get('matched_author', '')
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{matched_author}')")
            else:
                print(f"  [{self.platform_name}] 제목 일치")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치")
            return False


class AladinExtractor(BasePlatformExtractor):
    """알라딘 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "알라딘"
    
    @property
    def confidence(self) -> float:
        return 0.85  # 공식 서점 신뢰도 상향 (70% → 85%)
    
    @property
    def priority(self) -> int:
        return 11  # 우선순위 유지
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """알라딘에서 장르 추출"""
        urls = [link if isinstance(link, str) else link.get('href', '') for link in links]
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            if not self._verify_title(soup, title, author):
                continue
            
            # 카테고리에서 장르 추출
            category_links = soup.find_all('a', href=lambda x: x and 'CID=' in str(x))
            
            if not category_links:
                print(f"  [{self.platform_name}] 카테고리 링크를 찾지 못함")
                continue
            
            # 모든 카테고리 텍스트 수집
            category_texts = [cat_link.get_text(strip=True) for cat_link in category_links]
            category_path = ' > '.join(category_texts)
            
            print(f"  [{self.platform_name}] 카테고리 경로: {category_path}")
            
            # 우선순위: 구체적인 장르 키워드 먼저 매칭
            sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
            
            # 개별 카테고리 텍스트에서 장르 찾기 (역순으로, 더 구체적인 것부터)
            for cat_text in reversed(category_texts):
                for genre_key in sorted_genres:
                    if genre_key in cat_text:
                        mapped_genre = self.genre_mapping[genre_key]
                        print(f"  [{self.platform_name}] 카테고리 장르: {cat_text} → {mapped_genre}")
                        return {
                            'genre': mapped_genre,
                            'confidence': self.confidence,
                            'source': f'{self.platform_name.lower()}_category',
                            'raw_genre': cat_text,
                            'url': url
                        }
            
            # 전체 경로에서 장르 찾기 (폴백)
            for genre_key in sorted_genres:
                if genre_key in category_path:
                    mapped_genre = self.genre_mapping[genre_key]
                    print(f"  [{self.platform_name}] 카테고리 경로에서 장르: {genre_key} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_category',
                        'raw_genre': genre_key,
                        'url': url
                    }
            
            print(f"  [{self.platform_name}] 카테고리에서 매핑 가능한 장르를 찾지 못함")
        
        return None
    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함) - 알라딘"""
        page_title = soup.find('title')
        if not page_title:
            return False
        
        page_title_text = page_title.get_text()
        print(f"  [{self.platform_name}] 페이지 제목: {page_title_text[:80]}")
        
        # 알라딘 플랫폼 접미사 제거
        # "마왕 1 | 김남재 - 알라딘" → "마왕 1 | 김남재"
        import re
        cleaned = re.sub(r'\s*-\s*알라딘.*$', '', page_title_text, flags=re.IGNORECASE)
        
        # 알라딘 특유의 패턴 제거
        # "제4세대 지판전기 1-5 완결 /대현문화사" → "제4세대 지판전기"
        # 패턴: 숫자-숫자, 완결, /출판사명 등
        cleaned = re.sub(r'\s+\d+-\d+\s*(완결|세트|권)?.*$', '', cleaned)  # "1-5 완결 /대현문화사" 제거
        cleaned = re.sub(r'\s*/[^|]+$', '', cleaned)  # "/출판사명" 제거
        cleaned = re.sub(r'\s+\(.*?\)$', '', cleaned)  # "(부제)" 제거
        
        # 추가 정리: "제목 | 저자" 형식에서 제목만 추출
        # "마왕 1 | 김남재" → "마왕 1"
        if '|' in cleaned:
            parts = cleaned.split('|')
            if len(parts) >= 1:
                cleaned = parts[0].strip()
        
        # 저자명 포함 매칭
        matched, match_info = self.match_title(title, cleaned, search_author=author)
        if matched:
            if match_info.get('type') == 'short_with_author':
                matched_author = match_info.get('matched_author', '')
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{matched_author}')")
            else:
                print(f"  [{self.platform_name}] 제목 일치")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치")
            return False
