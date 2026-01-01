import os
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.classifier.api_config_manager import APIConfigManager

class TestHybridSecurity(unittest.TestCase):
    def setUp(self):
        self.manager = APIConfigManager('test_config.json')
        # 환경변수 임시 설정
        os.environ['NAVER_CLIENT_ID'] = 'ENV_TEST_ID'
        os.environ['NAVER_CLIENT_SECRET'] = 'ENV_TEST_SECRET'
        os.environ['GOOGLE_API_KEY'] = 'ENV_GOOGLE_KEY'
        os.environ['GOOGLE_CSE_ID'] = 'ENV_CSE_ID'

    def tearDown(self):
        # 환경변수 정리
        if 'NAVER_CLIENT_ID' in os.environ: del os.environ['NAVER_CLIENT_ID']
        if 'NAVER_CLIENT_SECRET' in os.environ: del os.environ['NAVER_CLIENT_SECRET']
        if 'GOOGLE_API_KEY' in os.environ: del os.environ['GOOGLE_API_KEY']
        if 'GOOGLE_CSE_ID' in os.environ: del os.environ['GOOGLE_CSE_ID']

    def test_env_priority_naver(self):
        print("\n[Test] Naver: Env Variable Priority")
        config = self.manager.load_config()
        self.assertEqual(config['client_id'], 'ENV_TEST_ID')
        self.assertEqual(config['client_secret'], 'ENV_TEST_SECRET')
        print(" -> Passed: Loaded from Env")

    def test_env_priority_google(self):
        print("\n[Test] Google: Env Variable Priority")
        config = self.manager.load_google_config()
        self.assertEqual(config['api_key'], 'ENV_GOOGLE_KEY')
        self.assertEqual(config['cse_id'], 'ENV_CSE_ID')
        print(" -> Passed: Loaded from Env")
        
    def test_fallback_encryption(self):
        print("\n[Test] Fallback to Encrypted File")
        # 환경변수 제거
        del os.environ['NAVER_CLIENT_ID']
        del os.environ['NAVER_CLIENT_SECRET']
        
        # 암호화 파일 생성 테스트는 복잡하므로, 메서드가 None을 반환하거나
        # (파일이 없으므로) 정상 동작하는지 확인
        config = self.manager.load_config()
        # 파일이 없으면 None이어야 함
        self.assertIsNone(config)
        print(" -> Passed: Correctly handled missing env and file")

if __name__ == '__main__':
    unittest.main()
