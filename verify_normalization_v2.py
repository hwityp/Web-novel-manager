
import sys
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).parent
project_root = current_dir
sys.path.insert(0, str(project_root))

from core.title_anchor_extractor import TitleAnchorExtractor
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter
from config.pipeline_config import PipelineConfig
from core.novel_task import NovelTask

def verify():
    print("=== Verification Start ===")
    
    # Setup
    extractor = TitleAnchorExtractor()
    config = PipelineConfig()
    normalizer = FilenameNormalizerAdapter(config)
    
    # Case 1: Preserve (19N)
    # Expected: "Title (19N) 100.txt" -> "Title (19N) 100.txt" (if no range/genre)
    raw_1 = "My Novel (19N) 100.txt"
    res_1 = extractor.extract(raw_1)
    print(f"\n[Case 1] Input: {raw_1}")
    print(f"  Title: '{res_1.title}' (Expect 'My Novel (19N)' or similar preserving 19N)")
    
    # Case 2: Range Leading Zeros
    # Expected: "Novel 001-242.txt" -> Range "1-242"
    raw_2 = "Magic Walk 001-242.txt"
    res_2 = extractor.extract(raw_2)
    print(f"\n[Case 2] Input: {raw_2}")
    print(f"  Range: '{res_2.range_info}' (Expect '1-242')")
    
    # Case 3: No [미분류] tag
    # Use Adapter directly
    print(f"\n[Case 3] Genre '미분류' check")
    normalized_name = normalizer._build_normalized_name(
        genre="미분류",
        title="Test Title",
        range_info="1-100"
    )
    print(f"  Result: '{normalized_name}'")
    if "[미분류]" not in normalized_name:
        print("  SUCCESS: [미분류] tag omitted.")
    else:
        print("  FAILURE: [미분류] tag present.")

if __name__ == "__main__":
    verify()
