"""
저자명 기반 장르 데이터베이스
유명 작가의 장르를 매핑하여 검색 실패 시 활용
"""

from typing import Optional, Dict, List


class AuthorGenreDB:
    """저자명 → 장르 매핑 데이터베이스"""
    
    def __init__(self):
        """저자 데이터베이스 초기화"""
        self.author_genre_map = self._init_author_db()
    
    def _init_author_db(self) -> Dict[str, str]:
        """저자명 → 장르 매핑 초기화"""
        return {
            # 무협 작가
            "고룡": "무협",
            "김용": "무협",
            "와룡생": "무협",
            "금강": "무협",
            "사마달": "무협",
            "황이": "무협",
            "영초": "무협",
            "이광주": "무협",
            "홍파": "무협",
            "서효원": "무협",
            "백운생": "무협",
            "권천": "무협",
            "황기록": "무협",
            "천중행": "무협",
            "유소백": "무협",
            "백운상": "무협",
            "고월": "무협",
            "백상": "무협",
            "야설록": "무협",
            "해천인": "무협",
            "진산": "무협",
            "풍종호": "무협",
            "검무협": "무협",
            "무림": "무협",
            "검궁": "무협",
            "검제": "무협",
            "천마": "무협",
            "검황": "무협",
            "검성": "무협",
            "무신": "무협",
            "협객": "무협",
            "강호": "무협",
            "무당": "무협",
            "소림": "무협",
            "화산": "무협",
            "청운": "무협",
            "검마": "무협",
            "검선": "무협",
            "검신": "무협",
            "검존": "무협",
            "검왕": "무협",
            "검제": "무협",
            "검황": "무협",
            "검성": "무협",
            
            # 판타지 작가
            "이영도": "판타지",
            "전민희": "판타지",
            "이우혁": "판타지",
            "조정래": "판타지",
            "김경진": "판타지",
            "박성우": "판타지",
            "이상규": "판타지",
            "김태원": "판타지",
            "박종서": "판타지",
            "이상욱": "판타지",
            "김성일": "판타지",
            "박상준": "판타지",
            "이상민": "판타지",
            "김성민": "판타지",
            "박상민": "판타지",
            
            # 현판 작가
            "싱숑": "현판",
            "나는뭐든": "현판",
            "김용": "현판",
            "박상준": "현판",
            "이상민": "현판",
            
            # 로판 작가
            "이솔": "로판",
            "김려령": "로판",
            "박서련": "로판",
            "이상희": "로판",
            "김은진": "로판",
            
            # 역사 작가
            "김훈": "역사",
            "이문열": "역사",
            "박경리": "역사",
            "조정래": "역사",
            "황석영": "역사",
        }
    
    def get_genre_by_author(self, author: str) -> Optional[str]:
        """저자명으로 장르 조회
        
        Args:
            author: 저자명
            
        Returns:
            장르 또는 None
        """
        if not author:
            return None
        
        # 공백 제거
        author_clean = author.replace(' ', '').strip()
        
        # 정확 매칭
        if author_clean in self.author_genre_map:
            return self.author_genre_map[author_clean]
        
        # 부분 매칭 (저자명이 포함된 경우)
        for db_author, genre in self.author_genre_map.items():
            if db_author in author_clean or author_clean in db_author:
                return genre
        
        return None
    
    def add_author(self, author: str, genre: str):
        """저자 추가 (동적 확장)
        
        Args:
            author: 저자명
            genre: 장르
        """
        author_clean = author.replace(' ', '').strip()
        self.author_genre_map[author_clean] = genre
    
    def get_all_authors(self) -> List[str]:
        """모든 저자명 조회"""
        return list(self.author_genre_map.keys())
    
    def get_authors_by_genre(self, genre: str) -> List[str]:
        """장르별 저자 조회
        
        Args:
            genre: 장르
            
        Returns:
            저자명 리스트
        """
        return [author for author, g in self.author_genre_map.items() if g == genre]
    
    def get_stats(self) -> Dict[str, int]:
        """통계 정보
        
        Returns:
            장르별 저자 수
        """
        stats = {}
        for genre in self.author_genre_map.values():
            stats[genre] = stats.get(genre, 0) + 1
        return stats


# 싱글톤 인스턴스
_author_db_instance = None


def get_author_db() -> AuthorGenreDB:
    """AuthorGenreDB 싱글톤 인스턴스 반환"""
    global _author_db_instance
    if _author_db_instance is None:
        _author_db_instance = AuthorGenreDB()
    return _author_db_instance
