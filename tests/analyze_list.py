import sys
import os
import re

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.title_anchor_extractor import TitleAnchorExtractor

def analyze_list():
    extractor = TitleAnchorExtractor()
    list_path = os.path.join(os.path.dirname(__file__), '..', 'list.txt')
    
    if not os.path.exists(list_path):
        print(f"Error: {list_path} not found")
        return

    print(f"{'Original Filename':<80} | {'Title':<40} | {'Volume/Range':<20} | {'Completed':<5} | {'Side Story':<20}")
    print("-" * 180)

    try:
        with open(list_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        count = 0
        suspicious_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove leading numbers/dots if present in the FILE itself (e.g. "1. filename")
            # But based on view_file output, the file just has raw filenames (the numbered list in view_file was added by the tool)
            # Checking line 1: "100층의 올마스터 120 .txt"
            
            result = extractor.extract(line)
            
            # Combine volume and range for display
            vol_range = f"{result.volume_info} {result.range_info}".strip()
            
            print(f"{line[:80]:<80} | {result.title[:40]:<40} | {vol_range[:20]:<20} | {str(result.is_completed):<5} | {result.side_story[:20]:<20}")
            
            # Basic heuristic for suspicious parsing
            if not result.title:
                print(f"  [SUSPICIOUS] Empty Title: {line}")
                suspicious_count += 1
            elif re.search(r'\d+-\d+', result.title):
                print(f"  [SUSPICIOUS] Range in Title?: {result.title} | Line: {line}")
                suspicious_count += 1
            
            count += 1
            
        print("-" * 180)
        print(f"Total processed: {count}, Suspicious: {suspicious_count}")
        
        # Select 10 most complex files
        # Complexity metric: length of filename + number of special characters
        def calculate_complexity(name):
            special_chars = len(re.findall(r'[^\w\s]', name))
            return len(name) + (special_chars * 2)
            
        complex_files = sorted(lines, key=lambda x: calculate_complexity(x.strip()), reverse=True)[:10]
        
        print("\nTop 10 Complex Files:")
        complex_files_path = os.path.join(os.path.dirname(__file__), 'complex_files.txt')
        with open(complex_files_path, 'w', encoding='utf-8') as f:
            for line in complex_files:
                line = line.strip()
                print(f"  - {line}")
                f.write(line + "\n")
        print(f"\nSaved complex files to {complex_files_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    analyze_list()
