"""
소설넷, 미스터블루 장르 추출기
"""

import re
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class NovelnetExtractor(BasePlatformExtractor):
    """소설넷 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "소설넷"
    
    @property
    def confidence(self) -> float:
        return 0.88  # 네이버시리즈와 유사한 신뢰도
    
    @property
    def priority(self) -> int:
        return 3  # 카카오페이지보다 우선 (장르 정보가 더 구체적)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """소설넷에서 장르 추출"""
        urls = self._extract_urls(links)
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            # 제목 확인 (저자명 포함)
            if not self._verify_title(soup, title, author):
                continue
            
            # 장르 추출 시도
            genre_result = self._extract_from_page(soup, url)
            if genre_result:
                return genre_result
        
        return None
    

    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함)"""
        # og:title 메타 태그 우선
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
        
        # 플랫폼 접미사 제거 (normalize_title에서 처리됨)
        matched, match_info = self.match_title(title, page_title, search_author=author, strict_short=True)
        
        if matched:
            if 'matched_author' in match_info:
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{match_info['matched_author']}')")
            else:
                print(f"  [{self.platform_name}] 제목 일치: {page_title[:50]}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title[:50]}")
            return False
    
    def _extract_from_page(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """페이지에서 장르 추출"""
        
        # 방법 1: 메타 태그에서 장르 추출
        genre_result = self._extract_from_meta(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 2: 카테고리/장르 링크에서 추출
        genre_result = self._extract_from_category(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 3: 본문에서 장르 추출
        genre_result = self._extract_from_text_common(soup, url, confidence=0.80)
        if genre_result:
            return genre_result
        
        return None
    
    def _extract_from_meta(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """메타 태그에서 장르 추출 (복수 장르 우선순위 처리)"""
        meta_tags = soup.find_all('meta')
        
        for meta in meta_tags:
            content = meta.get('content', '')
            name = meta.get('name', '')
            
            # keywords에서만 장르 찾기 (description은 일반 텍스트 포함)
            if name == 'keywords' and content:
                # 쉼표로 구분된 장르들 추출
                genre_candidates = []
                sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
                
                for genre_key in sorted_genres:
                    if genre_key in content:
                        if genre_key in self.genre_mapping:
                            mapped = self.genre_mapping[genre_key]
                            genre_candidates.append((genre_key, mapped))
                
                if genre_candidates:
                    # 복수 장르가 있을 때만 우선순위 적용
                    if len(genre_candidates) > 1:
                        # 장르 우선순위 (구체적 > 일반적)
                        priority_order = [
                            '스포츠',  # 스포츠 최우선
                            '무협', '선협',  # 무협
                            '현판', '현대판타지', '현대 판타지',  # 현판 (판타지보다 구체적) [Moved Up]
                            '겜판', '게임판타지', '게임 판타지',  # 겜판
                            '로판', '로맨스판타지', '로맨스 판타지', '로맨스',  # 로판 (현판보다 낮게 조정)
                            '퓨판', '퓨전판타지', '퓨전 판타지',  # 퓨판
                            '역사', '대체역사', '시대물',  # 역사
                            'SF',  # SF
                            '판타지'  # 판타지는 가장 낮은 우선순위
                        ]
                        
                        # 우선순위에 따라 선택
                        for priority_genre in priority_order:
                            for genre_key, mapped in genre_candidates:
                                if mapped == priority_genre or genre_key == priority_genre:
                                    all_genres = ', '.join([g for g, _ in genre_candidates])
                                    print(f"  [{self.platform_name}] 메타 장르: {all_genres} → {mapped} (우선순위 선택)")
                                    return {
                                        'genre': mapped,
                                        'confidence': self.confidence,
                                        'source': f'{self.platform_name.lower()}_meta',
                                        'raw_genre': genre_key,
                                        'url': url
                                    }
                    
                    # 단일 장르이거나 우선순위에 없으면 첫 번째 선택
                    genre_key, mapped = genre_candidates[0]
                    print(f"  [{self.platform_name}] 메타 장르: {genre_key} → {mapped}")
                    return {
                        'genre': mapped,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_meta',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        return None
    
    def _extract_from_category(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """카테고리/장르 링크에서 추출 (복수 장르 우선순위 처리)"""
        # product-category div 찾기 (소설넷 전용)
        category_div = soup.find('div', class_='product-category')
        
        if category_div:
            # 모든 링크에서 장르 추출
            genre_links = category_div.find_all('a')
            genre_candidates = []
            
            for link in genre_links:
                genre_text = link.get_text(strip=True)
                if genre_text in self.genre_mapping:
                    mapped = self.genre_mapping[genre_text]
                    genre_candidates.append((genre_text, mapped))
            
            if genre_candidates:
                # 복수 장르가 있을 때 우선순위 적용
                # 우선순위: 스포츠 > 현대판타지 > 판타지 (더 구체적인 장르 우선)
                # 무협 > 판타지, 로판 > 판타지 등
                if len(genre_candidates) > 1:
                    # 장르 우선순위 (구체적 > 일반적)
                    priority_order = [
                        '스포츠',  # 스포츠 최우선
                        '무협', '선협',  # 무협
                        '현판', '현대판타지', '현대 판타지',  # 현판 (판타지보다 구체적) [Moved Up]
                        '겜판', '게임판타지', '게임 판타지',  # 겜판
                        '로판', '로맨스판타지', '로맨스 판타지', '로맨스',  # 로판 (현판보다 낮게 조정)
                        '퓨판', '퓨전판타지', '퓨전 판타지',  # 퓨판
                        '역사', '대체역사', '시대물',  # 역사
                        'SF',  # SF
                        '판타지'  # 판타지는 가장 낮은 우선순위
                    ]
                    
                    # 우선순위에 따라 선택
                    for priority_genre in priority_order:
                        for genre_text, mapped in genre_candidates:
                            if mapped == priority_genre or genre_text == priority_genre:
                                all_genres = ', '.join([g for g, _ in genre_candidates])
                                print(f"  [{self.platform_name}] 카테고리 장르: {all_genres} → {mapped} (우선순위 선택)")
                                return {
                                    'genre': mapped,
                                    'confidence': self.confidence,
                                    'source': f'{self.platform_name.lower()}_category',
                                    'raw_genre': genre_text,
                                    'url': url
                                }
                
                # 단일 장르이거나 우선순위에 없으면 첫 번째 선택
                genre_text, mapped = genre_candidates[0]
                print(f"  [{self.platform_name}] 카테고리 장르: {genre_text} → {mapped}")
                return {
                    'genre': mapped,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_category',
                    'raw_genre': genre_text,
                    'url': url
                }
        
        # 일반적인 장르 요소 찾기 (폴백)
        genre_elements = soup.find_all(['div', 'span', 'a'], 
                                      class_=lambda x: x and ('genre' in str(x).lower() or 
                                                             'category' in str(x).lower()))
        
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for elem in genre_elements:
            elem_text = elem.get_text(strip=True)
            
            for genre_key in sorted_genres:
                if genre_key in elem_text:
                    mapped_genre = self.genre_mapping[genre_key]
                    print(f"  [{self.platform_name}] 카테고리 장르: {elem_text} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_category',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        return None
    


class MrblueExtractor(BasePlatformExtractor):
    """미스터블루 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "미스터블루"
    
    @property
    def confidence(self) -> float:
        return 0.85  # 조아라와 유사한 신뢰도
    
    @property
    def priority(self) -> int:
        return 9  # 교보문고 앞
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """미스터블루에서 장르 추출"""
        urls = self._extract_urls(links)
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            # 제목 확인 (저자명 포함)
            if not self._verify_title(soup, title, author):
                continue
            
            # 장르 추출 시도
            genre_result = self._extract_from_page(soup, url)
            if genre_result:
                return genre_result
        
        return None
    

    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함)"""
        # og:title 메타 태그 우선
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
        
        # 플랫폼 접미사 제거 (normalize_title에서 처리됨)
        matched, match_info = self.match_title(title, page_title, search_author=author, strict_short=True)
        
        if matched:
            if 'matched_author' in match_info:
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{match_info['matched_author']}')")
            else:
                print(f"  [{self.platform_name}] 제목 일치: {page_title[:50]}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title[:50]}")
            return False
    
    def _extract_from_page(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """페이지에서 장르 추출"""
        
        # 방법 1: 메타 태그에서 장르 추출
        genre_result = self._extract_from_meta(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 2: 장르 태그/배지에서 추출
        genre_result = self._extract_from_genre_tag(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 3: 카테고리에서 추출
        genre_result = self._extract_from_category(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 4: 본문에서 장르 추출
        genre_result = self._extract_from_text_common(soup, url, confidence=0.75)
        if genre_result:
            return genre_result
        
        return None
    
    def _extract_from_meta(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """메타 태그에서 장르 추출"""
        meta_tags = soup.find_all('meta')
        
        for meta in meta_tags:
            content = meta.get('content', '')
            name = meta.get('name', '')
            property_val = meta.get('property', '')
            
            # keywords, description, og:description에서 장르 찾기
            if (name in ['keywords', 'description'] or property_val == 'og:description') and content:
                sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
                
                for genre_key in sorted_genres:
                    if genre_key in content:
                        mapped_genre = self.genre_mapping[genre_key]
                        print(f"  [{self.platform_name}] 메타 장르: {genre_key} → {mapped_genre}")
                        return {
                            'genre': mapped_genre,
                            'confidence': self.confidence,
                            'source': f'{self.platform_name.lower()}_meta',
                            'raw_genre': genre_key,
                            'url': url
                        }
        
        return None
    
    def _extract_from_genre_tag(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """장르 태그/배지에서 추출"""
        # 장르 관련 클래스를 가진 요소 찾기
        genre_elements = soup.find_all(['span', 'div', 'a', 'li'], 
                                      class_=lambda x: x and ('genre' in str(x).lower() or 
                                                             'tag' in str(x).lower() or
                                                             'badge' in str(x).lower()))
        
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for elem in genre_elements:
            elem_text = elem.get_text(strip=True)
            
            # 직접 매핑
            if elem_text in self.genre_mapping:
                mapped_genre = self.genre_mapping[elem_text]
                print(f"  [{self.platform_name}] 장르 태그: {elem_text} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_tag',
                    'raw_genre': elem_text,
                    'url': url
                }
            
            # 부분 매칭
            for genre_key in sorted_genres:
                if genre_key in elem_text:
                    mapped_genre = self.genre_mapping[genre_key]
                    print(f"  [{self.platform_name}] 장르 태그: {elem_text} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_tag',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        return None
    
    def _extract_from_category(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """카테고리에서 추출"""
        # 카테고리 관련 요소 찾기
        category_elements = soup.find_all(['div', 'ul', 'nav'], 
                                         class_=lambda x: x and ('category' in str(x).lower() or 
                                                                'breadcrumb' in str(x).lower()))
        
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for elem in category_elements:
            elem_text = elem.get_text()
            
            for genre_key in sorted_genres:
                if genre_key in elem_text:
                    mapped_genre = self.genre_mapping[genre_key]
                    print(f"  [{self.platform_name}] 카테고리 장르: {genre_key} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_category',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        return None
    

