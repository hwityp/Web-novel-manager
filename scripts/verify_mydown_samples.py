#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
파일: scripts/verify_mydown_samples.py
역할 및 목적:
    C:\\Users\\hwity\\문서\\MyDown 폴더에서 무작위 200개 파일을 추출하여
    소설 국적 판별(NovelOriginDetector), 본문 헤더 추출(ContentHeaderGenreExtractor),
    장르 분류(GenreClassifierAdapter), 파일명 정규화(FilenameNormalizerAdapter)의
    정확도와 동작 상태를 검증하고 상세 통계를 생성합니다.
==============================================================================
"""
import os
import sys
from pathlib import Path

# UTF-8 콘솔 출력 설정
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import random
from collections import Counter
from core.title_anchor_extractor import TitleAnchorExtractor
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter
from core.utils.novel_origin_detector import NovelOriginDetector
from core.utils.content_header_extractor import ContentHeaderGenreExtractor
from core.pipeline_orchestrator import PipelineConfig
from core.novel_task import NovelTask

def main():
    target_dir = Path(r"C:\Users\hwity\문서\MyDown")
    if not target_dir.exists():
        print(f"❌ 대상 디렉터리가 존재하지 않습니다: {target_dir}")
        return

    # 1. 파일 목록 수집
    all_files = [f for f in target_dir.iterdir() if f.is_file() and f.suffix.lower() == '.txt']
    print(f"📁 대상 디렉터리: {target_dir}")
    print(f"📄 전체 텍스트 파일 수: {len(all_files)}개")

    if len(all_files) == 0:
        print("❌ 텍스트 파일이 없습니다.")
        return

    sample_size = min(200, len(all_files))
    # 재현성을 위한 시드 고정
    random.seed(42)
    sampled_files = random.sample(all_files, sample_size)
    print(f"🎲 무작위 추출 샘플 수: {sample_size}개 (시드: 42)\n")

    # 컴포넌트 초기화
    config = PipelineConfig()
    extractor = TitleAnchorExtractor()
    origin_detector = NovelOriginDetector()
    classifier_adapter = GenreClassifierAdapter(config)
    normalizer_adapter = FilenameNormalizerAdapter(config)

    results = []
    origin_counter = Counter()
    is_foreign_counter = Counter()
    genre_counter = Counter()
    source_counter = Counter()
    origin_genre_map = {
        'KR': Counter(),
        'CN': Counter(),
        'JP': Counter(),
        'UNKNOWN': Counter()
    }

    print("=" * 80)
    print(f"{'No.':<4} | {'원산지':<6} | {'장르':<6} | {'출처/신뢰도':<14} | {'정규화 파일명'}")
    print("=" * 80)

    for idx, file_path in enumerate(sampled_files, 1):
        raw_name = file_path.name
        
        # NovelTask 생성
        task = NovelTask(
            original_path=file_path,
            current_path=file_path,
            raw_name=raw_name
        )
        task.metadata['original_raw_name'] = raw_name

        # 1. 제목 앵커 파싱
        parse_res = extractor.extract(raw_name)
        task.title = parse_res.title
        task.author = parse_res.author
        task.volume_info = parse_res.volume_info
        task.range_info = parse_res.range_info
        task.is_completed = parse_res.is_completed
        task.side_story = parse_res.side_story
        task.edition_info = parse_res.edition_info
        if parse_res.original_foreign_title:
            task.metadata['original_foreign_title'] = parse_res.original_foreign_title
            task.metadata['has_space_before_foreign'] = parse_res.has_space_before_foreign

        # 2. 본문 헤더 추출 확인
        header_info = ContentHeaderGenreExtractor.extract_from_file(file_path)

        # 3. 장르 분류 실행 (내부에서 NovelOriginDetector.detect 자동 호출)
        classifier_adapter.classify(task)

        # 국적 정보 추출
        origin = task.metadata.get('country_origin', 'UNKNOWN')
        is_foreign = task.metadata.get('is_foreign', False)
        origin_reasons = task.metadata.get('origin_reasons', [])

        # 5. 가상 정규화 파일명 생성 (실제 파일 이동 없음)
        valid_genre = normalizer_adapter._validate_genre(task.genre)
        norm_name = normalizer_adapter._build_normalized_name(
            genre=valid_genre,
            title=task.title or raw_name,
            volume_info=task.volume_info,
            range_info=task.range_info,
            is_completed=task.is_completed,
            side_story=task.side_story,
            edition_info=task.edition_info,
            original_foreign_title=task.metadata.get('original_foreign_title', ''),
            has_space_before_foreign=task.metadata.get('has_space_before_foreign', True)
        ) + file_path.suffix

        # 통계 집계
        genre = task.genre or '미분류'
        source = getattr(task, 'source', 'unknown') or 'unknown'
        conf = getattr(task, 'confidence', 'low') or 'low'

        origin_counter[origin] += 1
        is_foreign_counter[is_foreign] += 1
        genre_counter[genre] += 1
        source_counter[source] += 1
        origin_genre_map[origin][genre] += 1

        res_entry = {
            'index': idx,
            'raw_name': raw_name,
            'title': task.title,
            'author': task.author,
            'origin': origin,
            'is_foreign': is_foreign,
            'origin_reason': ", ".join(origin_reasons) if origin_reasons else '',
            'header_genre': header_info.raw_genre if header_info else None,
            'header_is_foreign': header_info.is_foreign if header_info else False,
            'genre': genre,
            'genre_source': source,
            'genre_confidence': conf,
            'normalized_name': norm_name
        }
        results.append(res_entry)

        # 상위 30개 및 특정 샘플 출력
        if idx <= 25 or idx % 20 == 0:
            src_conf_str = f"{source}({conf})"
            print(f"[{idx:03d}] | {origin:<6} | {genre:<6} | {src_conf_str:<14} | {norm_name[:50]}")

    print("=" * 80)
    print("\n📊 [검증 결과 종합 통계 보고서]")
    print(f"• 총 검증 샘플 수: {len(results)}개")
    
    print("\n1. 소설 원산지(국적) 분포:")
    for orig, cnt in origin_counter.most_common():
        pct = (cnt / len(results)) * 100
        print(f"   - {orig:<7}: {cnt:3d}개 ({pct:5.1f}%)")
    print(f"   * 해외 소설 여부: 해외 {is_foreign_counter[True]}개 ({(is_foreign_counter[True]/len(results))*100:.1f}%), 국내 {is_foreign_counter[False]}개 ({(is_foreign_counter[False]/len(results))*100:.1f}%)")

    print("\n2. 장르별 분류 분포:")
    for g, cnt in genre_counter.most_common():
        pct = (cnt / len(results)) * 100
        print(f"   - {g:<7}: {cnt:3d}개 ({pct:5.1f}%)")

    print("\n3. 장르 판정 출처(Source) 분포:")
    for s, cnt in source_counter.most_common():
        pct = (cnt / len(results)) * 100
        print(f"   - {s:<12}: {cnt:3d}개 ({pct:5.1f}%)")

    print("\n4. 국적별 주요 장르 매핑 현황:")
    for orig in ['CN', 'JP', 'KR', 'UNKNOWN']:
        if origin_counter[orig] > 0:
            top_genres = origin_genre_map[orig].most_common(5)
            genre_summary = ", ".join([f"{g}({c})" for g, c in top_genres])
            print(f"   [{orig} 소설 총 {origin_counter[orig]}개] -> 주요 장르: {genre_summary}")

    # 결과 JSON 저장
    output_log_dir = Path(PROJECT_ROOT) / "logs"
    output_log_dir.mkdir(exist_ok=True)
    report_file = output_log_dir / "mydown_200_verification.json"
    
    summary_data = {
        "sample_size": len(results),
        "target_dir": str(target_dir),
        "origin_stats": dict(origin_counter),
        "is_foreign_stats": dict(is_foreign_counter),
        "genre_stats": dict(genre_counter),
        "source_stats": dict(source_counter),
        "origin_genre_distribution": {k: dict(v) for k, v in origin_genre_map.items()},
        "results": results
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    print(f"\n📁 상세 검증 결과 JSON 파일 저장 완료: {report_file}")

if __name__ == "__main__":
    main()
