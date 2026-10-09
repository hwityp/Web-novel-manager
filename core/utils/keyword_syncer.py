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

    def load_master_data(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """기본 사전 파일 로드"""
        primary_path = self.target_paths[0]
        if not primary_path.exists():
            return None, f"기본 사전 파일이 존재하지 않습니다: {primary_path}"
        try:
            with open(primary_path, 'r', encoding='utf-8') as f:
                return json.load(f), None
        except Exception as e:
            return None, f"사전 파싱 실패: {e}"

    def get_keywords(self, genre: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        사전 내 등록된 키워드 목록 조회 (장르 필터 및 검색 지원)
        
        Returns:
            List[Dict[str, Any]]: [{"keyword": ..., "genre": ..., "weight": ...}, ...]
        """
        master_data, err = self.load_master_data()
        if not master_data or err:
            return []

        single_keywords = master_data.get("single_keywords", {})
        results: List[Dict[str, Any]] = []

        search_lower = search.strip().lower() if search else None

        for g, kw_dict in single_keywords.items():
            if genre and genre != "전체" and g != genre:
                continue
            for kw, weight in kw_dict.items():
                if search_lower and (search_lower not in kw.lower() and search_lower not in g.lower()):
                    continue
                results.append({
                    "keyword": kw,
                    "genre": g,
                    "weight": int(weight)
                })

        # 키워드명 기준 오름차순 정렬
        results.sort(key=lambda x: (x["genre"], x["keyword"]))
        return results

    def add_or_update_keyword(
        self,
        keyword: str,
        genre: str,
        weight: int,
        run_regression_test: bool = False
    ) -> SyncResult:
        """
        단일 키워드 등록 또는 가중치 수정
        """
        kw = keyword.strip()
        genre = genre.strip()
        if not kw:
            return SyncResult(False, 0, 0, 0, [], [], error_message="키워드가 비어 있습니다.")
        if not genre:
            return SyncResult(False, 0, 0, 0, [], [], error_message="장르를 지정해야 합니다.")

        weight = max(1, min(10, weight))

        master_data, err = self.load_master_data()
        if not master_data:
            return SyncResult(False, 0, 0, 0, [], [], error_message=err)

        backup_files = self.backup_files()
        single_keywords = master_data.setdefault("single_keywords", {})
        genre_dict = single_keywords.setdefault(genre, {})

        is_update = kw in genre_dict
        genre_dict[kw] = weight

        added_count = 0 if is_update else 1
        updated_count = 1 if is_update else 0

        master_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        master_data["version"] = self._bump_version(master_data.get("version", "1.6.0"))

        return self._save_and_sync(
            master_data=master_data,
            backup_files=backup_files,
            added_count=added_count,
            updated_count=updated_count,
            run_regression_test=run_regression_test
        )

    def delete_keyword(
        self,
        keyword: str,
        genre: str,
        run_regression_test: bool = False
    ) -> SyncResult:
        """
        단일 키워드 삭제
        """
        kw = keyword.strip()
        genre = genre.strip()
        master_data, err = self.load_master_data()
        if not master_data:
            return SyncResult(False, 0, 0, 0, [], [], error_message=err)

        single_keywords = master_data.get("single_keywords", {})
        if genre not in single_keywords or kw not in single_keywords[genre]:
            return SyncResult(False, 0, 0, 0, [], [], error_message=f"'{genre}' 장르에 '{kw}' 키워드가 존재하지 않습니다.")

        backup_files = self.backup_files()
        del single_keywords[genre][kw]

        master_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        master_data["version"] = self._bump_version(master_data.get("version", "1.6.0"))

        return self._save_and_sync(
            master_data=master_data,
            backup_files=backup_files,
            added_count=0,
            updated_count=0,
            run_regression_test=run_regression_test
        )

    def batch_delete_keywords(
        self,
        items: List[Tuple[str, str]],
        run_regression_test: bool = False
    ) -> SyncResult:
        """
        여러 키워드 일괄 삭제 (items: [(keyword, genre), ...])
        """
        if not items:
            return SyncResult(False, 0, 0, 0, [], [], error_message="삭제할 키워드가 선택되지 않았습니다.")

        master_data, err = self.load_master_data()
        if not master_data:
            return SyncResult(False, 0, 0, 0, [], [], error_message=err)

        backup_files = self.backup_files()
        single_keywords = master_data.get("single_keywords", {})
        deleted_count = 0

        for kw, genre in items:
            kw_clean = kw.strip()
            genre_clean = genre.strip()
            if genre_clean in single_keywords and kw_clean in single_keywords[genre_clean]:
                del single_keywords[genre_clean][kw_clean]
                deleted_count += 1

        if deleted_count == 0:
            return SyncResult(False, 0, 0, 0, [], [], error_message="삭제 대상 키워드를 사전에서 찾지 못했습니다.")

        master_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        master_data["version"] = self._bump_version(master_data.get("version", "1.6.0"))

        return self._save_and_sync(
            master_data=master_data,
            backup_files=backup_files,
            added_count=0,
            updated_count=0,
            run_regression_test=run_regression_test
        )

    def _save_and_sync(
        self,
        master_data: Dict[str, Any],
        backup_files: List[Path],
        added_count: int,
        updated_count: int,
        run_regression_test: bool
    ) -> SyncResult:
        """원자적 파일 저장 및 동기화 공통 처리"""
        single_keywords = master_data.get("single_keywords", {})
        total_keywords = sum(len(kw_dict) for kw_dict in single_keywords.values())
        target_file_strs = []

        try:
            for path in self.target_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = path.with_suffix(path.suffix + ".tmp")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(master_data, f, ensure_ascii=False, indent=2)
                os.replace(temp_path, path)
                target_file_strs.append(str(path))
        except Exception as e:
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

        test_passed = None
        if run_regression_test:
            test_passed = self.run_test_suite()
            if not test_passed:
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

        # 런타임 메모리 동기화
        self._reload_keyword_manager()

        return SyncResult(
            success=True,
            added_count=added_count,
            updated_count=updated_count,
            total_keywords=total_keywords,
            target_files=target_file_strs,
            backup_files=[str(b) for b in backup_files],
            test_passed=test_passed
        )

    def _reload_keyword_manager(self):
        """런타임 KeywordManager 인스턴스 갱신"""
        try:
            from modules.classifier.src.core.keyword_manager import KeywordManager
            if KeywordManager._instance is not None:
                KeywordManager._instance.load_keywords()
        except Exception:
            pass

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
        master_data, err = self.load_master_data()
        if not master_data:
            return SyncResult(
                success=False,
                added_count=0,
                updated_count=0,
                total_keywords=0,
                target_files=[],
                backup_files=[],
                error_message=err or "사전 로드 실패"
            )

        # 백업 생성
        backup_files = self.backup_files()

        # 키워드 병합 수행
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

        # 메타데이터 갱신
        master_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        master_data["version"] = self._bump_version(master_data.get("version", "1.6.0"))

        return self._save_and_sync(
            master_data=master_data,
            backup_files=backup_files,
            added_count=added_count,
            updated_count=updated_count,
            run_regression_test=run_regression_test
        )

    def _find_pytest_command(self) -> List[str]:
        """pytest 실행 명령어 탐색 (Windows 및 가상환경 안정적 대응)"""
        pytest_exe = shutil.which("pytest")
        if pytest_exe:
            return [pytest_exe]
        py_exe = shutil.which("py")
        if py_exe:
            return [py_exe, "-3.13", "-m", "pytest"]
        return [sys.executable, "-m", "pytest"]

    def run_test_suite(self) -> bool:
        """회귀 테스트 실행"""
        try:
            cmd = self._find_pytest_command() + [
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

