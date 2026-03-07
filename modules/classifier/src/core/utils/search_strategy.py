"""
검색 전략 관리
"""

from typing import List, Dict, Any, Optional
from modules.classifier.src.core.utils.title_utils import parse_title_info, is_short_title, normalize_title, add_spacing_to_title
# split_title_variants는 더 이상 사용하지 않음 (제목 분리 비활성화)


class SearchStrategy:
    """검색 전략 관리 클래스"""
    
    def __init__(self, title: str):
        """
        Args:
            title: 원본 제목
        """
        self.original_title = title
        
        # 제목 정규화
        normalized_title = normalize_title(title)
        
        self.title_info = parse_title_info(normalized_title)
        self.main_title = self.title_info['main_title']
        self.subtitle = self.title_info['subtitle']
        self.author = self.title_info['author']
        # 제목 분리 비활성화 (의미 없는 검색 방지)
        # self.variants = split_title_variants(self.main_title)
        self.is_short = is_short_title(self.main_title)
        
        # 띄어쓰기 변형 추가
        self.spaced_title = add_spacing_to_title(self.main_title)
    
    def get_search_queries(self) -> List[Dict[str, Any]]:
        """검색 쿼리 목록 생성 (우선순위 순)
        
        Returns:
            [
                {'query': str, 'description': str, 'priority': int},
                ...
            ]
        """
        queries = []
        
        # 저자명이 있는 경우: 제목 + 저자명을 최우선으로
        if self.author:
            queries.append({
                'query': f"{self.main_title} {self.author}",
                'description': f"제목 + 저자명",
                'priority': 1
            })
        
        # 1차: 제목 특성에 따라 전략 선택
        if self.is_short:
            # 짧은 제목: "소설" 키워드 추가 (단, 저자명이 없을 때만)
            if not self.author:
                queries.append({
                    'query': f"소설 {self.main_title}",
                    'description': f"짧은 제목 → '소설' 키워드 추가",
                    'priority': 2
                })
            else:
                queries.append({
                    'query': self.main_title,
                    'description': f"제목만",
                    'priority': 2
                })
        else:
            # 긴 제목: "소설" 키워드 없이
            queries.append({
                'query': self.main_title,
                'description': f"긴 제목 → '소설' 키워드 없이",
                'priority': 2
            })
        
        # 2차: 1차와 반대 전략
        if self.is_short:
            queries.append({
                'query': self.main_title,
                'description': f"'소설' 키워드 제거",
                'priority': 3
            })
        else:
            queries.append({
                'query': f"소설 {self.main_title}",
                'description': f"'소설' 키워드 추가",
                'priority': 3
            })
        
        # 2.5차: 중국 소설 제목 패턴 감지 시 추가 검색
        if self._is_chinese_novel_title(self.main_title):
            queries.append({
                'query': f"{self.main_title} 중국 소설",
                'description': f"중국 소설 제목 패턴 → '중국 소설' 키워드 추가",
                'priority': 3
            })
            queries.append({
                'query': f"{self.main_title} 선협",
                'description': f"중국 소설 제목 패턴 → '선협' 키워드 추가",
                'priority': 4
            })
        
        # 3차: 부제로 검색
        if self.subtitle:
            queries.append({
                'query': self.subtitle,
                'description': f"부제로 검색",
                'priority': 4
            })
            
            # 부제 + 저자명
            if self.author:
                queries.append({
                    'query': f"{self.subtitle} {self.author}",
                    'description': f"부제 + 저자명",
                    'priority': 5
                })
        
        # 4차: 띄어쓰기 변형 검색 (원본과 다른 경우만)
        if self.spaced_title != self.main_title:
            queries.append({
                'query': self.spaced_title,
                'description': f"띄어쓰기 추가",
                'priority': 4
            })
            
            if self.author:
                queries.append({
                    'query': f"{self.spaced_title} {self.author}",
                    'description': f"띄어쓰기 추가 + 저자명",
                    'priority': 5
                })
        
        # 5차: 제목 분리 검색 비활성화 (의미 없는 검색 방지)
        # 제목 분리는 오히려 잘못된 결과를 가져올 수 있음
        # 예: "영웅왕 그 미래는" → "영웅왕 그" (의미 없음)
        # 유사도 매칭으로 대체
        
        return queries
    
    # 중국 소설 제목 어미 패턴 (한글 번역된 형태)
    CHINESE_TITLE_ENDINGS = [
        '전기', '열전', '비록', '야사', '연의', '지전', '기전',
        '행기', '유기', '몽기', '환기', '선기', '기담',
    ]
    
    # 단독으로 사용 시 중국 소설일 가능성이 높은 어미 (짧은 패턴)
    CHINESE_TITLE_SHORT_ENDINGS = ['전', '기', '록', '지']
    
    # 한국어 제목에서 제외할 단어 (오탐 방지)
    CHINESE_TITLE_EXCEPTIONS = [
        '역전기', '전기', '일기', '세기', '용기', '인기',
        '무도', '동기', '표기', '연기', '위기', '계기',
    ]
    
    def _is_chinese_novel_title(self, title: str) -> bool:
        """중국 소설 제목 패턴인지 확인
        
        한글로 번역된 중국 소설은 제목이 ~전, ~기, ~록, ~지 등으로 끝나는 경우가 많음.
        예: 범인수선전기, 투파창궁, 무련순행기, 태초검존
        """
        import re
        
        # 한국어 예외 단어 확인
        for exception in self.CHINESE_TITLE_EXCEPTIONS:
            if exception in title:
                return False
        
        # 긴 어미 패턴 확인 (우선순위 높음)
        for ending in self.CHINESE_TITLE_ENDINGS:
            if title.endswith(ending) and len(title) > len(ending) + 1:
                return True
        
        # 짧은 어미 패턴 확인 (한글로만 이루어진 제목에서)
        title_no_space = title.replace(' ', '')
        if re.match(r'^[가-힣]+$', title_no_space) and len(title_no_space) >= 4:
            for ending in self.CHINESE_TITLE_SHORT_ENDINGS:
                if title_no_space.endswith(ending) and len(title_no_space) > len(ending) + 2:
                    return True
        
        return False
    
    def log_info(self):
        """제목 분석 정보 로그 출력"""
        print(f"  [제목 분석] 원본: '{self.original_title}' → {self.title_info}")
        
        # 제목 분리 로그 제거 (비활성화됨)
        
        if self.is_short:
            print(f"  [검색 전략] 짧은 제목 → '소설' 키워드 추가")
        else:
            print(f"  [검색 전략] 긴 제목 → '소설' 키워드 없이")
