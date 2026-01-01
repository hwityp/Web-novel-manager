
import sys
import os
import logging
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.classifier.src.core.google_genre_extractor import GoogleGenreExtractor

class TestNovelNetFilter(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.extractor = GoogleGenreExtractor("fake_key", "fake_cx")

    @patch('modules.classifier.src.core.google_genre_extractor.requests.get')
    def test_novelnet_filtering(self, mock_get):
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {
                    'title': 'Valid Novel',
                    'snippet': 'Fantasy novel',
                    'link': 'https://ssn.so/novel/12345'
                },
                {
                    'title': 'Invalid Profile',
                    'snippet': 'User profile',
                    'link': 'https://ssn.so/profile/user1'
                },
                {
                    'title': 'Invalid Comment',
                    'snippet': 'Comment section',
                    'link': 'https://ssn.so/board/comments/999' # Assuming generic or specific match
                },
                {
                    'title': 'Another Valid Site',
                    'snippet': 'Reference',
                    'link': 'https://other-site.com/info'
                }
            ]
        }
        mock_get.return_value = mock_response

        # We need to capture logs to verify "Skipping"
        with self.assertLogs(self.extractor.logger, level='DEBUG') as cm:
            # Run extraction
            # extract_genre calls requests.get
            self.extractor.extract_genre("test query")
            
            # Check logs
            logs = [r.message for r in cm.records]
            
            # 1. Profile should be skipped
            profile_skip = any("Skipping NovelNet invalid page" in msg and "profile" in msg for msg in logs)
            self.assertTrue(profile_skip, "Should skip profile page")
            
            # 2. Comment should be skipped (if matched by logic) 
            # My logic: "notifications", "comments" in blacklist. 
            # or if not /novel/ (Whitelist).
            # https://ssn.so/board/comments/999 does NOT have /novel/, so it should be skipped by whitelist or blacklist.
            comment_skip = any("Skipping NovelNet" in msg and "comments" in msg for msg in logs)
             # Actually purely whitelist check: "Skipping NovelNet non-novel page"
            comment_skip_whitelist = any("Skipping NovelNet non-novel page" in msg and "comments" in msg for msg in logs)
            self.assertTrue(comment_skip or comment_skip_whitelist, "Should skip comment page")

            print("\n[Test Log Output]")
            for log in logs:
                if "Skipping" in log:
                    print(log)

if __name__ == '__main__':
    unittest.main()
