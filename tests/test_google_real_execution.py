import sys
import os
import logging

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.classifier.src.core.google_genre_extractor import GoogleGenreExtractor
from modules.classifier.api_config_manager import APIConfigManager

def test_google_search():
    print("="*60)
    print("구글 API 연동 실전 테스트 (Hybrid Security)")
    print("="*60)
    
    # 1. 키 로드 확인
    manager = APIConfigManager()
    config = manager.load_google_config()
    
    if not config:
        print("❌ [경고] .env 또는 암호화된 Google 설정이 없습니다.")
        print("   테스트를 진행하려면 .env 파일에 GOOGLE_API_KEY와 GOOGLE_CSE_ID를 설정하세요.")
        return

    print(f"[보안] Google API 설정 로드 성공 (Source: .env/Encrypted)")
    
    # 키 접두사 확인 (사용자 요청: AIzaSyCiV_...)
    current_key = config['api_key']
    expected_prefix = "AIzaSyCiV_"
    
    if current_key.startswith(expected_prefix):
        print(f"[검증] API Key가 올바른 프로젝트 키입니다. (Prefix: {expected_prefix})")
    else:
        print(f"[경고] API Key가 예상된 접두사와 다릅니다.")
        print(f"   Expected: {expected_prefix}...")
        print(f"   Actual:   {current_key[:10]}...")

    # 키 마스킹 출력
    masked_key = current_key[:5] + "*" * 5 + current_key[-3:] if current_key else "None"
    print(f"   API Key: {masked_key}")
    print("-" * 60)

    # 2. Extractor 초기화
    extractor = GoogleGenreExtractor(config['api_key'], config['cse_id'])
    
    # 3. 테스트 시나리오
    target_title = "어살"  # 네이버 검색 실패 예상 작품
    print(f"▶ 테스트 작품: {target_title}")
    
    # (가정) Naver 검색 실패
    print(f"▶ 1단계: Naver 검색 시도...")
    print(f"   -> 결과: 실패 (Simulation)")

    # Google 검색 시도
    print(f"▶ 2단계: Google 검색 시도...")
    result = extractor.extract_genre(target_title)
    
    print("-" * 60)
    print("<< 결과 보고서 >>")
    print(f"* 작품명: {target_title}")
    print(f"* Naver 결과: 실패 (Simulated/Confirmed)")
    
    if result:
        print(f"* Google 결과: [{result['genre']}]")
        print(f"* 최종 소스: {result['source']}")
        print(f"* 신뢰도: {result['confidence']}")
    else:
        print(f"* Google 결과: 검색 실패 또는 키워드 매칭 불가")
        print(f"* 최종 소스: -")
        print(f"* 신뢰도: 0.0")
    
    print("-" * 60)
    
    # 추가 테스트: 확실한 판타지 소설
    target2 = "전지적 독자 시점"
    print(f"▶ 추가 테스트: {target2}")
    result2 = extractor.extract_genre(target2)
    
    if result2:
        print(f"* Google 결과: [{result2['genre']}]")
    else:
        print(f"* Google 결과: 실패")

    print("="*60)

if __name__ == "__main__":
    # 로깅 포맷 설정 (Stdout으로 출력)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # DEBUG 모드로 변경
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)
    
    test_google_search()
