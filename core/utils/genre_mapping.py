"""
==============================================================================
파일: core/utils/genre_mapping.py
역할 및 목적:
    각양각색의 플랫폼별(카카오페이지, 시리즈, 리디북스, 조아라 등) 장르 명칭을 시스템 표준 장르(현판, 무협, 로판 등)로 정규화 매핑.
    `config/genre_mapping.json`을 동적으로 로드하고, 파일 누락 시 안전한 `DEFAULT_MAPPINGS` 폴백을 제공합니다.
주요 구성 요소:
    - GenreMappingLoader: 장르 매핑 규칙 로더 및 변환기 클래스
    - get_mapping_loader(): 싱글톤 인스턴스 반환 함수
    - map_genre(): 원시 장르명 문자열을 표준 장르명으로 변환
상호 연관 관계 및 의존성:
    - Caller: core.adapters.genre_classifier_adapter
    - Callee: config/genre_mapping.json
수정 시 주의사항:
    - 표준 장르 매핑 변경 시 `config/pipeline_config.py`의 `GENRE_WHITELIST`와 일관성을 유지해야 합니다.
==============================================================================
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
        "SF": "판타지",
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
        "仙侠": "선협",
        "修仙": "선협",
        "修真": "선협",
        "言情": "언정",
        "古代言情": "언정",
        "现代言情": "언정",
        "古言": "언정",
        "现言": "언정",
        "玄幻": "판타지",
        "都市": "현판",
        "科幻": "판타지",
        "异界": "퓨판",
        "武侠": "무협",
        "ハイファンタジー": "판타지",
        "ローファンタジー": "현판",
        "異世界": "판타지",
        "異世界転生": "판타지",
        "異世界転移": "판타지",
        "恋愛": "로판",
        "悪役令嬢": "로판",
        "ライトノベル": "판타지",
    }
    
    # 기본 화이트리스트
    DEFAULT_WHITELIST: List[str] = [
        "현판", "퓨판", "무협", "로판", "겜판", "판타지",
        "역사", "선협", "언정", "스포츠", "소설", "패러디", "미분류"
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
    
    @staticmethod
    def is_chinese_romance(title: str, text: str = "") -> bool:
        """중국 로판/로맨스 소설인지 판단"""
        import re
        sino_patterns = [
            r'[\u4e00-\u9fff\u3400-\u4dbf]',  # 한자 포함
            r'천월', r'비빈', r'낭낭', r'계후', r'소교낭', r'약향농', r'복운', r'육령', r'소저', r'공자',
            r'악독', r'미인', r'종전', r'매매', r'사합원', r'농부', r'가속원래', r'독심', r'만급작정',
            r'궁투', r'후궁', r'태의', r'칠령', r'팔령', r'지청', r'부처천월', r'교연미인', r'농부가적',
            r'부인', r'수모', r'단총', r'개가', r'계모', r'반공가산', r'시천당', r'소내포', r'복보',
            r'교처', r'군관', r'미색', r'극본'
        ]
        full_text = f"{title} {text}"
        for pat in sino_patterns:
            if re.search(pat, full_text):
                return True
        return False

    def map_genre(self, platform_genre: str, title: str = "", text: str = "") -> str:
        """
        플랫폼 장르를 표준 장르로 매핑 (중국 로판/로맨스는 '언정'으로 전환)
        
        Args:
            platform_genre: 플랫폼에서 추출한 장르명
            title: 소설 제목 (중국 로판 판별용)
            text: 원본 파일명/스니펫 (선택)
            
        Returns:
            표준 장르명 (GENRE_WHITELIST에 있는 값)
            매핑되지 않거나 화이트리스트에 없으면 '미분류'
        """
        if not platform_genre:
            return "미분류"
        
        # 정확한 매핑 찾기
        mapped = self.mappings.get(platform_genre)
        
        if not mapped:
            # 부분 매칭 시도 (긴 키워드부터)
            sorted_keys = sorted(self.mappings.keys(), key=len, reverse=True)
            for key in sorted_keys:
                if key in platform_genre:
                    mapped = self.mappings[key]
                    break
        
        if mapped and mapped in self.whitelist:
            # 로판/로맨스의 경우 중국 웹소설 판단 시 '언정'으로 변경
            if mapped in ['로판', '로맨스'] and self.is_chinese_romance(title, text):
                return '언정'
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
