"""
리디북스 장르 추출기
"""

import re
import json
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class RidibooksExtractor(BasePlatformExtractor):
    """리디북스 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "리디북스"
    
    @property
    def confidence(self) -> float:
        return 0.95  # 재매핑 오류 고려하여 98% → 95%로 조정
    
    @property
    def priority(self) -> int:
        return 1  # 최우선
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """리디북스에서 장르 추출 (모든 링크 확인 후 우선순위 선택)"""
        print(f"  [{self.platform_name}] 추출 시작 (링크 {len(links)}개)")
        
        # URL 추출 및 중복 제거
        urls = self._extract_urls(links)
        
        # 모든 링크에서 장르 추출
        genre_candidates = []
        
        for idx, url in enumerate(urls[:3], 1):
            print(f"  [{self.platform_name}] 링크 {idx}/{min(3, len(urls))} 확인 중...")
            
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            # 제목 확인 (저자명 포함)
            if not self._verify_title(soup, title, author):
                continue
            
            # 장르 추출 시도
            genre_result = self._extract_genre_from_page(soup, url)
            if genre_result:
                genre_candidates.append(genre_result)
        
        # 장르 후보가 없으면 None 반환
        if not genre_candidates:
            return None
        
        # 단일 장르면 바로 반환
        if len(genre_candidates) == 1:
            return genre_candidates[0]
        
        # 복수 장르가 있으면 우선순위에 따라 선택
        return self._select_best_genre(genre_candidates)
    

    
    def _select_best_genre(self, genre_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """복수 장르 중 우선순위에 따라 최적 장르 선택
        
        Args:
            genre_candidates: 장르 후보 리스트
            
        Returns:
            선택된 장르 결과
        """
        # 장르 우선순위
        # 역사/스포츠 > 무협/선협/로판 > 겜판 > 현판 > 퓨판 > 판타지
        priority_order = [
            '역사',      # 1순위: 역사 (판타지물보다 우선)
            '스포츠',    # 2순위: 스포츠 (판타지물보다 우선)
            '무협',      # 3순위: 무협
            '선협',      # 4순위: 선협
            '로판',      # 5순위: 로판
            '겜판',      # 6순위: 겜판 (판타지물 중 최우선)
            '현판',      # 7순위: 현판
            '퓨판',      # 8순위: 퓨판
            'SF',        # 9순위: SF
            '판타지',    # 10순위: 판타지 (가장 일반적)
            '미분류'     # 최하위
        ]
        
        # 우선순위에 따라 선택
        for priority_genre in priority_order:
            for candidate in genre_candidates:
                if candidate['genre'] == priority_genre:
                    # 복수 장르 정보 출력
                    all_genres = ', '.join([c['genre'] for c in genre_candidates])
                    print(f"  [{self.platform_name}] 복수 장르 발견: {all_genres} → {priority_genre} 선택 (우선순위)")
                    return candidate
        
        # 우선순위에 없으면 첫 번째 반환
        print(f"  [{self.platform_name}] 우선순위 없음, 첫 번째 선택: {genre_candidates[0]['genre']}")
        return genre_candidates[0]
    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함, 짧은 제목은 저자명 우선 확인)"""
        page_title = soup.find('title')
        if not page_title:
            return False
        
        page_title_text = page_title.get_text()
        
        # 리디북스 플랫폼 접미사 제거
        # "마왕 조동칠 - 판타지 웹소설 - 리디" → "마왕 조동칠"
        # "후회의 산미 - 로판 웹소설 - 리디" → "후회의 산미"
        import re
        cleaned = re.sub(r'\s*-\s*(판타지|로맨스|로판|무협|BL|현대판타지|퓨전판타지|게임판타지|정통판타지|선협|역사|SF|스포츠|겜판|퓨판|현판)?\s*(웹소설|e북|전자책|소설)?\s*-?\s*리디.*$', '', page_title_text, flags=re.IGNORECASE)
        
        # 짧은 제목 판단 (5글자 이하)
        is_short_title = len(title.replace(' ', '')) <= 5
        
        # 짧은 제목이고 저자명이 있는 경우, 저자명 우선 확인
        if is_short_title and author:
            matched, match_info = self.match_title(title, cleaned, search_author=author, strict_short=True)
            
            if matched:
                # 저자명이 일치하면 확실히 같은 작품
                if match_info.get('type') == 'short_with_author' and 'matched_author' in match_info:
                    print(f"  [{self.platform_name}] 제목 일치 (저자명 확인: '{match_info['matched_author']}')")
                    return True
                # 저자명이 페이지에 없지만 제목은 일치하는 경우 (리디북스에 저자명이 없을 수 있음)
                elif match_info.get('type') in ['exact', 'normalized', 'short_strict']:
                    print(f"  [{self.platform_name}] 제목 일치 (짧은 제목, 저자명 미확인): {page_title_text[:50]}")
                    return True
                else:
                    # 제목도 불일치
                    print(f"  [{self.platform_name}] 제목 불일치: {page_title_text[:50]}")
                    return False
            else:
                print(f"  [{self.platform_name}] 제목 불일치: {page_title_text[:50]}")
                return False
        else:
            # 긴 제목이거나 저자명이 없는 경우, 기존 로직 사용
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
    
    def _extract_genre_from_page(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """페이지에서 장르 추출"""
        
        # 방법 1: JSON-LD 스키마
        genre_result = self._extract_from_jsonld(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 2: Breadcrumb
        genre_result = self._extract_from_breadcrumb(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 3: 메타 태그
        genre_result = self._extract_from_meta(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 4: 장르 링크
        genre_result = self._extract_from_links(soup, url)
        if genre_result:
            return genre_result
        
        # 방법 5: 본문
        genre_result = self._extract_from_text(soup, url)
        if genre_result:
            return genre_result
        
        return None
    
    def _extract_from_jsonld(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """JSON-LD에서 장르 추출"""
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                if 'genre' in data:
                    genre_text = data['genre']
                    mapped_genre = self._map_genre(genre_text)
                    
                    if mapped_genre:
                        print(f"  [{self.platform_name}] JSON-LD 장르: {genre_text} → {mapped_genre}")
                        return {
                            'genre': mapped_genre,
                            'confidence': self.confidence,
                            'source': f'{self.platform_name.lower()}_jsonld',
                            'raw_genre': genre_text,
                            'url': url
                        }
            except:
                pass
        
        return None
    
    def _extract_from_breadcrumb(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """Breadcrumb에서 장르 추출"""
        breadcrumbs = soup.find_all(['nav', 'ol', 'ul', 'div'], 
                                    class_=lambda x: x and ('breadcrumb' in str(x).lower() or 'category' in str(x).lower()))
        
        for bc in breadcrumbs:
            links = bc.find_all('a')
            if links:
                last_genre_text = links[-1].get_text(strip=True)
                clean_genre = last_genre_text.replace(' 소설', '').replace(' 웹소설', '').replace(' 장르', '').strip()
                
                mapped_genre = self._map_genre(clean_genre)
                if mapped_genre:
                    print(f"  [{self.platform_name}] Breadcrumb 장르: {last_genre_text} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': self.confidence,
                        'source': f'{self.platform_name.lower()}_breadcrumb',
                        'raw_genre': last_genre_text,
                        'url': url
                    }
        
        return None
    
    def _extract_from_meta(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """메타 태그에서 장르 추출"""
        meta_tags = soup.find_all('meta')
        
        for meta in meta_tags:
            if meta.get('name') == 'keywords' or meta.get('property') == 'keywords':
                content = meta.get('content', '')
                mapped_genre = self._map_genre(content)
                
                if mapped_genre:
                    print(f"  [{self.platform_name}] 메타 장르: {content[:30]} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': 0.95,
                        'source': f'{self.platform_name.lower()}_meta',
                        'raw_genre': content[:30],
                        'url': url
                    }
        
        return None
    
    def _extract_from_links(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """장르 링크에서 추출"""
        genre_links = soup.find_all('a', href=True)
        
        priority_genres = ['퓨전 판타지', '현대 판타지', '게임 판타지', 
                          '로맨스 판타지', '무협', '판타지']
        
        for genre_key in priority_genres:
            for link in genre_links:
                link_text = link.get_text(strip=True)
                if link_text == genre_key:
                    mapped_genre = self._map_genre(genre_key)
                    if mapped_genre:
                        print(f"  [{self.platform_name}] 링크 장르: {link_text} → {mapped_genre}")
                        return {
                            'genre': mapped_genre,
                            'confidence': 0.95,
                            'source': f'{self.platform_name.lower()}_link',
                            'raw_genre': link_text,
                            'url': url
                        }
        
        return None
    
    def _extract_from_text(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """본문에서 장르 추출"""
        text_content = soup.get_text()
        
        priority_genres = ['퓨전판타지', '퓨전 판타지', '현대판타지', '게임판타지', 
                          '로맨스판타지', '판타지', '무협', '로맨스']
        
        for genre_key in priority_genres:
            if genre_key in text_content:
                mapped_genre = self._map_genre(genre_key)
                if mapped_genre:
                    print(f"  [{self.platform_name}] 본문 장르: {genre_key} → {mapped_genre}")
                    return {
                        'genre': mapped_genre,
                        'confidence': 0.90,
                        'source': f'{self.platform_name.lower()}_page',
                        'raw_genre': genre_key,
                        'url': url
                    }
        
        return None
    
    def _map_genre(self, genre_text: str) -> Optional[str]:
        """장르 매핑 (긴 키워드부터)"""
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for genre_key in sorted_genres:
            if genre_key in genre_text:
                return self.genre_mapping[genre_key]
        
        return None
