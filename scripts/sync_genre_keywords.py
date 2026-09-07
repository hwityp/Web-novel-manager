"""
==============================================================================
파일: scripts/sync_genre_keywords.py
역할 및 목적:
    추출된 후보군(`modules/classifier/candidate_keywords.json`)을 검증하고,
    두 개의 통합 장르 키워드 JSON 파일에 원자적으로 병합 및 동기화하는 CLI 스크립트.
    선택적으로 동기화 직후 단위/회귀 테스트를 자동 수행하여 안전성을 검증.
사용 예시:
    python scripts/sync_genre_keywords.py
    python scripts/sync_genre_keywords.py --no-test
==============================================================================
"""
import sys
import json
import argparse
from pathlib import Path

# Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.utils.genre_cache_miner import GenreCandidate
from core.utils.keyword_syncer import KeywordSyncer


def main():
    parser = argparse.ArgumentParser(description="장르 키워드 사전 원자적 동기화 및 무결성 검증 도구")
    parser.add_argument("--candidates", type=str, default="modules/classifier/candidate_keywords.json", help="후보군 파일 경로")
    parser.add_argument("--no-test", action="store_true", help="회귀 테스트 실행 건너뛰기")
    parser.add_argument("--weight-cap", type=int, default=8, help="신규 키워드 가중치 상한선 (기본: 8)")
    args = parser.parse_args()

    cand_path = Path(args.candidates)
    if not cand_path.exists():
        print(f"[!] 후보군 파일이 없습니다: {cand_path}")
        print("    먼저 'python scripts/mine_genre_candidates.py'를 실행하세요.")
        sys.exit(1)

    try:
        with open(cand_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        candidate_dicts = data.get("candidates", [])
        candidates = [GenreCandidate(**item) for item in candidate_dicts]
    except Exception as e:
        print(f"[FAIL] 후보군 파일 읽기 실패: {e}")
        sys.exit(1)

    print(f"[*] 동기화 준비: {len(candidates)}개 후보 키워드")
    syncer = KeywordSyncer()
    
    # 동기화 전 통계
    stats_before = syncer.get_statistics()
    print(f"[*] 동기화 전 상태: 총 {stats_before.get('total')}개 키워드 (v{stats_before.get('version')})")

    # 병합 및 동기화 실행
    result = syncer.merge_and_sync(
        candidates=candidates,
        run_regression_test=not args.no_test,
        max_weight_cap=args.weight_cap
    )

    if result.success:
        print("\n" + "=" * 50)
        print(f"[OK] 동기화 성공!")
        print(f" - 추가된 키워드: {result.added_count}개")
        print(f" - 가중치 갱신 키워드: {result.updated_count}개")
        print(f" - 최종 총 키워드 수: {result.total_keywords}개")
        if result.test_passed is not None:
            status = "통과 (PASS)" if result.test_passed else "실패 (FAIL)"
            print(f" - 회귀 테스트: {status}")
        print(f" - 갱신된 파일들:")
        for tf in result.target_files:
            print(f"   • {tf}")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print(f"[FAIL] 동기화 실패: {result.error_message}")
        if result.backup_files:
            print(f" - 안전하게 롤백되었습니다. 백업 파일:")
            for bf in result.backup_files:
                print(f"   • {bf}")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
