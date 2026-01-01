import sys
import os
import csv
import time
import logging
from typing import List, Dict

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.classifier.api_config_manager import APIConfigManager
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.pipeline_orchestrator import PipelineConfig
from core.novel_task import NovelTask
from core.title_anchor_extractor import TitleAnchorExtractor
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("BatchClassifier")

def main():
    print("="*80)
    print("일괄 장르 분류 프로세스 (Batch Genre Classification)")
    print("="*80)

    # 1. 환경 변수 로드 (Override)
    load_dotenv(override=True)
    
    # 2. API 설정 및 키 접두사 검증
    manager = APIConfigManager()
    google_conf = manager.load_google_config()
    
    if not google_conf:
        print("❌ Google API 설정이 없습니다. .env 파일을 확인하세요.")
        return

    api_key = google_conf['api_key']
    if api_key.startswith("AIzaSyCiV_"):
        print(f"✅ [보안] API Key Verified (Prefix: AIzaSyCiV_)")
    else:
        print(f"⚠️ [경고] API Key Prefix Mismatch: {api_key[:10]}...")

    # 3. 컴포넌트 초기화
    config = PipelineConfig()
    adapter = GenreClassifierAdapter(config)
    title_extractor = TitleAnchorExtractor()
    
    # 4. 파일 리스트 읽기
    list_file = "list.txt"
    if not os.path.exists(list_file):
        print(f"❌ '{list_file}' 파일이 없습니다.")
        return

    with open(list_file, 'r', encoding='utf-8') as f:
        filenames = [line.strip() for line in f if line.strip()]

    print(f"▶ 총 처리 대상: {len(filenames)}개")
    print("-" * 80)

    # 5. 결과 파일 준비
    output_file = "classification_results.csv"
    
    # 동시성 제어
    from concurrent.futures import ThreadPoolExecutor
    import threading
    
    csv_lock = threading.Lock()
    stats_lock = threading.Lock()
    
    # 통계
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'processed_count': 0
    }

    # CSV 헤더 작성 (먼저 실행)
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['filename', 'title', 'genre', 'confidence', 'source']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    def process_item(filename):
        try:
            # 6-1. 제목 추출
            parsed = title_extractor.extract(filename)
            clean_title = parsed.title if parsed.title else filename
            
            # 6-2. Task 생성
            task = NovelTask(original_path=filename, current_path=filename, raw_name=filename)
            task.title = clean_title
            
            # 6-3. 분류 실행 (Hybrid Search)
            adapter.classify(task)
            
            # 6-4. 결과 구성
            genre = task.genre if task.genre else "미분류"
            outcome = {
                'filename': filename,
                'title': clean_title,
                'genre': genre,
                'confidence': task.confidence,
                'source': getattr(task, 'source', 'unknown')
            }
            
            # 6-5. 결과 기록 (Thread-Safe)
            with csv_lock:
                with open(output_file, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=['filename', 'title', 'genre', 'confidence', 'source'])
                    writer.writerow(outcome)
            
            # 통계 업데이트
            with stats_lock:
                stats['processed_count'] += 1
                if genre and genre != "미분류":
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                
                # 진행 상황 로그 (10개 단위)
                if stats['processed_count'] % 10 == 0:
                    print(f"[{stats['processed_count']}/{len(filenames)}] 분류 완료... (성공: {stats['success']}, 실패: {stats['failed']})")

        except Exception as e:
            msg = f"❌ [Error] {filename}: {e}"
            print(msg)
            with stats_lock:
                stats['failed'] += 1

    # 6. 병렬 실행
    print(f"▶ 병렬 처리 시작 (Threads: 10)...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(process_item, filenames)

    # 7. 최종 보고
    print("="*80)
    print("최종 처리 결과 보고")
    print("="*80)
    print(f"총 파일 수: {len(filenames)}")
    print(f"처리 완료 : {stats['processed_count']}")
    print(f"분류 성공 : {stats['success']}")
    print(f"미분류    : {stats['failed']}")
    print(f"결과 파일 : {os.path.abspath(output_file)}")
    print("="*80)

if __name__ == "__main__":
    main()
