
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.pipeline_logger import PipelineLogger, get_logger

def test_logger():
    log_dir = Path("tests/logs_test")
    if log_dir.exists():
        shutil.rmtree(log_dir)
        
    # Initialize logger
    logger = PipelineLogger(log_dir=log_dir, console_output=True)
    
    # Log something in Korean to test UTF-8
    test_msg = "테스트 메시지입니다. 한글이 잘 나오나요?"
    logger.info(test_msg)
    
    # Check file existence
    date_str = datetime.now().strftime("%Y%m%d")
    expected_filename = f"wnap_{date_str}.log"
    log_file = log_dir / expected_filename
    
    if not log_file.exists():
        print(f"[FAIL] Log file not created: {log_file}")
        return
        
    print(f"[SUCCESS] Log file created: {log_file}")
    
    # Check content and encoding
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if test_msg in content:
                print(f"[SUCCESS] Content match and UTF-8 encoding verified.")
            else:
                print(f"[FAIL] Content mismatch. Found: {content}")
    except UnicodeDecodeError:
        print("[FAIL] File is not valid UTF-8.")
    except Exception as e:
        print(f"[FAIL] Error reading file: {e}")
        
    logger.close()

if __name__ == "__main__":
    test_logger()
