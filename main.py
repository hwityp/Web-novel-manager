#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web Novel Archive Pipeline (WNAP) - CLI Entry Point

웹소설 아카이브 파일을 자동으로 정리하는 통합 파이프라인의 CLI 인터페이스입니다.

사용법:
    python main.py --source <소스폴더> [옵션]

예시:
    python main.py -s ./novels                    # dry-run 모드로 미리보기
    python main.py -s ./novels --no-dry-run      # 실제 실행
    python main.py -s ./novels -t ./정리완료 -y   # 확인 없이 실행

Validates: Requirements 8.1
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가 (절대 import 지원)
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
from pathlib import Path
from typing import Optional

from core.pipeline_orchestrator import PipelineOrchestrator, PipelineResult
from core.pipeline_logger import PipelineLogger
from core.version import __version__, get_full_version
from config.pipeline_config import PipelineConfig


def create_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        prog='wnap',
        description=f'Web Novel Archive Pipeline v{__version__} - 웹소설 아카이브 자동 정리 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s -s ./novels                    # dry-run 모드로 미리보기 (기본값)
  %(prog)s -s ./novels --no-dry-run       # 실제 파일 변경 실행
  %(prog)s -s ./novels -t ./정리완료 -y    # 확인 없이 실행
  %(prog)s -s ./novels --log-level DEBUG  # 디버그 로그 출력
        """
    )
    
    # 필수 인자
    parser.add_argument(
        '-s', '--source',
        type=str,
        required=True,
        help='정리할 소스 폴더 경로 (필수)'
    )
    
    # 선택 인자
    parser.add_argument(
        '-t', '--target',
        type=str,
        default=None,
        help='결과물이 저장될 타겟 폴더 경로 (기본값: 소스폴더/정리완료)'
    )
    
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        default=True,
        help='실제 파일 변경 없이 미리보기만 실행 (기본값: True)'
    )
    
    parser.add_argument(
        '--no-dry-run',
        action='store_true',
        help='실제 파일 변경 실행 (dry-run 비활성화)'
    )
    
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='실행 전 확인 절차 건너뛰기'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='로그 레벨 설정 (기본값: INFO)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='설정 파일 경로 (기본값: config/pipeline_config.json)'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=get_full_version(),
        help='버전 정보 출력'
    )
    
    return parser


def validate_source_folder(source_path: Path) -> bool:
    """소스 폴더 유효성 검증"""
    if not source_path.exists():
        print(f"\n❌ 오류: 소스 폴더가 존재하지 않습니다: {source_path}")
        return False
    
    if not source_path.is_dir():
        print(f"\n❌ 오류: 지정된 경로가 폴더가 아닙니다: {source_path}")
        return False
    
    return True


def print_settings_summary(
    source_folder: Path,
    target_folder: str,
    dry_run: bool,
    log_level: str
):
    """실행 설정 요약 출력"""
    mode_text = "🔍 미리보기 모드 (파일 변경 없음)" if dry_run else "⚡ 실행 모드 (파일 변경됨)"
    
    print("\n" + "=" * 60)
    print("📁 Web Novel Archive Pipeline (WNAP)")
    print("=" * 60)
    print(f"\n{mode_text}\n")
    print(f"  📂 소스 폴더: {source_folder}")
    print(f"  📂 타겟 폴더: {target_folder}")
    print(f"  📝 로그 레벨: {log_level}")
    print("\n" + "-" * 60)


def confirm_execution(dry_run: bool) -> bool:
    """실행 확인 프롬프트"""
    if dry_run:
        prompt = "\n미리보기를 실행하시겠습니까? [Y/n]: "
    else:
        prompt = "\n⚠️  실제 파일이 변경됩니다. 계속하시겠습니까? [y/N]: "
    
    try:
        response = input(prompt).strip().lower()
        
        if dry_run:
            # dry-run은 기본값이 Yes
            return response != 'n'
        else:
            # 실제 실행은 기본값이 No
            return response == 'y' or response == 'yes'
    except (EOFError, KeyboardInterrupt):
        print("\n\n취소되었습니다.")
        return False


def print_progress(current: int, total: int, filename: str):
    """진행 상황 출력"""
    percentage = (current / total * 100) if total > 0 else 0
    bar_length = 30
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = '█' * filled + '░' * (bar_length - filled)
    
    # 파일명이 너무 길면 자르기
    max_name_len = 40
    display_name = filename[:max_name_len] + '...' if len(filename) > max_name_len else filename
    
    print(f"\r[{bar}] {current}/{total} ({percentage:.1f}%) - {display_name}", end='', flush=True)


def print_final_summary(result: PipelineResult, dry_run: bool):
    """최종 결과 요약 출력"""
    mode = "미리보기" if dry_run else "실행"
    
    print("\n\n" + "=" * 60)
    print(f"✅ 파이프라인 {mode} 완료")
    print("=" * 60)
    
    # 통계
    print(f"\n📊 처리 결과:")
    print(f"   총 파일 수:  {result.total_files}")
    print(f"   ✓ 성공:      {result.processed}")
    print(f"   ✗ 실패:      {result.failed}")
    print(f"   ⊘ 건너뜀:    {result.skipped}")
    
    # 성공률
    if result.total_files > 0:
        success_rate = (result.processed / result.total_files) * 100
        print(f"\n   성공률: {success_rate:.1f}%")
    
    # 매핑 파일 위치
    if result.mapping_csv_path:
        print(f"\n📄 매핑 파일: {result.mapping_csv_path}")
    
    # 에러 목록 (최대 5개)
    if result.errors:
        print(f"\n⚠️  오류 목록 ({len(result.errors)}건):")
        for i, error in enumerate(result.errors[:5]):
            print(f"   {i+1}. {error}")
        if len(result.errors) > 5:
            print(f"   ... 외 {len(result.errors) - 5}건")
    
    print("\n" + "=" * 60)


def run_pipeline(
    source_folder: Path,
    target_folder: str,
    dry_run: bool,
    log_level: str,
    config_path: Optional[str] = None
) -> PipelineResult:
    """파이프라인 실행"""
    # 설정 로드
    if config_path:
        config = PipelineConfig.load(Path(config_path))
    else:
        config = PipelineConfig()
    
    # CLI 인자로 설정 오버라이드
    config.source_folder = str(source_folder)
    config.target_folder = target_folder
    config.log_level = log_level
    config.dry_run = dry_run
    
    # 로거 생성
    logger = PipelineLogger(
        log_level=log_level,
        console_output=False  # CLI에서는 별도로 진행 상황 출력
    )
    
    # 오케스트레이터 생성 및 실행
    orchestrator = PipelineOrchestrator(config, logger)
    
    print("\n🚀 파이프라인 시작...\n")
    
    result = orchestrator.run(source_folder, dry_run=dry_run)
    
    return result


def main():
    """메인 엔트리포인트"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 소스 폴더 검증
    source_folder = Path(args.source).resolve()
    if not validate_source_folder(source_folder):
        sys.exit(1)
    
    # dry-run 결정 (--no-dry-run이 있으면 False)
    dry_run = not args.no_dry_run
    
    # 타겟 폴더 결정
    target_folder = args.target if args.target else str(source_folder / "정리완료")
    
    # 설정 요약 출력
    print_settings_summary(
        source_folder=source_folder,
        target_folder=target_folder,
        dry_run=dry_run,
        log_level=args.log_level
    )
    
    # 확인 절차 (--yes가 없으면)
    if not args.yes:
        if not confirm_execution(dry_run):
            print("\n취소되었습니다.")
            sys.exit(0)
    
    try:
        # 파이프라인 실행
        result = run_pipeline(
            source_folder=source_folder,
            target_folder=target_folder,
            dry_run=dry_run,
            log_level=args.log_level,
            config_path=args.config
        )
        
        # 최종 결과 출력
        print_final_summary(result, dry_run)
        
        # 종료 코드 결정
        if result.failed > 0:
            sys.exit(1)  # 일부 실패
        sys.exit(0)  # 성공
        
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 치명적 오류: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
