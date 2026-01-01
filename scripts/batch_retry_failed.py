import sys
import os
import csv
import time
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.classifier.api_config_manager import APIConfigManager
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.pipeline_orchestrator import PipelineConfig
from core.novel_task import NovelTask
from core.title_anchor_extractor import TitleAnchorExtractor
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')

def main():
    print("="*80)
    print("미분류 작품 재처리 (Google Scraping & Enhanced Logic)")
    print("="*80)

    # 1. 환경 변수
    load_dotenv(override=True)
    
    # 2. API 설정 확인
    manager = APIConfigManager()
    google_conf = manager.load_google_config()
    if google_conf and google_conf['api_key'].startswith("AIzaSyCiV_"):
         print(f"✅ [보안] API Key Verified (Prefix: AIzaSyCiV_)")
    else:
         print(f"⚠️ [경고] API Key 확인 필요")

    # 3. 컴포넌트
    config = PipelineConfig()
    adapter = GenreClassifierAdapter(config)
    title_extractor = TitleAnchorExtractor()
    
    # 4. CSV 로드
    input_file = "classification_results.csv"
    if not os.path.exists(input_file):
        print("❌ 결과 파일이 없습니다.")
        return

    all_rows = []
    failed_indices = []
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for i, row in enumerate(reader):
            all_rows.append(row)
            if row['genre'] == '미분류' or row['genre'] == 'Error':
                failed_indices.append(i)
                
    print(f"▶ 총 데이터: {len(all_rows)}")
    print(f"▶ 재처리 대상: {len(failed_indices)} (미분류/Error)")
    print("-" * 80)
    
    csv_lock = threading.Lock()
    stats = {'processed': 0, 'success': 0, 'quota_error': False}
    
    def process_index(idx):
        if stats['quota_error']:
            return

        row = all_rows[idx]
        filename = row['filename']
        
        try:
            # Task 생성 및 분류
            parsed = title_extractor.extract(filename)
            clean_title = parsed.title if parsed.title else filename
            
            task = NovelTask(original_path=filename, current_path=filename, raw_name=filename)
            task.title = clean_title
            
            adapter.classify(task)
            
            # Quota Check (stdout capture hack is hard, logic inference)
            # If Google Extractor prints CRITICAL, we can't catch it here easily in thread.
            # But we can check if task.source is '-' and we expected Google.
            
            # 결과 업데이트
            if task.genre and task.genre != '미분류':
                row['genre'] = task.genre
                row['confidence'] = task.confidence
                row['source'] = getattr(task, 'source', 'unknown')
                
                with csv_lock:
                    stats['success'] += 1
                    print(f"  [성공] {clean_title} -> {task.genre} ({row['source']})")
            else:
                print(f"  [실패] {clean_title}")

        except Exception as e:
            print(f"❌ {filename}: {e}")

        stats['processed'] += 1

    # 병렬 실행 (5 threads to be gentle with Scraping/Quota)
    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(process_index, failed_indices))
        
    print("-" * 80)
    
    # 결과 저장 (Overwrite)
    with open(input_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
        
    print(f"재처리 완료: {stats['processed']}건 중 {stats['success']}건 복구 성공")
    print(f"파일 저장 완료: {input_file}")

if __name__ == "__main__":
    main()
