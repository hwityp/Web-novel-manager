"""
해외(중국 및 일본) 웹소설 플랫폼 전용 장르 추출기

지원 플랫폼:
- Qidian (起点中文网, qidian.com)
- JJWXC (晋江文学城, jjwxc.net)
- Baidu Baike (百度百科, baike.baidu.com)
- Syosetu (小説家になろう syosetu.com 및 ハーメルン syosetu.org)
- Kakuyomu (カクヨム, kakuyomu.jp)
"""

import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

from modules.classifier.src.core.platform_extractors.base_extractor import BasePlatformExtractor


class QidianExtractor(BasePlatformExtractor):
    """중국 최대 남성향 웹소설 플랫폼 치뎬(起点中文网, qidian.com) 추출기"""

    @property
    def platform_name(self) -> str:
        return "치뎬"

    @property
    def confidence(self) -> float:
        return 0.95

    @property
    def priority(self) -> int:
        return 3  # 높은 우선순위

    CN_QIDIAN_MAP = {
        '玄幻': '판타지',
        '奇幻': '판타지',
        '都市': '현판',
        '诸天无限': '현판',
        '无限流': '현판',
        '仙侠': '선협',
        '修真': '선협',
        '历史': '역사',
        '军事': '역사',
        '同人': '패러디',
        '轻小说': '패러디',
        '游戏': '겜판',
        '科幻': '퓨판',
        '武侠': '무협',
        '悬疑': '공포',
        '体育': '스포츠',
    }

    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        print(f"  [{self.platform_name}] 추출 시작 (링크 {len(links)}개)")
        urls = [link.get('href', '') if hasattr(link, 'get') else str(link) for link in links]

        for href in urls:
            if not href or not ('qidian.com' in href):
                continue

            soup = self.fetch_page(href)
            if not soup:
                continue

            # 1. 태그/분류 링크 탐색 (.book-info, .tag-wrap 등)
            raw_genres = []

            # meta 태그 확인 (og:novel:category 등)
            cat_meta = soup.find('meta', property=re.compile(r'category|genre', re.I))
            if cat_meta:
                content_val = cat_meta.get('content')
                if isinstance(content_val, str) and content_val.strip():
                    raw_genres.append(content_val.strip())
                elif isinstance(content_val, list):
                    raw_genres.extend(str(c).strip() for c in content_val if str(c).strip())

            # a 태그 중 카테고리 링크
            for a in soup.find_all('a', href=re.compile(r'/category/|/all\?')):
                text = a.get_text().strip()
                if text:
                    raw_genres.append(text)

            # 본문 내 텍스트 매칭
            body_text = soup.get_text()
            for cn_tag, mapped in self.CN_QIDIAN_MAP.items():
                if cn_tag in raw_genres or cn_tag in body_text[:2000]:
                    print(f"  [{self.platform_name}] 장르 발견: '{cn_tag}' → '{mapped}'")
                    return {
                        'genre': mapped,
                        'confidence': self.confidence,
                        'source': f"{self.platform_name}_meta",
                        'raw_genre': cn_tag,
                        'url': href
                    }

        return None


class JJWXCExtractor(BasePlatformExtractor):
    """중국 최대 여성향 웹소설 플랫폼 진장문학성(晋江文学城, jjwxc.net) 추출기"""

    @property
    def platform_name(self) -> str:
        return "진장문학성"

    @property
    def confidence(self) -> float:
        return 0.95

    @property
    def priority(self) -> int:
        return 3

    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        print(f"  [{self.platform_name}] 추출 시작 (링크 {len(links)}개)")
        urls = [link.get('href', '') if hasattr(link, 'get') else str(link) for link in links]

        for href in urls:
            if not href or not ('jjwxc.net' in href or 'jjwxc.com' in href):
                continue

            soup = self.fetch_page(href)
            if not soup:
                continue

            # 文章类型 탐색 (예: 原创-言情-架空历史-爱情)
            full_text = soup.get_text()
            if '文章类型' in full_text:
                m = re.search(r'文章类型[：:]\s*([^\n\r]+)', full_text)
                if m:
                    type_str = m.group(1).strip()
                    if any(kw in type_str for kw in ['言情', '古代言情', '现代言情', '纯爱', '幻想现言']):
                        print(f"  [{self.platform_name}] 언정 감지: '{type_str}' → '언정'")
                        return {
                            'genre': '언정',
                            'confidence': self.confidence,
                            'source': f"{self.platform_name}_meta",
                            'raw_genre': type_str,
                            'url': href
                        }
                    elif any(kw in type_str for kw in ['衍生', '同人']):
                        print(f"  [{self.platform_name}] 패러디 감지: '{type_str}' → '패러디'")
                        return {
                            'genre': '패러디',
                            'confidence': self.confidence,
                            'source': f"{self.platform_name}_meta",
                            'raw_genre': type_str,
                            'url': href
                        }

            # 기본적으로 진장은 거의 모든 인기작이 '언정' (여성향)
            if '言情' in full_text[:3000] or '古言' in full_text[:3000] or '现言' in full_text[:3000]:
                print(f"  [{self.platform_name}] 언정 텍스트 감지 → '언정'")
                return {
                    'genre': '언정',
                    'confidence': self.confidence,
                    'source': f"{self.platform_name}_text",
                    'raw_genre': '言情',
                    'url': href
                }

        return None


class BaiduBaikeExtractor(BasePlatformExtractor):
    """중국 백과사전 바이두 백과(百度百科, baike.baidu.com) 소설 정보 추출기"""

    @property
    def platform_name(self) -> str:
        return "바이두백과"

    @property
    def confidence(self) -> float:
        return 0.90

    @property
    def priority(self) -> int:
        return 4

    BAIKE_GENRE_MAP = {
        '古代言情': '언정',
        '现代言情': '언정',
        '言情': '언정',
        '仙侠': '선협',
        '修仙': '선협',
        '修真': '선협',
        '玄幻': '판타지',
        '奇幻': '판타지',
        '都市': '현판',
        '都市生活': '현판',
        '历史': '역사',
        '军事': '역사',
        '架空历史': '역사',
        '游戏': '겜판',
        '科幻': '퓨판',
        '末世': '퓨판',
        '武侠': '무협',
        '同人': '패러디',
        '衍生': '패러디',
    }

    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        print(f"  [{self.platform_name}] 추출 시작 (링크 {len(links)}개)")
        urls = [link.get('href', '') if hasattr(link, 'get') else str(link) for link in links]

        for href in urls:
            if not href or not ('baike.baidu.com' in href):
                continue

            soup = self.fetch_page(href)
            if not soup:
                continue

            full_text = soup.get_text()

            # 作品类型 / 题材 탐색
            m = re.search(r'(?:作品类型|小说类型|题材|类型)[：:]\s*([^\n\r]+)', full_text)
            if m:
                type_line = m.group(1).strip()
                for cn_k, mapped in self.BAIKE_GENRE_MAP.items():
                    if cn_k in type_line:
                        print(f"  [{self.platform_name}] 장르 발견: '{type_line}' → '{mapped}'")
                        return {
                            'genre': mapped,
                            'confidence': self.confidence,
                            'source': f"{self.platform_name}_item",
                            'raw_genre': type_line,
                            'url': href
                        }

            # 본문 내 장르 키워드
            for cn_k, mapped in self.BAIKE_GENRE_MAP.items():
                if f"这是一部{cn_k}" in full_text[:3000] or f"网络小说，属于{cn_k}" in full_text[:3000]:
                    print(f"  [{self.platform_name}] 본문 장르 매칭: '{cn_k}' → '{mapped}'")
                    return {
                        'genre': mapped,
                        'confidence': self.confidence,
                        'source': f"{self.platform_name}_text",
                        'raw_genre': cn_k,
                        'url': href
                    }

        return None


class SyosetuExtractor(BasePlatformExtractor):
    """일본 웹소설 플랫폼 소설가가 되자(syosetu.com) 및 하멜른(syosetu.org) 추출기"""

    @property
    def platform_name(self) -> str:
        return "소설가가되자"

    @property
    def confidence(self) -> float:
        return 0.92

    @property
    def priority(self) -> int:
        return 4

    SYOSETU_MAP = {
        'ハイファンタジー': '판타지',
        'ローファンタジー': '현판',
        '異世界〔恋愛〕': '로판',
        '現実世界〔恋愛〕': '로판',
        'VRゲーム': '겜판',
        '宇宙': '퓨판',
        '空想科学': '퓨판',
        'パニック': '퓨판',
        '歴史': '역사',
        '推理': '소설',
        'ホラー': '공포',
        'アクション': '판타지',
        'コメディー': '소설',
    }

    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        print(f"  [{self.platform_name}] 추출 시작 (링크 {len(links)}개)")
        urls = [link.get('href', '') if hasattr(link, 'get') else str(link) for link in links]

        for href in urls:
            if not href:
                continue

            # 1. 하멜른(syosetu.org)은 99% 이상 2차 창작(패러디) 소설 사이트
            if 'syosetu.org' in href:
                print(f"  [{self.platform_name}] 하멜른(ハーメルン) 감지 → '패러디'")
                return {
                    'genre': '패러디',
                    'confidence': 0.95,
                    'source': "하멜른_domain",
                    'raw_genre': '二次創作',
                    'url': href
                }

            # 2. 소설가가 되자(syosetu.com)
            if 'syosetu.com' in href:
                soup = self.fetch_page(href)
                if not soup:
                    continue

                full_text = soup.get_text()

                for jp_g, mapped in self.SYOSETU_MAP.items():
                    if jp_g in full_text[:2000]:
                        print(f"  [{self.platform_name}] 나로우 장르 감지: '{jp_g}' → '{mapped}'")
                        return {
                            'genre': mapped,
                            'confidence': self.confidence,
                            'source': f"{self.platform_name}_meta",
                            'raw_genre': jp_g,
                            'url': href
                        }

        return None


class KakuyomuExtractor(BasePlatformExtractor):
    """일본 웹소설 플랫폼 카쿠요무(カクヨム, kakuyomu.jp) 추출기"""

    @property
    def platform_name(self) -> str:
        return "카쿠요무"

    @property
    def confidence(self) -> float:
        return 0.92

    @property
    def priority(self) -> int:
        return 4

    KAKUYOMU_MAP = {
        '異世界ファンタジー': '판타지',
        '現代ファンタジー': '현판',
        'SF': '퓨판',
        '恋愛': '로판',
        'ラブコメ': '로판',
        'ホラー': '공포',
        'ミステリー': '소설',
        '歴史・時代・伝奇': '역사',
        '二次創作': '패러디',
    }

    def extract_genre(self, links: List[Any], title: str, author: Optional[str] = None) -> Optional[Dict[str, Any]]:
        print(f"  [{self.platform_name}] 추출 시작 (링크 {len(links)}개)")
        urls = [link.get('href', '') if hasattr(link, 'get') else str(link) for link in links]

        for href in urls:
            if not href or not ('kakuyomu.jp' in href):
                continue

            soup = self.fetch_page(href)
            if not soup:
                continue

            full_text = soup.get_text()
            for jp_g, mapped in self.KAKUYOMU_MAP.items():
                if jp_g in full_text[:2500]:
                    print(f"  [{self.platform_name}] 카쿠요무 장르 감지: '{jp_g}' → '{mapped}'")
                    return {
                        'genre': mapped,
                        'confidence': self.confidence,
                        'source': f"{self.platform_name}_meta",
                        'raw_genre': jp_g,
                        'url': href
                    }

        return None
