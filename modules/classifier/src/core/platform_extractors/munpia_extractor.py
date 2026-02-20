"""
문피아 장르 추출기
"""

import re
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class MunpiaExtractor(BasePlatformExtractor):
    """문피아 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "문피아"
    
    @property
    def confidence(self) -> float:
        return 0.92  # 신뢰도 상향 (90% → 92%)
    
    @property
    def priority(self) -> int:
        return 2
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """문피아에서 장르 추출"""
        urls = self._extract_urls(links)
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            if not self._verify_title(soup, title):
                continue
            
            # meta-path에서 장르 추출
            genre_result = self._extract_from_meta_path(soup, url)
            if genre_result:
                return genre_result
            
            # 본문에서 장르 추출
            genre_result = self._extract_from_text_common(soup, url, confidence=0.85)
            if genre_result:
                return genre_result
        
        return None
    
    def _extract_urls(self, links: List[Any]) -> List[str]:
        """URL 추출 및 모바일 링크 변환"""
        import re
        urls = []
        seen = set()
        
        for link in links:
            href = link.get('href', '') if hasattr(link, 'get') else str(link)
            if href:
                original_href = href
                
                # 모바일 링크를 데스크톱으로 변환
                # https://m.munpia.com/novel/detail/289952 → https://novel.munpia.com/289952
                if 'm.munpia.com/novel/detail/' in href:
                    href = re.sub(r'm\.munpia\.com/novel/detail/(\d+)', r'novel.munpia.com/\1', href)
                    print(f"  [{self.platform_name}] 모바일 링크 변환: {original_href} → {href}")
                elif 'm.munpia.com' in href:
                    # 기타 모바일 링크
                    href = href.replace('m.munpia.com', 'novel.munpia.com')
                    print(f"  [{self.platform_name}] 모바일 링크 변환: {original_href} → {href}")
                
                if href not in seen:
                    seen.add(href)
                    urls.append(href)
        
        return urls
    
    def _verify_title(self, soup, title: str) -> bool:
        """제목 확인"""
        # h2.title 태그
        title_elem = soup.find('h2', class_='title')
        if title_elem:
            page_title = title_elem.get_text(strip=True)
        else:
            # title 태그 또는 og:title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                page_title = og_title.get('content', '').strip()
            else:
                title_tag = soup.find('title')
                if title_tag:
                    page_title_text = title_tag.get_text()
                    # " - 웹소설 문피아" 같은 플랫폼 접미사만 제거
                    # 부제목은 유지 (예: "오파츠 - 수천 년은 이른 물건")
                    if ' - 웹소설 문피아' in page_title_text:
                        page_title = page_title_text.replace(' - 웹소설 문피아', '').strip()
                    elif ' - 문피아' in page_title_text:
                        page_title = page_title_text.replace(' - 문피아', '').strip()
                    else:
                        page_title = page_title_text.strip()
                else:
                    return False
        
        # 태그 제거 (normalize_title에서도 처리되지만, 로그 출력을 위해 미리 제거)
        cleaned = re.sub(r'\s*\[.*?\]\s*', '', page_title)
        cleaned = re.sub(r'^(개정판|합본|특별판|완전판|무삭제판|리마스터판)\s*[-|]\s*', '', cleaned)
        cleaned = re.sub(r'\s*[-|]\s*(개정판|합본|특별판|완전판|무삭제판|리마스터판)$', '', cleaned)
        
        matched, _ = self.match_title(title, cleaned, strict_short=True)
        
        if matched:
            print(f"  [{self.platform_name}] 제목 일치: {page_title}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {page_title}")
            return False
    
    def _extract_from_meta_path(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """meta-path에서 장르 추출"""
        meta_path = soup.find('p', class_='meta-path')
        if not meta_path:
            return None
        
        # 전체 경로에서 마지막 부분(장르) 추출
        path_text = meta_path.get_text(strip=True)
        path_parts = [p.strip() for p in path_text.split('>')]
        
        if len(path_parts) >= 3:
            genre_text = path_parts[-1]
            found_genres = [g.strip() for g in genre_text.split(',')]
        else:
            strong = meta_path.find('strong')
            if strong:
                genre_text = strong.get_text(strip=True)
                found_genres = [g.strip() for g in genre_text.split(',')]
            else:
                return None
        
        if not found_genres:
            return None
        
        # 디버그: 원본 장르 출력
        print(f"  [{self.platform_name}] 발견된 장르: {', '.join(found_genres)}")
        
        # 유효한 장르만 필터링
        valid_genres = [g for g in found_genres if g in self.genre_mapping]
        if valid_genres:
            print(f"  [{self.platform_name}] 매핑 가능한 장르: {', '.join(valid_genres)}")
            found_genres = valid_genres
        else:
            print(f"  [{self.platform_name}] 매핑 불가능한 장르들, 원본 사용")
        
        # 다중 장르 처리
        if len(found_genres) >= 2:
            primary_genre = self._resolve_multiple_genres(found_genres)
            if primary_genre:
                mapped_genre = self.genre_mapping.get(primary_genre, primary_genre)
                print(f"  [{self.platform_name}] meta-path 장르 (다중): {', '.join(found_genres)} → {primary_genre} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_meta_path',
                    'raw_genre': primary_genre,
                    'url': url
                }
        
        # 단일 장르
        if len(found_genres) == 1:
            genre_key = found_genres[0]
            if genre_key in self.genre_mapping:
                mapped_genre = self.genre_mapping[genre_key]
                print(f"  [{self.platform_name}] meta-path 장르: {genre_key} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_meta_path',
                    'raw_genre': genre_key,
                    'url': url
                }
        
        return None
    
    def _resolve_multiple_genres(self, genres: List[str]) -> Optional[str]:
        """다중 장르 우선순위 결정"""
        history_genres = ['대체역사', '대체 역사', '역사']
        fantasy_genres = ['판타지', '현대판타지', '퓨전판타지', '퓨전', '현판']
        military_genres = ['전쟁·밀리터리', '전쟁 밀리터리', '밀리터리', '전쟁']
        
        # 밀리터리 최우선 (다른 장르와 함께 있어도 밀리터리 선택)
        has_military = any(m in genres for m in military_genres)
        if has_military:
            for m in military_genres:
                if m in genres:
                    return m
        
        # 대체역사 + 판타지 → 역사
        has_history = any(h in genres for h in history_genres)
        has_fantasy = any(f in genres for f in fantasy_genres)
        
        if has_history and has_fantasy:
            for h in history_genres:
                if h in genres:
                    return h
        
        # 현대판타지 + 스포츠 → 스포츠
        if '현대판타지' in genres and '스포츠' in genres:
            return '스포츠'
        
        # 현대판타지 + 퓨전 → 현판
        if '현대판타지' in genres and '퓨전' in genres:
            return '현대판타지'
        
        # 판타지 + 퓨전 → 퓨전판타지
        if '판타지' in genres and '퓨전' in genres:
            return '퓨전판타지' if '퓨전판타지' in self.genre_mapping else '퓨전'
        
        # 판타지 + 게임 → 게임판타지
        if '판타지' in genres and '게임' in genres:
            return '게임판타지' if '게임판타지' in self.genre_mapping else '게임'
        
        # 가장 세부적인 장르 선택 (길이 순)
        return sorted(genres, key=len, reverse=True)[0]
    

