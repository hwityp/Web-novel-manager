"""
==============================================================================
파일: core/novel_task.py
역할 및 목적:
    웹소설 처리 파이프라인 전 단계를 관통하는 핵심 데이터 모델(`NovelTask`).
    원본 파일 경로, 추출된 순수 제목(Title Anchor), 저자, 권수/범위, 완결/외전 여부,
    분류된 장르, 신뢰도(confidence), 처리 상태(status) 등을 캡슐화하여 파이프라인 모듈 간 공유합니다.
주요 구성 요소:
    - NovelTask: 데이터클래스 기반 작업 단위 구조체
    - to_dict(), from_dict(): 직렬화/역직렬화 메서드
상호 연관 관계 및 의존성:
    - Caller: core.pipeline_orchestrator, core.adapters.*, gui.main_window, scripts.*
    - Callee: pathlib.Path
수정 시 주의사항:
    - 필드 추가 시 to_dict(), from_dict() 및 하위 호환성을 유지해야 합니다.
    - `original_path`는 절대 변경하지 않고, 단계별 파일 이동 시 `current_path`만 갱신해야 합니다.
==============================================================================
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import json


@dataclass
class NovelTask:
    """웹소설 처리의 모든 상태를 담는 데이터 객체"""
    
    # 파일 경로
    original_path: Path          # 원본 파일 경로
    current_path: Path           # 현재 파일 경로 (처리 중 변경될 수 있음)
    
    # 파싱된 정보
    raw_name: str                # 원본 파일명 (확장자 제외)
    title: str = ""              # 추출된 제목 (Title Anchor)
    author: str = ""             # 저자명
    genre: str = ""              # 분류된 장르
    volume_info: str = ""        # 권/부 정보 (예: "1-2부")
    range_info: str = ""         # 범위 정보 (예: "1-536")
    is_completed: bool = False   # 완결 여부
    side_story: str = ""         # 외전 정보 (예: "외전 1-5")
    edition_info: str = ""       # 판본 정보 (예: "[개정판]")

    
    # 처리 상태
    status: str = "pending"      # pending, processing, completed, failed, skipped
    confidence: str = "none"     # none, low, medium, high
    source: str = ""             # 판단 근거 (cache, 문피아, 리디북스, 사용자 등)
    error_message: str = ""      # 에러 발생 시 메시지
    
    # 메타데이터
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화를 위한 딕셔너리 변환"""
        return {
            'original_path': str(self.original_path),
            'current_path': str(self.current_path),
            'raw_name': self.raw_name,
            'title': self.title,
            'author': self.author,
            'genre': self.genre,
            'volume_info': self.volume_info,
            'range_info': self.range_info,
            'is_completed': self.is_completed,
            'side_story': self.side_story,
            'edition_info': self.edition_info,
            'status': self.status,
            'confidence': self.confidence,
            'source': self.source,
            'error_message': self.error_message,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NovelTask':
        """딕셔너리에서 NovelTask 복원"""
        return cls(
            original_path=Path(data['original_path']),
            current_path=Path(data['current_path']),
            raw_name=data['raw_name'],
            title=data.get('title', ''),
            author=data.get('author', ''),
            genre=data.get('genre', ''),
            volume_info=data.get('volume_info', ''),
            range_info=data.get('range_info', ''),
            is_completed=data.get('is_completed', False),
            side_story=data.get('side_story', ''),
            edition_info=data.get('edition_info', ''),
            status=data.get('status', 'pending'),
            confidence=data.get('confidence', 'none'),
            source=data.get('source', ''),
            error_message=data.get('error_message', ''),
            metadata=data.get('metadata', {})
        )
    
    def to_json(self) -> str:
        """JSON 문자열로 직렬화"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'NovelTask':
        """JSON 문자열에서 NovelTask 복원"""
        data = json.loads(json_str)
        return cls.from_dict(data)
