"""
Genre Mapping Loader

외부 JSON 파일에서 장르 매핑 규칙을 로드하고 관리합니다.
플랫폼별 장르명을 표준 장르명으로 변환합니다.

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.3
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional


def _get_base_path() -> Path:
    """PyInstaller 패키징 환경과 일반 실행 환경 모두에서 올바른 기본 경로 반환"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent.parent.parent


class GenreMappingLoader:
    """장르 매핑 규칙 로더"""
    
    MAPPING_FILE = "config/genre_mapping.json"
    
    # 기본 매핑 (파일 로드 실패 시 사용)
    DEFAULT_MAPPINGS: Dict[str, str] = {
        "로맨스 판타지": "로판",
        "로맨스판타지": "로판",
        "로판": "로판",
        "로맨스": "로판",
        "BL": "로판",
        "현대판타지": "현판",
        "현대 판타지": "현판",
        "현대물": "현판",
        "현판": "현판",
        "퓨전판타지": "퓨판",
        "퓨전 판타지": "퓨판",
        "퓨전물": "퓨판",
        "퓨전": "퓨판",
        "퓨판": "퓨판",
        "게임판타지": "겜판",
        "게임 판타지": "겜판",
        "게임": "겜판",
        "겜판": "겜판",
        "무협": "무협",
        "무협 소설": "무협",
        "선협": "선협",
        "판타지": "판타지",
        "정통판타지": "판타지",
        "정통 판타지": "판타지",
        "라이트노벨": "판타지",
        "SF": "SF",
        "스포츠": "스포츠",
        "스포츠물": "스포츠",
        "역사": "역사",
        "역사물": "역사",
        "대체역사": "역사",
        "언정": "언정",
        "미스터리": "소설",
        "소설": "소설",
        "패러디": "패러디",  # [NEW]
        "팬픽": "패러디",    # [NEW]
    }
    
    # 기본 화이트리스트
    DEFAULT_WHITELIST: List[str] = [
        "현판", "퓨판", "무협", "로판", "겜판", "판타지",
        "SF", "역사", "선협", "언정", "스포츠", "소설", "패러디", "미분류"
    ]
    
    def __init__(self, mapping_file: Optional[str] = None):
        """
        매핑 파일 로드 (실패 시 기본 매핑 사용)
        
        Args:
            mapping_file: 매핑 파일 경로 (None이면 기본 경로 사용)
        """
        self.mapping_file = mapping_file or self.MAPPING_FILE
        self.mappings: Dict[str, str] = {}
        self.whitelist: List[str] = []
        self._load_mappings()
    
    def _load_mappings(self):
        """매핑 파일 로드"""
        try:
            # PyInstaller 환경 지원
            if self.mapping_file == self.MAPPING_FILE:
                mapping_path = _get_base_path() / self.mapping_file
            else:
                mapping_path = Path(self.mapping_file)
            
            if mapping_path.exists():
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.mappings = data.get('mappings', self.DEFAULT_MAPPINGS)
                self.whitelist = data.get('whitelist', self.DEFAULT_WHITELIST)
                print(f"[GenreMappingLoader] 매핑 파일 로드 완료: {len(self.mappings)}개 규칙")
            else:
                print(f"[GenreMappingLoader] 매핑 파일 없음, 기본 매핑 사용")
                self.mappings = self.DEFAULT_MAPPINGS.copy()
                self.whitelist = self.DEFAULT_WHITELIST.copy()
                
        except Exception as e:
            print(f"[GenreMappingLoader] 매핑 파일 로드 실패: {e}, 기본 매핑 사용")
            self.mappings = self.DEFAULT_MAPPINGS.copy()
            self.whitelist = self.DEFAULT_WHITELIST.copy()
    
    def map_genre(self, platform_genre: str) -> str:
        """
        플랫폼 장르를 표준 장르로 매핑
        
        Args:
            platform_genre: 플랫폼에서 추출한 장르명
            
        Returns:
            표준 장르명 (GENRE_WHITELIST에 있는 값)
            매핑되지 않거나 화이트리스트에 없으면 '미분류'
        """
        if not platform_genre:
            return "미분류"
        
        # 정확한 매핑 찾기
        mapped = self.mappings.get(platform_genre)
        
        if mapped:
            # 화이트리스트 검증
            if mapped in self.whitelist:
                return mapped
            else:
                return "미분류"
        
        # 부분 매칭 시도 (긴 키워드부터)
        sorted_keys = sorted(self.mappings.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in platform_genre:
                mapped = self.mappings[key]
                if mapped in self.whitelist:
                    return mapped
        
        # 매핑 실패
        return "미분류"
    
    def is_valid_genre(self, genre: str) -> bool:
        """
        장르가 GENRE_WHITELIST에 있는지 확인
        
        Args:
            genre: 확인할 장르명
            
        Returns:
            화이트리스트에 있으면 True
        """
        return genre in self.whitelist
    
    def get_whitelist(self) -> List[str]:
        """화이트리스트 반환"""
        return self.whitelist.copy()
    
    def get_all_mappings(self) -> Dict[str, str]:
        """모든 매핑 규칙 반환"""
        return self.mappings.copy()


# 싱글톤 인스턴스
_mapping_loader: Optional[GenreMappingLoader] = None


def get_mapping_loader() -> GenreMappingLoader:
    """싱글톤 GenreMappingLoader 인스턴스 반환"""
    global _mapping_loader
    if _mapping_loader is None:
        _mapping_loader = GenreMappingLoader()
    return _mapping_loader
