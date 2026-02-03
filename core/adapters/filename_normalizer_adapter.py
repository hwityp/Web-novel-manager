"""
FilenameNormalizer Adapter

기존 정규화 로직을 파이프라인에 맞게 래핑합니다.
normalize(task: NovelTask) 메서드로 파일명을 정규화하고 NovelTask를 반환합니다.

표준 파일명 형식:
    [장르] 제목 부정보 범위 (완) + 외전.확장자

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""
import re
from pathlib import Path
from typing import Optional, List

from core.novel_task import NovelTask
from core.pipeline_logger import PipelineLogger
from core.title_anchor_extractor import TitleAnchorExtractor
from config.pipeline_config import PipelineConfig, GENRE_WHITELIST


# 유니코드 공백 문자 패턴
UNICODE_SPACES = re.compile(r'[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]+')


class FilenameNormalizerAdapter:
    """기존 정규화 로직을 파이프라인에 맞게 래핑"""
    
    def __init__(self, config: PipelineConfig, logger: Optional[PipelineLogger] = None):
        """
        Args:
            config: 파이프라인 설정
            logger: 파이프라인 로거 (없으면 기본 로거 생성)
        """
        self.config = config
        self.logger = logger or PipelineLogger(console_output=False)
        self._extractor = TitleAnchorExtractor()
    
    def parse_only(self, task: NovelTask) -> NovelTask:
        """
        파일명에서 메타데이터만 추출 (정규화 전 단계)
        
        Args:
            task: 처리할 NovelTask
            
        Returns:
            메타데이터(title, author 등)가 채워진 NovelTask
        """
        try:
            # 제목 앵커 추출 (이미 title이 있으면 건너뜀)
            if not task.title:
                parse_result = self._extractor.extract(task.raw_name)
                task.title = parse_result.title
                task.author = parse_result.author or task.author
                task.volume_info = parse_result.volume_info or task.volume_info
                task.range_info = parse_result.range_info or task.range_info
                task.is_completed = parse_result.is_completed or task.is_completed
                task.side_story = parse_result.side_story or task.side_story
                
                # [Fix] 원본 장르 보존
                if not task.genre and parse_result.original_genre:
                    task.genre = parse_result.original_genre
                    
                self.logger.debug(f"메타데이터 추출 완료: {task.raw_name} -> {task.title}")
        except Exception as e:
            self.logger.warning(f"메타데이터 추출 실패: {e}")
            
        return task
    
    def normalize(self, task: NovelTask) -> NovelTask:
        """
        파일명 정규화 후 task 업데이트
        
        Args:
            task: 정규화할 NovelTask
            
        Returns:
            정규화된 파일명이 업데이트된 NovelTask
        """
        try:
            # 1. 제목 앵커 추출 (title이 비어있으면)
            if not task.title:
                parse_result = self._extractor.extract(task.raw_name)
                task.title = parse_result.title
                task.author = parse_result.author or task.author
                task.volume_info = parse_result.volume_info or task.volume_info
                task.range_info = parse_result.range_info or task.range_info
                task.is_completed = parse_result.is_completed or task.is_completed
                task.side_story = parse_result.side_story or task.side_story
                
                # [Fix] 원본 장르 보존 (정규화 시점에서도 적용)
                if not task.genre and parse_result.original_genre:
                    task.genre = parse_result.original_genre
            
            # 2. 장르 화이트리스트 검증
            genre = self._validate_genre(task.genre)
            
            # 3. 표준 파일명 생성
            normalized_name = self._build_normalized_name(
                genre=genre,
                title=task.title or task.raw_name,
                volume_info=task.volume_info,
                range_info=task.range_info,
                is_completed=task.is_completed,
                side_story=task.side_story
            )
            
            # 4. 확장자 추가
            extension = task.current_path.suffix if task.current_path else '.txt'
            normalized_name = normalized_name + extension
            
            # 5. 타겟 경로 생성 및 충돌 처리
            target_folder = self._get_target_folder(task)
            target_path = target_folder / normalized_name
            target_path = self._handle_collision(target_path)
            
            # 6. task 업데이트
            task.metadata['normalized_name'] = target_path.name
            task.metadata['target_path'] = str(target_path)
            task.genre = genre
            task.status = 'completed'
            
            self.logger.debug(f"파일명 정규화 완료: {task.raw_name} → {target_path.name}")
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = f"정규화 실패: {str(e)}"
            self.logger.error(f"파일명 정규화 실패: {task.raw_name} - {e}")
        
        return task

    def preview_normalized_name(self, task: NovelTask) -> str:
        """
        정규화된 파일명 미리보기 (dry-run용)
        
        Args:
            task: NovelTask
            
        Returns:
            정규화된 파일명 문자열
        """
        # 제목 앵커 추출
        if not task.title:
            parse_result = self._extractor.extract(task.raw_name)
            title = parse_result.title
            volume_info = parse_result.volume_info
            range_info = parse_result.range_info
            is_completed = parse_result.is_completed
            side_story = parse_result.side_story
            original_genre = parse_result.original_genre # [Fix]
        else:
            title = task.title
            volume_info = task.volume_info
            range_info = task.range_info
            is_completed = task.is_completed
            side_story = task.side_story
            original_genre = ""
        
        # 장르 결정 (task.genre 우선, 없으면 원본 장르 사용)
        genre_candidate = task.genre or original_genre
        genre = self._validate_genre(genre_candidate)
        
        normalized = self._build_normalized_name(
            genre=genre,
            title=title or task.raw_name,
            volume_info=volume_info,
            range_info=range_info,
            is_completed=is_completed,
            side_story=side_story
        )
        
        extension = task.current_path.suffix if task.current_path else '.txt'
        return normalized + extension
    
    def _validate_genre(self, genre: str) -> str:
        """
        장르 화이트리스트 검증 (Requirement 5.2)
        
        Args:
            genre: 검증할 장르
            
        Returns:
            유효한 장르 (화이트리스트에 없으면 '미분류')
        """
        if not genre or genre not in GENRE_WHITELIST:
            return '미분류'
        return genre
    
    def _build_normalized_name(
        self,
        genre: str,
        title: str,
        volume_info: str = "",
        range_info: str = "",
        is_completed: bool = False,
        side_story: str = ""
    ) -> str:
        """
        표준 형식 파일명 생성 (Requirement 5.1, 5.5)
        
        형식: [장르] 제목 부정보 범위 (완) + 외전
        
        Args:
            genre: 장르
            title: 제목
            volume_info: 권/부 정보
            range_info: 범위 정보
            is_completed: 완결 여부
            side_story: 외전 정보
            
        Returns:
            정규화된 파일명 (확장자 제외)
        """
        parts = []
        
        # 1. 장르 태그
        if genre and genre != '미분류':
            parts.append(f"[{genre}]")
        
        # 2. 제목 (공백 정규화)
        clean_title = self._normalize_spaces(title)
        parts.append(clean_title)
        
        # 3. 부 정보 (범위 앞에 위치)
        if volume_info:
            clean_volume = self._normalize_spaces(volume_info)
            parts.append(clean_volume)
        
        # 4. 범위 정보
        if range_info:
            clean_range = self._normalize_spaces(range_info)
            parts.append(clean_range)
        
        # 5. 완결 마커
        if is_completed:
            parts.append("(완)")
        
        # 6. 외전 정보
        if side_story:
            clean_side = self._normalize_spaces(side_story)
            parts.append(f"+ {clean_side}")
        
        # 조합 및 최종 정규화
        result = " ".join(parts)
        result = self._normalize_spaces(result)
        
        return result
    
    def _normalize_spaces(self, text: str) -> str:
        """
        유니코드 공백 정규화 (Requirement 5.3)
        
        Args:
            text: 정규화할 텍스트
            
        Returns:
            공백이 정규화된 텍스트
        """
        if not text:
            return ""
        
        # 유니코드 특수 공백을 일반 공백으로 변환
        text = UNICODE_SPACES.sub(' ', text)
        
        # 연속 공백을 하나로 압축
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _get_target_folder(self, task: NovelTask) -> Path:
        """
        타겟 폴더 경로 결정
        
        Args:
            task: NovelTask
            
        Returns:
            타겟 폴더 Path
        """
        if self.config.target_folder:
            # 설정에 타겟 폴더가 지정된 경우
            base_path = task.current_path.parent if task.current_path else Path('.')
            return base_path / self.config.target_folder
        else:
            # 원본 파일과 같은 폴더
            return task.current_path.parent if task.current_path else Path('.')
    
    def _handle_collision(self, target_path: Path) -> Path:
        """
        파일명 충돌 처리 (Requirement 5.6)
        
        Args:
            target_path: 원래 타겟 경로
            
        Returns:
            충돌이 해결된 경로 (필요시 숫자 접미사 추가)
        """
        if not target_path.exists():
            return target_path
        
        # 파일명과 확장자 분리
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        
        # 숫자 접미사 추가
        counter = 1
        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                self.logger.debug(f"파일명 충돌 해결: {target_path.name} → {new_name}")
                return new_path
            counter += 1
            
            # 무한 루프 방지
            if counter > 1000:
                raise RuntimeError(f"파일명 충돌 해결 실패: {target_path}")
    
    def normalize_batch(self, tasks: List[NovelTask]) -> List[NovelTask]:
        """
        여러 태스크 일괄 정규화
        
        Args:
            tasks: 정규화할 NovelTask 목록
            
        Returns:
            정규화된 NovelTask 목록
        """
        return [self.normalize(task) for task in tasks]
    

