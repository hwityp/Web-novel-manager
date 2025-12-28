"""
Genre Cache

검색 결과를 캐싱하여 동일 제목에 대한 반복 검색을 방지합니다.
성능 향상을 위해 캐시를 최우선으로 확인합니다.

Validates: Requirements 9.1, 9.2, 9.4
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


def _get_base_path() -> Path:
    """PyInstaller 패키징 환경과 일반 실행 환경 모두에서 올바른 기본 경로 반환"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent.parent.parent


class GenreCache:
    """장르 검색 결과 캐시 관리"""
    
    CACHE_FILE = "config/genre_cache.json"
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        캐시 파일 로드
        
        Args:
            cache_file: 캐시 파일 경로 (None이면 기본 경로 사용)
        """
        self.cache_file = cache_file or self.CACHE_FILE
        self.entries: Dict[str, Dict] = {}
        self._modified = False
        self._load_cache()
    
    def _load_cache(self):
        """캐시 파일 로드"""
        try:
            # PyInstaller 환경 지원
            if self.cache_file == self.CACHE_FILE:
                cache_path = _get_base_path() / self.cache_file
            else:
                cache_path = Path(self.cache_file)
            
            if cache_path.exists():
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.entries = data.get('entries', {})
                print(f"[GenreCache] 캐시 로드 완료: {len(self.entries)}개 항목")
            else:
                print(f"[GenreCache] 캐시 파일 없음, 빈 캐시로 시작")
                self.entries = {}
                
        except Exception as e:
            print(f"[GenreCache] 캐시 로드 실패: {e}, 빈 캐시로 시작")
            self.entries = {}
    
    def get(self, title: str) -> Optional[Dict]:
        """
        캐시에서 장르 정보 조회
        
        Args:
            title: 순수 제목
            
        Returns:
            {'genre': str, 'confidence': str, 'source': str} 또는 None
        """
        if not title:
            return None
        
        # 정규화된 키로 조회
        key = self._normalize_key(title)
        entry = self.entries.get(key)
        
        if entry:
            print(f"  [캐시 히트] '{title}' → {entry.get('genre')} ({entry.get('source')})")
            return {
                'genre': entry.get('genre'),
                'confidence': entry.get('confidence'),
                'source': entry.get('source')
            }
        
        return None
    
    def set(self, title: str, genre: str, confidence: str, source: str):
        """
        캐시에 장르 정보 저장
        
        Args:
            title: 순수 제목
            genre: 분류된 장르
            confidence: 신뢰도 (high, medium, low)
            source: 출처 (플랫폼명 또는 'keyword')
        """
        if not title or not genre:
            return
        
        key = self._normalize_key(title)
        
        self.entries[key] = {
            'genre': genre,
            'confidence': confidence,
            'source': source,
            'cached_at': datetime.now().isoformat()
        }
        
        self._modified = True
        print(f"  [캐시 저장] '{title}' → {genre} ({source})")
    
    def _normalize_key(self, title: str) -> str:
        """
        캐시 키 정규화
        
        - 소문자 변환
        - 앞뒤 공백 제거
        
        Args:
            title: 원본 제목
            
        Returns:
            정규화된 키
        """
        return title.strip().lower()
    
    def save(self):
        """캐시를 파일에 저장"""
        if not self._modified:
            return
        
        try:
            cache_path = Path(self.cache_file)
            
            # 디렉토리 생성
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': '1.0',
                'description': '장르 검색 결과 캐시',
                'updated_at': datetime.now().isoformat(),
                'entries': self.entries
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._modified = False
            print(f"[GenreCache] 캐시 저장 완료: {len(self.entries)}개 항목")
            
        except Exception as e:
            print(f"[GenreCache] 캐시 저장 실패: {e}")
    
    def clear(self):
        """캐시 초기화"""
        self.entries = {}
        self._modified = True
    
    def size(self) -> int:
        """캐시 항목 수 반환"""
        return len(self.entries)
    
    def has(self, title: str) -> bool:
        """캐시에 해당 제목이 있는지 확인"""
        key = self._normalize_key(title)
        return key in self.entries


# 싱글톤 인스턴스
_genre_cache: Optional[GenreCache] = None


def get_genre_cache() -> GenreCache:
    """싱글톤 GenreCache 인스턴스 반환"""
    global _genre_cache
    if _genre_cache is None:
        _genre_cache = GenreCache()
    return _genre_cache
