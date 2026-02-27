"""
카카오페이지 장르 추출기
"""

import re
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class KakaoExtractor(BasePlatformExtractor):
    """카카오페이지 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "카카오페이지"
    
    @property
    def confidence(self) -> float:
        return 0.90  # 신뢰도 조정 (95% → 90%)
    
    @property
    def priority(self) -> int:
        return 4  # 우선순위 상향 (5 → 4)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """카카오페이지에서 장르 추출"""
        urls = self._extract_urls(links)
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            # 제목 확인 (저자명 포함)
            if not self._verify_title(soup, title, author):
                continue
            
            # span 태그에서 장르 추출
            genre_result = self._extract_from_span(soup, url)
            if genre_result:
                # 현판 → 스포츠 재분류 필요 여부 표시
                if genre_result['genre'] == '현판':
                    genre_result['needs_sports_check'] = True
                    genre_result['needs_history_check'] = True
                # 판타지 → 역사/겜판/퓨판 세분화 필요 여부 표시
                elif genre_result['genre'] == '판타지':
                    genre_result['needs_fantasy_refinement'] = True
                return genre_result
            
            # 본문에서 장르 추출
            genre_result = self._extract_from_text_common(soup, url, confidence=0.85)
            if genre_result:
                # 현판 → 스포츠 재분류 필요 여부 표시
                if genre_result['genre'] == '현판':
                    genre_result['needs_sports_check'] = True
                    genre_result['needs_history_check'] = True
                # 판타지 → 역사/겜판/퓨판 세분화 필요 여부 표시
                elif genre_result['genre'] == '판타지':
                    genre_result['needs_fantasy_refinement'] = True
                return genre_result
        
        return None
    

    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함)"""
        page_title_tag = soup.find('title')
        if not page_title_tag:
            return False
        
        page_title_text = page_title_tag.get_text()
        
        # 카카오페이지 플랫폼 접미사 제거
        # "마왕 조동칠 - 웹소설 | 카카오페이지" → "마왕 조동칠"
        import re
        cleaned = re.sub(r'\s*-\s*(웹소설|웹툰|책)\s*\|?\s*카카오페이지.*$', '', page_title_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+\d+화\s*\|?\s*카카오페이지.*$', '', cleaned, flags=re.IGNORECASE)
        
        matched, match_info = self.match_title(title, cleaned, search_author=author, strict_short=True)
        
        if matched:
            if 'matched_author' in match_info:
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{match_info['matched_author']}')")
            else:
                print(f"  [{self.platform_name}] 제목 일치: {page_title_text[:50]}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title_text[:50]}")
            return False
    
    def _extract_from_span(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """span 태그에서 장르 추출"""
        genre_spans = soup.find_all('span', class_='break-all align-middle')
        
        for span in genre_spans:
            genre_text = span.get_text(strip=True)
            if genre_text in self.genre_mapping:
                mapped_genre = self.genre_mapping[genre_text]
                print(f"  [{self.platform_name}] 장르 태그: {genre_text} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_tag',
                    'raw_genre': genre_text,
                    'url': url
                }
        
        return None
    

