"""
네이버시리즈 장르 추출기
"""

import re
from typing import Dict, List, Optional, Any
from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class NaverSeriesExtractor(BasePlatformExtractor):
    """네이버시리즈 장르 추출기"""
    
    @property
    def platform_name(self) -> str:
        return "네이버시리즈"
    
    @property
    def confidence(self) -> float:
        return 0.88  # 신뢰도 상향 (85% → 88%)
    
    @property
    def priority(self) -> int:
        return 3  # 우선순위 상향 (4 → 3)
    
    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """네이버시리즈에서 장르 추출"""
        urls = self._extract_urls(links)
        
        for idx, url in enumerate(urls[:3], 1):
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            if not self._verify_title(soup, title, author):
                continue
            
            # e북 카테고리에서 장르 추출 (최우선)
            if '/ebook/' in url:
                genre_result = self._extract_from_ebook_category(soup, url)
                if genre_result:
                    # 현판 → 스포츠 재분류 필요 여부 표시
                    if genre_result['genre'] == '현판':
                        genre_result['needs_sports_check'] = True
                    # 판타지 → 역사/겜판/퓨판 세분화 필요 여부 표시
                    elif genre_result['genre'] == '판타지':
                        genre_result['needs_fantasy_refinement'] = True
                    return genre_result
            
            # 메타 태그에서 장르 추출
            genre_result = self._extract_from_meta(soup, url)
            if genre_result:
                # 현판 → 스포츠 재분류 필요 여부 표시
                if genre_result['genre'] == '현판':
                    genre_result['needs_sports_check'] = True
                # 판타지 → 역사/겜판/퓨판 세분화 필요 여부 표시
                elif genre_result['genre'] == '판타지':
                    genre_result['needs_fantasy_refinement'] = True
                return genre_result
            
            # 본문에서 장르 추출
            genre_result = self._extract_from_text(soup, url)
            if genre_result:
                # 현판 → 스포츠 재분류 필요 여부 표시
                if genre_result['genre'] == '현판':
                    genre_result['needs_sports_check'] = True
                # 판타지 → 역사/겜판/퓨판 세분화 필요 여부 표시
                elif genre_result['genre'] == '판타지':
                    genre_result['needs_fantasy_refinement'] = True
                return genre_result
        
        return None
    

    
    def _verify_title(self, soup, title: str, author: Optional[str] = None) -> bool:
        """제목 확인 (저자명 포함)"""
        cleaned_page_title = None
        
        # og:title 메타 태그 (최우선)
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            og_title_text = og_title.get('content', '').strip()
            if og_title_text and '네이버' not in og_title_text and '시리즈' not in og_title_text:
                cleaned_page_title = self._clean_title(og_title_text)
        
        # h 태그에서 제목 찾기
        if not cleaned_page_title:
            exclude_keywords = ['navigation', 'nav', 'bar', 'menu', 'header', 'footer', 'local', 'global', 'series']
            
            for tag in soup.find_all(['h1', 'h2', 'h3']):
                tag_text = tag.get_text(strip=True)
                text_lower = tag_text.lower()
                
                if any(keyword in text_lower for keyword in exclude_keywords):
                    continue
                if tag_text.isupper() and len(tag_text) <= 10:
                    continue
                if tag_text and len(tag_text) >= 2:
                    if '네이버' not in tag_text and '시리즈' not in tag_text and 'naver' not in text_lower:
                        cleaned_page_title = self._clean_title(tag_text)
                        break
        
        # title 태그 (폴백)
        if not cleaned_page_title:
            title_tag = soup.find('title')
            if title_tag:
                page_title_text = title_tag.get_text()
                cleaned_page_title = self._clean_title(page_title_text)
        
        if not cleaned_page_title or cleaned_page_title.lower() in ['네이버 시리즈', '네이버시리즈']:
            return False
        
        # 저자명 포함 매칭 (짧은 제목 엄격 매칭)
        matched, match_info = self.match_title(title, cleaned_page_title, search_author=author, strict_short=True)
        
        if matched:
            if match_info.get('type') == 'short_with_author':
                print(f"  [{self.platform_name}] 제목 일치 (저자명 확인): {cleaned_page_title}")
            else:
                print(f"  [{self.platform_name}] 제목 일치: {cleaned_page_title}")
            return True
        else:
            print(f"  [{self.platform_name}] 제목 불일치: {cleaned_page_title}")
            return False
    
    def _clean_title(self, title_text: str) -> str:
        """제목 정제"""
        cleaned = re.sub(r'\s*[\[\(【<].*?[\]\)】>]\s*', ' ', title_text)
        cleaned = re.sub(r'\s*[-|]\s*(웹소설\s*홈\s*:\s*)?네이버\s*시리즈.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*[-|]\s*네이버시리즈.*$', '', cleaned, flags=re.IGNORECASE)
        
        if re.match(r'^네이버\s*시리즈\s*$', cleaned, flags=re.IGNORECASE):
            return ''
        
        cleaned = re.sub(r'^(개정판|합본|특별판|완전판|무삭제판|리마스터판)\s*[|]\s*', '', cleaned)
        cleaned = re.sub(r'\s*[|]\s*(개정판|합본|특별판|완전판|무삭제판|리마스터판)$', '', cleaned)
        cleaned = ' '.join(cleaned.split()).strip()
        
        return cleaned
    
    def _extract_from_meta(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """메타 태그에서 장르 추출"""
        meta_tags = soup.find_all('meta')
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for meta in meta_tags:
            content = meta.get('content', '')
            name = meta.get('name', '')
            
            # description에서 해시태그 추출
            if name == 'description' and '#' in content:
                hashtags = re.findall(r'#([가-힣a-zA-Z]+)', content)
                
                if hashtags:
                    for hashtag in hashtags:
                        if hashtag in self.genre_mapping:
                            mapped_genre = self.genre_mapping[hashtag]
                            print(f"  [{self.platform_name}] 메타 장르 (해시태그): #{hashtag} → {mapped_genre}")
                            return {
                                'genre': mapped_genre,
                                'confidence': self.confidence,
                                'source': f'{self.platform_name.lower()}_meta',
                                'raw_genre': hashtag,
                                'url': url
                            }
            
            # 일반 메타 태그
            if any(genre in content for genre in ['판타지', '무협', '로맨스', 'BL']):
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
    
    def _extract_from_ebook_category(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """e북 카테고리에서 장르 추출
        
        HTML 구조:
        <li><span class="tit tit_cate">카테고리</span> 
            <a href="/ebook/categoryProductList.series?categoryTypeCode=genre&genreCode=301" 
               class="NPI=a:clink,i:6394378">소설</a>
        </li>
        """
        # 카테고리 링크 찾기
        category_links = soup.find_all('a', href=lambda x: x and '/ebook/categoryProductList.series' in str(x))
        
        if not category_links:
            print(f"  [{self.platform_name}] e북 카테고리 링크를 찾지 못함")
            return None
        
        # 카테고리 텍스트 추출
        for link in category_links:
            category_text = link.get_text(strip=True)
            
            # e북 카테고리 매핑
            ebook_category_mapping = {
                '소설': '소설',
                '판타지': '판타지',
                '로맨스': '로판',
                '무협': '무협',
                'BL': '로판',
                '라이트노벨': '판타지',
                '추리/미스터리': '미스터리',
                'SF': 'SF',
                '역사': '역사',
                '스릴러': '스릴러',
                '공포': '공포',
                '시/에세이': '소설',
                '인문': '소설',
                '자기계발': '소설',
            }
            
            if category_text in ebook_category_mapping:
                mapped_genre = ebook_category_mapping[category_text]
                print(f"  [{self.platform_name}] e북 카테고리: {category_text} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_ebook_category',
                    'raw_genre': category_text,
                    'url': url
                }
            else:
                print(f"  [{self.platform_name}] e북 카테고리 '{category_text}'는 매핑되지 않음")
        
        return None
    
    def _extract_from_text(self, soup, url: str) -> Optional[Dict[str, Any]]:
        """본문에서 장르 추출"""
        # 제목 근처 텍스트만 추출
        title_elem = soup.find('title')
        if title_elem:
            body = soup.find('body')
            if body:
                body_text = body.get_text()
                title_text = title_elem.get_text()
                title_idx = body_text.find(title_text)
                if title_idx != -1:
                    info_text = body_text[title_idx:title_idx+1000]
                else:
                    info_text = body_text[:1000]
            else:
                info_text = soup.get_text()[:1000]
        else:
            info_text = soup.get_text()[:1000]
        
        sorted_genres = sorted(self.genre_mapping.keys(), key=len, reverse=True)
        
        for genre_key in sorted_genres:
            if genre_key in info_text:
                mapped_genre = self.genre_mapping[genre_key]
                print(f"  [{self.platform_name}] 본문 장르: {genre_key} → {mapped_genre}")
                return {
                    'genre': mapped_genre,
                    'confidence': self.confidence,
                    'source': f'{self.platform_name.lower()}_page',
                    'raw_genre': genre_key,
                    'url': url
                }
        
        return None
