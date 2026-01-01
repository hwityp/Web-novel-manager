"""
API 설정 관리자 (암호화 지원)
네이버 API 키를 안전하게 저장하고 불러오기
"""
import os
import sys
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

# .env 파일 로드 (시스템 변수보다 우선)
load_dotenv(override=True)


class APIConfigManager:
    """API 설정 암호화 관리자"""
    
    def __init__(self, config_file='naver_api_config.json'):
        """
        초기화
        
        Args:
            config_file: 설정 파일 경로
        """
        self.config_file = config_file
        self.key_file = '.api_key'  # 암호화 키 저장 파일 (숨김 파일)
        
        # 암호화 키 생성 또는 로드
        self.cipher_key = self._get_or_create_key()
        self.cipher = Fernet(self.cipher_key)
    
    def _get_or_create_key(self):
        """암호화 키 생성 또는 로드"""
        # PyInstaller 환경 고려
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        key_path = os.path.join(application_path, self.key_file)
        
        if os.path.exists(key_path):
            # 기존 키 로드
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            # 새 키 생성
            # 머신별 고유 키 생성 (머신 ID 기반)
            machine_id = self._get_machine_id()
            
            # PBKDF2HMAC로 키 파생
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'genre_classifier_salt',  # 고정 salt
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
            
            # 키 저장
            with open(key_path, 'wb') as f:
                f.write(key)
            
            # 숨김 파일로 설정 (Windows)
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(key_path, 2)  # FILE_ATTRIBUTE_HIDDEN
            except:
                pass
            
            return key
    
    def _get_machine_id(self):
        """머신 고유 ID 생성"""
        import platform
        import uuid
        
        # 여러 정보를 조합하여 고유 ID 생성
        machine_info = f"{platform.node()}-{uuid.getnode()}"
        return machine_info
    
    def save_config(self, client_id, client_secret, encrypt=True):
        """
        API 설정 저장
        
        Args:
            client_id: 네이버 Client ID
            client_secret: 네이버 Client Secret
            encrypt: 암호화 여부 (기본값: True)
        
        Returns:
            bool: 성공 여부
        """
        try:
            config = {
                'client_id': client_id,
                'client_secret': client_secret,
                'encrypted': encrypt
            }
            
            if encrypt:
                # 암호화
                config_json = json.dumps(config)
                encrypted_data = self.cipher.encrypt(config_json.encode())
                
                # Base64 인코딩하여 저장 (JSON 호환)
                save_data = {
                    'encrypted': True,
                    'data': base64.b64encode(encrypted_data).decode()
                }
            else:
                # 평문 저장
                save_data = config
            
            # 파일 저장 (PyInstaller 환경 고려)
            if getattr(sys, 'frozen', False):
                application_path = os.path.dirname(sys.executable)
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            config_path = os.path.join(application_path, self.config_file)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"[API Config] 설정 저장 완료 (암호화: {'예' if encrypt else '아니오'})")
            return True
            
        except Exception as e:
            print(f"[API Config] 저장 실패: {e}")
            return False
    
    def load_config(self):
        """
        API 설정 로드 (Hybrid Security: Env -> Encrypted)
        
        Returns:
            dict: {'client_id': str, 'client_secret': str} 또는 None
        """
        # 1. 환경변수 확인 (.env)
        env_client_id = os.getenv("NAVER_CLIENT_ID")
        env_client_secret = os.getenv("NAVER_CLIENT_SECRET")
        
        if env_client_id and env_client_secret:
            print(f"[API Config] .env 환경변수에서 설정 로드 완료")
            return {
                'client_id': env_client_id,
                'client_secret': env_client_secret
            }

        try:
            # PyInstaller 환경 고려
            if getattr(sys, 'frozen', False):
                application_path = os.path.dirname(sys.executable)
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            config_path = os.path.join(application_path, self.config_file)
            
            if not os.path.exists(config_path):
                print(f"[API Config] 설정 파일 없음: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 암호화된 데이터인지 확인
            if data.get('encrypted'):
                # 복호화
                encrypted_data = base64.b64decode(data['data'])
                decrypted_data = self.cipher.decrypt(encrypted_data)
                config = json.loads(decrypted_data.decode())
                
                print(f"[API Config] 암호화된 설정 로드 완료")
            else:
                # 평문 데이터
                config = data
                print(f"[API Config] 평문 설정 로드 완료")
            
            return {
                'client_id': config.get('client_id'),
                'client_secret': config.get('client_secret')
            }
            
        except Exception as e:
            print(f"[API Config] 로드 실패: {e}")
            return None
    
    def load_google_config(self, config_file='google_api_config.json'):
        """
        Google API 설정 로드 (Hybrid Security: Env -> Encrypted)
        Env 우선순위: GOOGLE_API_KEY, GOOGLE_CSE_ID
        Fallback: google_api_config.json (암호화)
        
        Returns:
            dict: {'api_key': str, 'cse_id': str} 또는 None
        """
        # 1. 환경변수 확인 (.env)
        env_api_key = os.getenv("GOOGLE_API_KEY")
        env_cse_id = os.getenv("GOOGLE_CSE_ID")
        
        if env_api_key and env_cse_id:
            print(f"[API Config] .env 환경변수에서 Google 설정 로드 완료")
            return {
                'api_key': env_api_key,
                'cse_id': env_cse_id
            }

        try:
            # PyInstaller 환경 고려
            if getattr(sys, 'frozen', False):
                application_path = os.path.dirname(sys.executable)
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            config_path = os.path.join(application_path, config_file)
            
            if not os.path.exists(config_path):
                # print(f"[API Config] Google 설정 파일 없음: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 암호화된 데이터인지 확인
            if data.get('encrypted'):
                # 복호화
                encrypted_data = base64.b64decode(data['data'])
                decrypted_data = self.cipher.decrypt(encrypted_data)
                config = json.loads(decrypted_data.decode())
                
                print(f"[API Config] 암호화된 Google 설정 로드 완료")
            else:
                # 평문 데이터
                config = data
                print(f"[API Config] 평문 Google 설정 로드 완료")
            
            return {
                'api_key': config.get('api_key'),
                'cse_id': config.get('cse_id')
            }
            
        except Exception as e:
            print(f"[API Config] Google 설정 로드 실패: {e}")
            return None

    def migrate_to_encrypted(self):
        """평문 설정을 암호화 설정으로 마이그레이션"""
        try:
            config = self.load_config()
            if config:
                # 암호화하여 다시 저장
                return self.save_config(
                    config['client_id'],
                    config['client_secret'],
                    encrypt=True
                )
            return False
        except Exception as e:
            print(f"[API Config] 마이그레이션 실패: {e}")
            return False


def test_encryption():
    """암호화 테스트"""
    print("="*60)
    print("API 설정 암호화 테스트")
    print("="*60)
    print()
    
    manager = APIConfigManager('test_config.json')
    
    # 1. 암호화 저장
    print("1. 암호화 저장 테스트...")
    test_id = "test_client_id_12345"
    test_secret = "test_client_secret_67890"
    
    success = manager.save_config(test_id, test_secret, encrypt=True)
    print(f"   저장 결과: {'성공' if success else '실패'}")
    print()
    
    # 2. 암호화 로드
    print("2. 암호화 로드 테스트...")
    config = manager.load_config()
    
    if config:
        print(f"   Client ID: {config['client_id']}")
        print(f"   Client Secret: {config['client_secret']}")
        
        # 검증
        if config['client_id'] == test_id and config['client_secret'] == test_secret:
            print("   ✅ 암호화/복호화 성공!")
        else:
            print("   ❌ 데이터 불일치!")
    else:
        print("   ❌ 로드 실패!")
    
    print()
    
    # 3. 파일 내용 확인
    print("3. 저장된 파일 내용 (암호화됨):")
    try:
        with open('test_config.json', 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"   {content[:200]}...")
    except:
        pass
    
    print()
    
    # 4. 평문 저장 테스트
    print("4. 평문 저장 테스트...")
    manager.save_config(test_id, test_secret, encrypt=False)
    
    print("   저장된 파일 내용 (평문):")
    try:
        with open('test_config.json', 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"   {content}")
    except:
        pass
    
    print()
    
    # 5. 정리
    print("5. 테스트 파일 정리...")
    try:
        os.remove('test_config.json')
        os.remove('.api_key')
        print("   ✅ 정리 완료")
    except:
        pass
    
    print()
    print("="*60)


if __name__ == '__main__':
    test_encryption()
