"""
==============================================================================
파일: scripts/run_new_100_verification.py
역할 및 목적:
    `list.txt`에서 무작위 100개 샘플(시드 고정)을 추출하여 Title Anchor 파싱 및
    Search-First 장르 분류 정확도를 자동 검증하는 배치 검증 스크립트.
    결과 통계(분류율, 미분류율)를 터미널에 출력하고 JSON 결과 파일로 저장합니다.
주요 구성 요소:
    - main(): 100개 샘플링 및 TitleAnchorExtractor / GenreClassifierAdapter 연동 검증
상호 연관 관계 및 의존성:
    - Caller: 개발자 및 자동화 테스트
    - Callee: core.title_anchor_extractor, core.adapters.genre_classifier_adapter, list.txt
수정 시 주의사항:
    - 재현 가능한 평가를 위해 random.seed(2026)를 고정 유지해야 합니다.
==============================================================================
"""
import os
import sys

# 프로젝트 루트 경로를 sys.path 최상단에 추가 (Pyrefly / linter 및 실행 경로 호환)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import random
from core.title_anchor_extractor import TitleAnchorExtractor  # type: ignore
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter  # type: ignore
from core.pipeline_orchestrator import PipelineConfig  # type: ignore
from core.novel_task import NovelTask  # type: ignore

def main():
    if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    # 1. 파일 읽기 (UTF-16) - 프로젝트 루트 기준 절대 경로 적용
    list_path = os.path.join(PROJECT_ROOT, 'list.txt')
    if not os.path.exists(list_path):
        print(f"❌ '{list_path}' 파일을 찾을 수 없습니다.")
        return

    with open(list_path, 'r', encoding='utf-16') as f:
        lines = [l.strip() for l in f if l.strip()]

    print(f"Total lines in list.txt: {len(lines)}")

    # 2. 새로운 무작위 100개 샘플링 (seed=2026)
    random.seed(2026)
    samples = random.sample(lines, 100)

    extractor = TitleAnchorExtractor()
    config = PipelineConfig()
    adapter = GenreClassifierAdapter(config)

    results = []
    for idx, raw_name in enumerate(samples, 1):
        parsed = extractor.extract(raw_name)
        clean_title = parsed.title if parsed.title else raw_name
        
        task = NovelTask(original_path=raw_name, current_path=raw_name, raw_name=raw_name)
        task.title = clean_title
        
        adapter.classify(task)
        
        res = {
            'index': idx,
            'raw_name': raw_name,
            'extracted_title': parsed.title,
            'author': parsed.author,
            'volume_info': parsed.volume_info,
            'range_info': parsed.range_info,
            'is_completed': parsed.is_completed,
            'side_story': parsed.side_story,
            'genre': task.genre,
            'genre_source': getattr(task, 'genre_source', 'unknown'),
            'genre_confidence': getattr(task, 'genre_confidence', 0.0)
        }
        results.append(res)
        print(f"[{idx:03d}/100] RAW: {raw_name[:40]} -> TITLE: '{parsed.title}' | GENRE: {task.genre}")

    output_json = os.path.join(PROJECT_ROOT, 'new_sample_100_verification.json')
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSuccessfully verified NEW 100 samples and saved to {output_json}!")

    classified = [r for r in results if r['genre'] != '미분류']
    unclassified = [r for r in results if r['genre'] == '미분류']

    print("\n==================================================")
    print("  NEW 100 Sample Verification Summary")
    print("==================================================")
    print(f"Total Samples: {len(results)}")
    print(f"Classified: {len(classified)} ({len(classified)/len(results)*100:.1f}%)")
    print(f"Unclassified: {len(unclassified)} ({len(unclassified)/len(results)*100:.1f}%)")
    print("==================================================")

if __name__ == '__main__':
    main()
