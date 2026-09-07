"""
==============================================================================
파일: scripts/mine_genre_candidates.py
역할 및 목적:
    장르 캐시(`config/genre_cache.json`)를 스캔하여 신규 장르 키워드 및
    중국어 음독 패턴 후보를 추출하고, `modules/classifier/candidate_keywords.json`으로
    내보내는 CLI 스크립트.
사용 예시:
    python scripts/mine_genre_candidates.py
    python scripts/mine_genre_candidates.py --min-count 2 --min-purity 0.7
==============================================================================
"""
import sys
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

from core.utils.genre_cache_miner import GenreCacheMiner


def main():
    parser = argparse.ArgumentParser(description="장르 캐시 기반 신규 키워드/음독 패턴 마이닝 도구")
    parser.add_argument("--cache", type=str, default="config/genre_cache.json", help="캐시 파일 경로")
    parser.add_argument("--out", type=str, default="modules/classifier/candidate_keywords.json", help="후보군 저장 경로")
    parser.add_argument("--min-count", type=int, default=1, help="최소 출현 횟수")
    parser.add_argument("--min-purity", type=float, default=0.6, help="최소 장르 독점도 (0.0 ~ 1.0)")
    args = parser.parse_args()

    cache_path = Path(args.cache)
    out_path = Path(args.out)

    print(f"[*] 캐시 마이닝 시작: {cache_path}")
    miner = GenreCacheMiner(cache_file=cache_path)
    candidates = miner.mine(min_count=args.min_count, min_purity=args.min_purity)

    print(f"[+] 마이닝 완료: 총 {len(candidates)}개의 후보 키워드 도출")
    print("-" * 60)
    print(f"{'키워드':<15} | {'장르':<8} | {'빈도':<4} | {'순도':<6} | {'가중치':<4} | {'원문/유형'}")
    print("-" * 60)
    for c in candidates[:20]: # 상위 20개 출력
        cjk_info = f"({c.cjk_source})" if c.cjk_source else c.source_type
        print(f"{c.keyword:<15} | {c.genre:<8} | {c.count:<4} | {c.purity:<6.2f} | {c.suggested_weight:<4} | {cjk_info}")
    
    if len(candidates) > 20:
        print(f"... 외 {len(candidates) - 20}개 생략")
    print("-" * 60)

    success = miner.export_candidates(out_path, candidates)
    if success:
        print(f"[OK] 후보군 저장 완료: {out_path}")
    else:
        print(f"[FAIL] 후보군 저장 실패")


if __name__ == "__main__":
    main()
