"""
==============================================================================
파일: core/utils/keyword_syncer.py
역할 및 목적:
    두 개의 장르 키워드 JSON 파일(`modules/classifier/genre_keywords.json` 및
    `modules/classifier/src/data/genre_keywords.json`)의 동기화, 백업, 롤백 및
    신규 마이닝 키워드 병합을 원자적(Atomic)으로 처리하는 동기화 관리 모듈.
주요 구성 요소:
    - SyncResult: 동기화 결과 데이터클래스
    - KeywordSyncer: 이중 JSON 파일 원자적 동기화 및 무결성 관리 엔진
==============================================================================
"""
import os
import sys
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from core.utils.genre_cache_miner import GenreCandidate


@dataclass
class SyncResult:
    """동기화 작업 결과"""
    success: bool
    added_count: int
    updated_count: int
    total_keywords: int
    target_files: List[str]
    backup_files: List[str]
    test_passed: Optional[bool] = None
    error_message: Optional[str] = None


class KeywordSyncer:
    """장르 키워드 사전 원자적 동기화기"""

    DEFAULT_TARGET_PATHS = [
        Path("modules/classifier/genre_keywords.json"),
        Path("modules/classifier/src/data/genre_keywords.json"),
    ]

    def __init__(self, target_paths: Optional[List[Path]] = None):
        self.target_paths = target_paths or self.DEFAULT_TARGET_PATHS

    def get_statistics(self, target_path: Optional[Path] = None) -> Dict[str, Any]:
        """사전의 장르별 키워드 통계 조회"""
        path = target_path or self.target_paths[0]
        if not path.exists():
            return {"total": 0, "genres": {}, "version": "unknown", "last_updated": "unknown"}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            single_keywords = data.get("single_keywords", {})
            genre_counts = {genre: len(kw_dict) for genre, kw_dict in single_keywords.items()}
            total = sum(genre_counts.values())

            return {
                "total": total,
                "genres": genre_counts,
                "version": data.get("version", "1.0.0"),
                "last_updated": data.get("last_updated", "unknown"),
                "description": data.get("description", "")
            }
        except Exception as e:
            return {"total": 0, "genres": {}, "error": str(e)}

    def backup_files(self) -> List[Path]:
        """대상 파일들을 .bak 확장자로 백업"""
        backups = []
        for path in self.target_paths:
            if path.exists():
                bak_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, bak_path)
                backups.append(bak_path)
        return backups

    def restore_backups(self) -> bool:
        """백업 파일로부터 복원 (롤백)"""
        success = True
        for path in self.target_paths:
            bak_path = path.with_suffix(path.suffix + ".bak")
            if bak_path.exists():
                try:
                    shutil.copy2(bak_path, path)
                except Exception as e:
                    print(f"[KeywordSyncer] 롤백 실패 ({path}): {e}")
                    success = False
        return success

    def _bump_version(self, version_str: str) -> str:
        """시맨틱 버전 마이너/패치 넘버 증가 (예: 1.6.0 -> 1.6.1)"""
        parts = version_str.split('.')
        if len(parts) == 3 and parts[-1].isdigit():
            parts[-1] = str(int(parts[-1]) + 1)
            return '.'.join(parts)
        return version_str + ".1"

    def merge_and_sync(
        self,
        candidates: List[GenreCandidate],
        run_regression_test: bool = True,
        max_weight_cap: int = 8
    ) -> SyncResult:
        """
        후보군 키워드를 통합 사전에 병합하고 모든 대상 파일에 원자적으로 동기화.
        
        Args:
            candidates: 병합할 후보 키워드 목록
            run_regression_test: 동기화 후 pytest 단위 테스트 실행 여부
            max_weight_cap: 신규 키워드 가중치 상한선 (기본 8)
        """
        # 1. 원본 파일 유효성 확인
        primary_path = self.target_paths[0]
        if not primary_path.exists():
            return SyncResult(
                success=False,
                added_count=0,
                updated_count=0,
                total_keywords=0,
                target_files=[],
                backup_files=[],
                error_message=f"기본 사전 파일이 존재하지 않습니다: {primary_path}"
            )

        try:
            with open(primary_path, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
        except Exception as e:
            return SyncResult(
                success=False,
                added_count=0,
                updated_count=0,
                total_keywords=0,
                target_files=[],
                backup_files=[],
                error_message=f"사전 파싱 실패: {e}"
            )

        # 2. 백업 생성
        backup_files = self.backup_files()

        # 3. 키워드 병합 수행
        single_keywords = master_data.setdefault("single_keywords", {})
        added_count = 0
        updated_count = 0

        for cand in candidates:
            genre = cand.genre
            if genre not in single_keywords:
                single_keywords[genre] = {}

            weight = min(cand.suggested_weight, max_weight_cap)
            existing_weight = single_keywords[genre].get(cand.keyword)

            if existing_weight is None:
                single_keywords[genre][cand.keyword] = weight
                added_count += 1
            elif weight > existing_weight:
                single_keywords[genre][cand.keyword] = weight
                updated_count += 1

        # 4. 메타데이터 갱신
        master_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        master_data["version"] = self._bump_version(master_data.get("version", "1.6.0"))

        total_keywords = sum(len(kw_dict) for kw_dict in single_keywords.values())

        # 5. 모든 대상 파일에 원자적 쓰기 (Atomic write via temp file)
        target_file_strs = []
        try:
            for path in self.target_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = path.with_suffix(path.suffix + ".tmp")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(master_data, f, ensure_ascii=False, indent=2)
                # 원자적 교체
                os.replace(temp_path, path)
                target_file_strs.append(str(path))
        except Exception as e:
            # 쓰기 실패 시 즉시 롤백
            self.restore_backups()
            return SyncResult(
                success=False,
                added_count=0,
                updated_count=0,
                total_keywords=0,
                target_files=[],
                backup_files=[str(b) for b in backup_files],
                error_message=f"원자적 파일 쓰기 실패, 롤백되었습니다: {e}"
            )

        # 6. 회귀 테스트 실행 (선택적)
        test_passed = None
        if run_regression_test:
            test_passed = self.run_test_suite()
            if not test_passed:
                # 테스트 실패 시 롤백 수행
                self.restore_backups()
                return SyncResult(
                    success=False,
                    added_count=added_count,
                    updated_count=updated_count,
                    total_keywords=total_keywords,
                    target_files=target_file_strs,
                    backup_files=[str(b) for b in backup_files],
                    test_passed=False,
                    error_message="회귀 단위 테스트 실패로 인해 안전하게 롤백되었습니다."
                )

        return SyncResult(
            success=True,
            added_count=added_count,
            updated_count=updated_count,
            total_keywords=total_keywords,
            target_files=target_file_strs,
            backup_files=[str(b) for b in backup_files],
            test_passed=test_passed
        )

    def run_test_suite(self) -> bool:
        """회귀 테스트 실행"""
        try:
            # venv python 탐색
            python_bin = sys.executable
            cmd = [
                python_bin, "-m", "pytest",
                "tests/test_chinese_phonetic_analyzer.py",
                "-q"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            print(f"[KeywordSyncer] 테스트 실행 중 오류: {e}")
            return False
