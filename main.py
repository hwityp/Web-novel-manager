#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
파일: main.py
역할 및 목적:
    Web Novel Archive Pipeline (WNAP) Manager 애플리케이션의 최상위 진입점(Entrypoint).
    인자가 주어지지 않거나 --gui 플래그 전달 시 Tkinter 기반 통합 GUI(MainWindow)를 실행하고,
    -s / --source 인자 전달 시 백그라운드 배치 처리를 위한 CLI 파이프라인 모드를 구동합니다.
주요 구성 요소:
    - main(): 커맨드라인 인자 파싱 및 GUI/CLI 실행 분기
    - run_cli(): PipelineOrchestrator를 통한 터미널 기반 파이프라인 실행
    - _setup_paths(): PyInstaller 패키징(EXE) 및 개발 환경에 따른 sys.path 및 작업 디렉토리 보정
상호 연관 관계 및 의존성:
    - Caller: 사용자가 직접 실행 (python main.py, WNAP_Manager.exe)
    - Callee: gui.main_window.MainWindow, core.pipeline_orchestrator.PipelineOrchestrator,
              core.pipeline_logger.PipelineLogger, core.version
수정 시 주의사항:
    - PyInstaller 번들링 시 frozen 환경(_MEIPASS)과 스크립트 실행 환경의 경로 호환성을 유지해야 합니다.
    - 환경 변수(.env) 로드는 모듈 import 이전에 수행되어야 API 키가 정상 주입됩니다.
==============================================================================
"""
import sys
import os
from dotenv import load_dotenv

# 환경 변수 로드 (API 키 등)
load_dotenv(override=True)

# 프로젝트 루트를 sys.path에 추가 (절대 import 지원)
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ============================================================================
# PyInstaller 경로 보정 (EXE 실행 환경 지원)
# ============================================================================
def _setup_paths():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        application_path = os.path.dirname(sys.executable)
        os.chdir(application_path)
    else:
        base_path = _project_root
        application_path = base_path

    if base_path not in sys.path:
        sys.path.insert(0, base_path)

    return base_path, application_path

_BASE_PATH, _APP_PATH = _setup_paths()


# ============================================================================
# GUI 모드
# ============================================================================
def run_gui(log_level: str = 'INFO'):
    """GUI 애플리케이션 실행"""
    from gui.main_window import WNAPMainWindow
    app = WNAPMainWindow(log_level=log_level)
    app.mainloop()


# ============================================================================
# CLI 모드
# ============================================================================
import argparse
from pathlib import Path
from typing import Optional

from core.version import __version__, get_full_version
from core.pipeline_orchestrator import PipelineOrchestrator, PipelineResult
from core.pipeline_logger import PipelineLogger
from config.pipeline_config import PipelineConfig


def create_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        prog='wnap',
        description=f'Web Novel Archive Pipeline v{__version__} - 웹소설 아카이브 자동 정리 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s                              # GUI 모드 (인자 없음)
  %(prog)s --gui                        # GUI 모드 명시
  %(prog)s -s ./novels                  # CLI dry-run 미리보기
  %(prog)s -s ./novels --no-dry-run     # CLI 실제 실행
  %(prog)s -s ./novels -t ./정리완료 -y  # 확인 없이 실행
        """
    )

    # GUI 모드 플래그
    parser.add_argument(
        '--gui',
        action='store_true',
        help='GUI 모드 실행 (인자 없이 실행할 때와 동일)'
    )

    # CLI 소스 폴더 (없으면 GUI 모드)
    parser.add_argument(
        '-s', '--source',
        type=str,
        default=None,
        help='정리할 소스 폴더 경로 (지정 시 CLI 파이프라인 모드)'
    )

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
    if not source_path.exists():
        print(f"\n❌ 오류: 소스 폴더가 존재하지 않습니다: {source_path}")
        return False
    if not source_path.is_dir():
        print(f"\n❌ 오류: 지정된 경로가 폴더가 아닙니다: {source_path}")
        return False
    return True


def print_settings_summary(source_folder: Path, target_folder: str, dry_run: bool, log_level: str):
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
    prompt = "\n미리보기를 실행하시겠습니까? [Y/n]: " if dry_run else \
             "\n⚠️  실제 파일이 변경됩니다. 계속하시겠습니까? [y/N]: "
    try:
        response = input(prompt).strip().lower()
        return response != 'n' if dry_run else response in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        print("\n\n취소되었습니다.")
        return False


def print_final_summary(result: PipelineResult, dry_run: bool):
    mode = "미리보기" if dry_run else "실행"
    print("\n\n" + "=" * 60)
    print(f"✅ 파이프라인 {mode} 완료")
    print("=" * 60)
    print(f"\n📊 처리 결과:")
    print(f"   총 파일 수:  {result.total_files}")
    print(f"   ✓ 성공:      {result.processed}")
    print(f"   ✗ 실패:      {result.failed}")
    print(f"   ⊘ 건너뜀:    {result.skipped}")
    if result.total_files > 0:
        success_rate = (result.processed / result.total_files) * 100
        print(f"\n   성공률: {success_rate:.1f}%")
    if result.mapping_csv_path:
        print(f"\n📄 매핑 파일: {result.mapping_csv_path}")
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
    if config_path:
        config = PipelineConfig.load(Path(config_path))
    else:
        config = PipelineConfig()

    config.source_folder = str(source_folder)
    config.target_folder = target_folder
    config.log_level = log_level
    config.dry_run = dry_run

    logger = PipelineLogger(log_level=log_level, console_output=False)
    orchestrator = PipelineOrchestrator(config, logger)

    print("\n🚀 파이프라인 시작...\n")
    return orchestrator.run(source_folder, dry_run=dry_run)


# ============================================================================
# 메인 진입점
# ============================================================================
def main():
    parser = create_parser()
    args = parser.parse_args()

    # GUI 모드: 인자가 없거나 --gui 플래그가 있으면
    if args.source is None or args.gui:
        run_gui(log_level=args.log_level)
        return

    # CLI 모드: -s 소스 폴더가 지정된 경우
    source_folder = Path(args.source).resolve()
    if not validate_source_folder(source_folder):
        sys.exit(1)

    dry_run = not args.no_dry_run
    target_folder = args.target if args.target else str(source_folder / "정리완료")

    print_settings_summary(
        source_folder=source_folder,
        target_folder=target_folder,
        dry_run=dry_run,
        log_level=args.log_level
    )

    if not args.yes:
        if not confirm_execution(dry_run):
            print("\n취소되었습니다.")
            sys.exit(0)

    try:
        result = run_pipeline(
            source_folder=source_folder,
            target_folder=target_folder,
            dry_run=dry_run,
            log_level=args.log_level,
            config_path=args.config
        )
        print_final_summary(result, dry_run)
        sys.exit(1 if result.failed > 0 else 0)

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 치명적 오류: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
