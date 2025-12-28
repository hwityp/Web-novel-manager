"""
노벨피아 장르 추출기
"""

import re
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class NovelpiaExtractor(BasePlatformExtractor):
    """노벨피아 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "노벨피아"
    
    @property
    def confidence(self) -> float:
        return 0.92  # 신뢰도 상향 (90% → 92%)
    
    @property
    def priority(self) -> int:
        return 6  # 우선순위 하향 (3 → 6, 카카오페이지 다음)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """노벨피아에서 장르 추출"""
        urls = self._extract_urls(links)
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            if not self._verify_title(soup, title):
                continue
            
            # 해시태그에서 장르 추출
            genre_result = self._extract_from_hashtags(soup, url)
            if genre_result:
                return genre_result
            
            # 본문에서 장르 추출
            genre_result = self._extract_from_text(soup, url)
            if genre_result:
                return genre_result
        
        return None
    
    def _extract_urls(self, links: List[Any]) -> List[str]:
        """URL 추출"""
        urls = []
        seen = set()
        
        for link in links:
            href = link.get('href', '') if hasattr(link, 'get') else str(link)
            if href and href not in seen:
                seen.add(href)
                urls.append(href)
        
        return urls
    
    def _verify_title(self, soup, title: str) -> bool:
        """제목 확인"""
        # og:title 메타 태그
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            page_title = og_title.get('content', '').strip()
        else:
            # title 태그
            title_tag = soup.find('title')
            if title_tag:
                page_title = title_tag.get_text().strip()
            else:
                return False
        
        # "노벨피아 - 웹소설로 꿈꾸는 세상! - " 제거
        page_title = re.sub(r'^노벨피아\s*-\s*웹소설로\s*꿈꾸는\s*세상!\s*-\s*', '', page_title)
        page_title = re.sub(r'\s*-\s*노벨피아$', '', page_title)
        page_title = page_title.strip()
        
        if not page_title:
            return False
        
        # base_extractor의 match_title 사용 (짧은 제목 엄격 매칭 포함)
        matched, match_info = self.match_title(title, page_title, strict_short=True)
        
        if matched:
            print(f"  [{self.platform_name}] 제목 일치: {page_title}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title}")
            return False
    
    def _extract_from_hashtags(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """해시태그에서 장르 추출"""
        hashtag_text = ""
        
        # 해시태그 영역 찾기
        tag_elements = soup.find_all(['div', 'span', 'p'], 
                                    class_=lambda x: x and ('tag' in x.lower() or 'hash' in x.lower()))
        
        if tag_elements:
            for elem in tag_elements:
                hashtag_text += elem.get_text() + " "
        else:
            # # 기호 주변만 추출
            text_content = soup.get_text()
            hash_matches = re.finditer(r'#\w+', text_content)
            for match in hash_matches:
                start = max(0, match.start() - 50)
                end = min(len(text_content), match.end() + 50)
                hashtag_text += text_content[start:end] + " "
        
        if not hashtag_text:
            return None
        
        # 복합 장르 확인
        compound_result = self._check_compound_genres(hashtag_text, url)
        if compound_result:
            return compound_result
        
        # 해시태그 조합 확인
        combination_result = self._check_genre_combinations(hashtag_text, url)
        if combination_result:
            return combination_result
        
        # 단일 장르 확인
        single_result = self._check_single_genres(hashtag_text, url)
        if single_result:
            return single_result
        
        return None
    
    def _check_compound_genres(self, hashtag_text: str, url: str) -> Optional[Dict[str, Any]]:
        """복합 장르 확인"""
        compound_genres = [
            ('현대판타지', '현판'),
            ('현대 판타지', '현판'),
            ('로맨스판타지', '로판'),
            ('로맨스 판타지', '로판'),
            ('퓨전판타지', '퓨판'),
            ('퓨전 판타지', '퓨판'),
            ('게임판타지', '겜판'),
            ('게임 판타지', '겜판'),
        ]
        
        for compound_key, mapped_genre in compound_genres:
            if f"#{compound_key}" in hashtag_text or f"# {compound_key}" in hashtag_text:
                print(f"  [{self.platform_name}] 해시태그 장르 (복합): #{compound_key} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_hashtag',
                    'raw_genre': compound_key,
                    'url': url
                }
        
        return None
    
    def _check_genre_combinations(self, hashtag_text: str, url: str) -> Optional[Dict[str, Any]]:
        """해시태그 조합 확인"""
        combinations = [
            (['로맨스', '판타지'], '로판', '로맨스+판타지'),
            (['판타지', '퓨전'], '퓨판', '판타지+퓨전'),
            (['무협', '게임'], '겜판', '무협+게임'),
            (['현대', '판타지'], '현판', '현대+판타지'),
        ]
        
        for keywords, genre, raw_genre in combinations:
            if all(f"#{kw}" in hashtag_text or f"# {kw}" in hashtag_text for kw in keywords):
                print(f"  [{self.platform_name}] 해시태그 장르 (조합): {' + '.join([f'#{k}' for k in keywords])} → {genre}")
                return {
                    'genre': genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_hashtag_analysis',
                    'raw_genre': raw_genre,
                    'url': url
                }
        
        return None
    
    def _check_single_genres(self, hashtag_text: str, url: str) -> Optional[Dict[str, Any]]:
        """단일 장르 확인"""
        priority_genres = ['무협', '선협', '로판', '로맨스판타지', '로맨스 판타지', '로맨스',
                          '현판', '현대판타지', '현대 판타지', '현대',
                          '겜판', '게임판타지', '게임 판타지', '게임',
                          '퓨판', '퓨전판타지', '퓨전 판타지', '퓨전',
                          '스포츠', '스포츠물', '역사', '역사물', 'SF', 'BL']
        low_priority_genres = ['판타지', '소설']
        
        # 우선순위 높은 장르
        for genre_key in priority_genres:
            if genre_key in self.genre_mapping:
                if f"#{genre_key}" in hashtag_text or f"# {genre_key}" in hashtag_text:
                    mapped_genre = self.genre_mapping[genre_key]
                    print(f"  [{self.platform_name}] 해시태그 장르: #{genre_key} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_hashtag',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        # 우선순위 낮은 장르
        for genre_key in low_priority_genres:
            if genre_key in self.genre_mapping:
                if f"#{genre_key}" in hashtag_text or f"# {genre_key}" in hashtag_text:
                    mapped_genre = self.genre_mapping[genre_key]
                    print(f"  [{self.platform_name}] 해시태그 장르: #{genre_key} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_hashtag',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        return None
    
    def _extract_from_text(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """본문에서 장르 추출"""
        text_content = soup.get_text()
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for genre_key in sorted_genres:
            if genre_key in text_content:
                mapped_genre = self.genre_mapping[genre_key]
                print(f"  [{self.platform_name}] 본문 장르: {genre_key} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': 0.80,
                    'source': f'{self.platform_name.lower()}_page',
                    'raw_genre': genre_key,
                    'url': url
                }
        
        return None
