import os
import shutil
import time
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

import sys
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.novel_task import NovelTask
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter
from config.pipeline_config import PipelineConfig

# 상위 10개 복잡한 파일명 (analysis_output.txt 등에서 식별됨)
COMPLEX_FILES = [
    "[선협] 구성성인，선관소아양마(성인이 되었더니 선관이 말을 키우라 부르네) 1-1132 (완).txt",
    "[임아소] 신선이 되자, 자손들이 저에게 출산해달라 부탁합니다. (완).txt",
    "망왕지종호흡법개시 1-643 完 (AI번역) #패러디 #테니스의 왕자.txt",
    "초가류방 - 부황, 자공간유둔량 1-452 (완) + 외전.txt",
    "천성농가소복보, 도황로상개괘료 1-1214 (완) + 외전.txt",
    "500조 재벌가 천재아들 1-324본편 및 외전 完, 후기 포함.txt",
    "[선협] 어살 1-1014 完 (AI번역) @EE.txt",
    "만재폐체, 즘마취지수초만선료 1-2055 (AI번역).txt",
    "천재가 된 재벌가 사생아는 말단 사원으로 시작한다 1-328 完.txt",
    "검술과 궁술에 미친 자작가 이공자가 돈도 잘 범 1-218 完.txt"
]

def test_complex_files_integrity():
    """복잡한 파일명 정규화 및 메타데이터 보존 테스트"""
    
    with TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        source_dir = base_path / "source"
        target_dir = base_path / "target"
        source_dir.mkdir()
        
        print(f"\n[테스트 시작] 임시 디렉토리: {temp_dir}")
        print(f"{'='*80}")
        print(f"{'Original Filename':<60} | {'Normalized Filename':<60}")
        print(f"{'-'*120}")
        
        config = PipelineConfig()
        config.target_folder = "target" # 상대 경로 설정
        normalizer = FilenameNormalizerAdapter(config)
        
        created_files = []
        
        # 1. 파일 생성 및 메타데이터 설정
        for name in COMPLEX_FILES:
            file_path = source_dir / name
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("dummy content")
            
            # 수정 시간 설정 (과거 시간)
            past_time = time.time() - 10000
            os.utime(file_path, (past_time, past_time))
            created_files.append((file_path, past_time))
            
        # 2. 정규화 및 복사 테스트
        success_count = 0
        
        for file_path, original_mtime in created_files:
            # Task 생성
            task = NovelTask(
                original_path=file_path,
                current_path=file_path,
                raw_name=file_path.stem
            )
            
            # 정규화 수행
            task = normalizer.normalize(task)
            
            # 정규화 결과 출력
            normalized_name = task.metadata.get('normalized_name', 'FAILED')
            print(f"{file_path.name[:58]:<60} | {normalized_name[:60]:<60}")
            
            if task.status == 'failed':
                print(f"  [FAIL] Normalization failed: {task.error_message}")
                continue
                
            # 실제 파일 복사 시뮬레이션 (PipelineOrchestrator._move_file 로직)
            target_path = task.current_path.parent / task.metadata['target_path']
            
            # 타겟 경로가 절대경로가 아닌 경우 처리 (테스트 환경)
            if not Path(target_path).is_absolute():
                 target_path = file_path.parent / target_path
                 
            # PipelineOrchestrator 로직과 동일하게 디렉토리 생성 및 copy2 사용
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(file_path), str(target_path))
            
            # 3. 검증
            # A. 파일 존재 확인
            if not target_path.exists():
                print(f"  [FAIL] Target file not created: {target_path}")
                continue
                
            # B. 메타데이터(mtime) 확인
            target_mtime = target_path.stat().st_mtime
            
            # copy2는 mtime을 보존해야 함 (오차 범위 2초 허용)
            if abs(original_mtime - target_mtime) > 2.0:
                print(f"  [FAIL] Metadata mismatch! Orig: {original_mtime}, Target: {target_mtime}")
            else:
                success_count += 1
                
        print(f"{'='*80}")
        print(f"Total: {len(COMPLEX_FILES)}, Success: {success_count}")
        
        if success_count == len(COMPLEX_FILES):
            print("\n[SUCCESS] 모든 테스트 통과!")
        else:
            print("\n[FAILURE] 일부 테스트 실패")
            sys.exit(1)

if __name__ == "__main__":
    test_complex_files_integrity()
