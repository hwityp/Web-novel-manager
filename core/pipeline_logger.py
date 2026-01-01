"""
PipelineLogger 로깅 모듈

파이프라인 실행 중 발생하는 모든 이벤트를 기록합니다.
콘솔과 파일 출력을 동시에 지원하며, 로그 파일 로테이션을 제공합니다.

Validates: Requirements 9.1, 9.3, 9.4, 9.5
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


# 로그 파일 기본 설정
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_LOG_FILENAME = "wnap.log"  # 변경: pipeline.log -> wnap.log
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5


class PipelineLogger:
    """파이프라인 전용 로거 클래스"""
    
    def __init__(
        self,
        log_level: str = "INFO",
        log_dir: Optional[Path] = None,
        log_filename: str = DEFAULT_LOG_FILENAME,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        console_output: bool = True
    ):
        """
        PipelineLogger 초기화
        
        Args:
            log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
            log_dir: 로그 파일 저장 디렉토리
            log_filename: 로그 파일명
            max_bytes: 로그 파일 최대 크기 (기본 10MB)
            backup_count: 백업 파일 개수
            console_output: 콘솔 출력 여부
        """
        self.log_level = self._validate_log_level(log_level)
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        
        # 1. Summary Log (wnap.log) - Fixed name
        self.summary_log_filename = DEFAULT_LOG_FILENAME
        
        # 2. Detail Log (wnap_YYYYMMDD.log) - Daily rotation
        if log_filename == DEFAULT_LOG_FILENAME:
            date_str = datetime.now().strftime("%Y%m%d")
            self.detail_log_filename = f"wnap_{date_str}.log"
        else:
            self.detail_log_filename = log_filename
            
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.console_output = console_output
        
        # 로거 설정
        self._logger = self._setup_logger()
    
    def _validate_log_level(self, level: str) -> str:
        """로그 레벨 유효성 검증"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        level_upper = level.upper()
        return level_upper if level_upper in valid_levels else "INFO"
    
    def _get_log_level_int(self) -> int:
        """문자열 로그 레벨을 logging 모듈 상수로 변환"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        return level_map.get(self.log_level, logging.INFO)
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정 및 핸들러 추가"""
        # 고유한 로거 이름 생성 (테스트 시 충돌 방지)
        logger_name = f"pipeline_{id(self)}"
        logger = logging.getLogger(logger_name)
        # 로거 레벨을 DEBUG로 설정하여 모든 로그가 핸들러에 도달하도록 함
        # 각 핸들러가 자신의 레벨에 맞게 필터링
        logger.setLevel(logging.DEBUG)
        
        # 로그 포맷 설정
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # 1. Summary File Handler (INFO 고정)
        self._add_file_handler(logger, formatter, self.summary_log_filename, logging.INFO)
        
        # 2. Detail File Handler (DEBUG 고정 - 터미널 출력 포함)
        # 사용자 설정보다 더 상세한 내용을 기록하기 위해 항상 DEBUG로 설정
        self._add_file_handler(logger, formatter, self.detail_log_filename, logging.DEBUG)
        
        # 콘솔 핸들러 설정 (사용자 설정 레벨 따름)
        if self.console_output:
            self._setup_console_handler(logger, formatter)
        
        return logger
    
    def _add_file_handler(self, logger: logging.Logger, formatter: logging.Formatter, filename: str, level: int):
        """파일 핸들러 추가 (공통 메서드)"""
        # 로그 디렉토리 생성
        self.log_dir = Path(self.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        log_path = self.log_dir / filename
        
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    def _setup_console_handler(self, logger: logging.Logger, formatter: logging.Formatter):
        """콘솔 핸들러 설정"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._get_log_level_int())
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    @property
    def log_file_path(self) -> Path:
        """현재 로그 파일 경로 반환"""
        return self.log_dir / self.detail_log_filename
    
    def debug(self, message: str):
        """DEBUG 레벨 로그"""
        self._logger.debug(message)
    
    def info(self, message: str):
        """INFO 레벨 로그"""
        self._logger.info(message)
    
    def warning(self, message: str):
        """WARNING 레벨 로그"""
        self._logger.warning(message)
    
    def error(self, message: str, exc_info: bool = True):
        """
        ERROR 레벨 로그
        
        Args:
            message: 에러 메시지
            exc_info: 예외 발생 시 스택 트레이스 포함 여부 (기본 True)
        """
        # 현재 예외 컨텍스트가 있으면 스택 트레이스 포함
        self._logger.error(message, exc_info=exc_info and sys.exc_info()[0] is not None)
    
    def exception(self, message: str):
        """예외 발생 시 스택 트레이스와 함께 ERROR 로그"""
        self._logger.exception(message)
    
    def log_task_start(self, task_name: str, file_path: str):
        """태스크 시작 로그"""
        self.info(f"[START] {task_name}: {file_path}")
    
    def log_task_complete(self, task_name: str, file_path: str):
        """태스크 완료 로그"""
        self.info(f"[COMPLETE] {task_name}: {file_path}")
    
    def log_task_skip(self, task_name: str, file_path: str, reason: str):
        """태스크 스킵 로그"""
        self.warning(f"[SKIP] {task_name}: {file_path} - {reason}")
    
    def log_task_error(self, task_name: str, file_path: str, error: Exception):
        """태스크 에러 로그 (스택 트레이스 포함)"""
        self.error(f"[ERROR] {task_name}: {file_path} - {type(error).__name__}: {error}")
    
    def log_pipeline_start(self, source_folder: str, total_files: int):
        """파이프라인 시작 로그"""
        self.info(f"{'='*60}")
        self.info(f"Pipeline started: {source_folder}")
        self.info(f"Total files to process: {total_files}")
        self.info(f"{'='*60}")
    
    def log_pipeline_complete(self, processed: int, failed: int, skipped: int):
        """파이프라인 완료 로그"""
        self.info(f"{'='*60}")
        self.info(f"Pipeline completed")
        self.info(f"  Processed: {processed}")
        self.info(f"  Failed: {failed}")
        self.info(f"  Skipped: {skipped}")
        self.info(f"{'='*60}")
    
    def close(self):
        """로거 핸들러 정리"""
        for handler in self._logger.handlers[:]:
            handler.close()
            self._logger.removeHandler(handler)


def get_logger(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    console_output: bool = True
) -> PipelineLogger:
    """PipelineLogger 인스턴스 생성 헬퍼 함수"""
    return PipelineLogger(
        log_level=log_level,
        log_dir=log_dir,
        console_output=console_output
    )
