"""
==============================================================================
파일: scripts/scheduled_keyword_update.py
역할 및 목적:
    정기 스케줄(주간 또는 월간)에 따라 자동으로 실행되어:
    1) 캐시(`config/genre_cache.json`) 마이닝
    2) 신규 음독/장르 키워드 후보군 추출
    3) 무결성 검증 및 회귀 테스트 가드 실행
    4) 이중 장르 키워드 JSON 원자적 동기화
    5) 결과 로그를 `logs/keyword_update.log`에 기록
    하는 자동화 배치 스크립트.
사용 예시:
    python scripts/scheduled_keyword_update.py
    python scripts/scheduled_keyword_update.py --min-purity 0.7
==============================================================================
"""
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.utils.genre_cache_miner import GenreCacheMiner
from core.utils.keyword_syncer import KeywordSyncer


def setup_logger(log_dir: Path) -> logging.Logger:
    """배치 전용 로거 설정"""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ScheduledKeywordUpdate")
    logger.setLevel(logging.INFO)

    log_file = log_dir / "keyword_update.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def main():
    parser = argparse.ArgumentParser(description="정기 배치용 키워드 사전 자동 업데이트 도구")
    parser.add_argument("--cache", type=str, default="config/genre_cache.json", help="캐시 파일 경로")
    parser.add_argument("--min-count", type=int, default=2, help="최소 출현 빈도 (배치는 기본 2회 이상으로 안전성 강화)")
    parser.add_argument("--min-purity", type=float, default=0.7, help="최소 장르 독점도 (배치는 기본 0.7 이상)")
    parser.add_argument("--no-test", action="store_true", help="회귀 테스트 건너뛰기")
    args = parser.parse_args()

    logger = setup_logger(Path("logs"))
    logger.info("=== 정기 키워드 사전 업데이트 배치 시작 ===")

    cache_path = Path(args.cache)
    if not cache_path.exists():
        logger.warning(f"캐시 파일이 존재하지 않아 배치를 종료합니다: {cache_path}")
        sys.exit(0)

    # 1. 마이닝
    miner = GenreCacheMiner(cache_file=cache_path)
    candidates = miner.mine(min_count=args.min_count, min_purity=args.min_purity)
    logger.info(f"캐시 마이닝 완료: 후보 키워드 {len(candidates)}개 발견")

    if not candidates:
        logger.info("새로 추가할 유의미한 후보 키워드가 없습니다. 배치를 종료합니다.")
        sys.exit(0)

    # 2. 후보군 저장
    cand_out = Path("modules/classifier/candidate_keywords.json")
    miner.export_candidates(cand_out, candidates)
    logger.info(f"후보군 파일 저장 완료: {cand_out}")

    # 3. 원자적 동기화 및 회귀 검증
    syncer = KeywordSyncer()
    result = syncer.merge_and_sync(
        candidates=candidates,
        run_regression_test=not args.no_test,
        max_weight_cap=8
    )

    if result.success:
        logger.info(
            f"동기화 성공! 추가: {result.added_count}개, 갱신: {result.updated_count}개, "
            f"총 키워드: {result.total_keywords}개, 테스트: {result.test_passed}"
        )
    else:
        logger.error(f"동기화 실패: {result.error_message}")
        sys.exit(1)

    logger.info("=== 정기 키워드 사전 업데이트 배치 정상 완료 ===")


if __name__ == "__main__":
    main()
