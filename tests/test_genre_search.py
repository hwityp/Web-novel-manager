import sys
import os
import shutil
import logging
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.novel_task import NovelTask
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from config.pipeline_config import PipelineConfig

# 로깅 설정 (콘솔 출력용)
logging.basicConfig(level=logging.DEBUG)

def test_search_logic():
    print(f"\n{'='*80}")
    print("Search-First Genre Classification Verification")
    print(f"{'='*80}")

    config = PipelineConfig()
    classifier = GenreClassifierAdapter(config)
    
    # 테스트할 파일 목록 (사용자가 언급한 예시 포함)
    test_files = [
        "100층의 올마스터 120 .txt",
        "[선협] 어살 1-1014 完 (AI번역) @EE.txt",
        "달빛조각사 58권.txt", # 유명한 소설 추가
        "임의의_검색되지_않을_파일_키워드테스트.txt" # Fallback 확인용
    ]
    
    for filename in test_files:
        print(f"\n[Test File] {filename}")
        
        # 가짜 파일 경로 생성
        dummy_path = Path(f"C:/Test/{filename}")
        task = NovelTask(
            original_path=dummy_path,
            current_path=dummy_path,
            raw_name=dummy_path.stem
        )
        
        # 분류 수행
        # 주의: classify() 메서드 내부에서 print문으로 검색 과정을 출력하므로 이를 확인해야 함
        try:
            task = classifier.classify(task)
            
            print(f"  -> Final Genre: {task.genre}")
            print(f"  -> Confidence: {task.confidence}")
            print(f"  -> Source: {task.source}")
            
            if task.source == 'cache':
                print("  (Warning: Result came from CACHE. Delete 'genre_cache.json' to test real search)")
                
        except Exception as e:
            print(f"  [ERROR] Classification failed: {e}")

if __name__ == "__main__":
    # 캐시 파일이 있다면 삭제하여 리얼 검색 유도 (선택 사항)
    # cache_path = Path('config/genre_cache.json')
    # if cache_path.exists():
    #     print("Removing genre cache for fresh search test...")
    #     os.remove(cache_path)
        
    test_search_logic()
