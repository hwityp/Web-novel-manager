import sys
import os
sys.path.append(os.getcwd())

print("Attempting to import GoogleGenreExtractor...")
try:
    from modules.classifier.src.core.google_genre_extractor import GoogleGenreExtractor
    print("Import Successful!")
    
    extractor = GoogleGenreExtractor("test", "test")
    print("Instantiation Successful!")
    
    if hasattr(extractor, 'quota_blocked'):
        print(f"Quota Blocked logic found: {extractor.quota_blocked}")
    else:
        print("Warning: quota_blocked attribute not found in __init__")

    print("_scrape_url check:", extractor._scrape_url("invalid_url")) # Should return []

except Exception as e:
    print(f"Import Failed: {e}")
    import traceback
    traceback.print_exc()

print("Verification Done.")
