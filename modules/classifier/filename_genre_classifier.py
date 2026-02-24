"""
파일명 기반 장르 분류기 (개선 버전)
파일명에서 소설 제목 추출 → 장르 분류
작가명 제거 로직 추가

버전은 core/version.py에서 중앙 관리됩니다.
"""

import os
import re
import sys

from modules.classifier.src.core.hybrid_classifier_v2 import HybridClassifier


class FilenameGenreClassifier:
    """파일명 기반 장르 분류기"""
    
    def __init__(self):
        self.classifier = HybridClassifier()
    
    def extract_title_from_filename(self, filename):
        """
        파일명에서 소설 제목 추출 (개선 버전)
        
        예시:
        - "나혼자만레벨업_001.txt" → "나혼자만레벨업"
        - "[판타지] 전지적 독자 시점.epub" → "전지적 독자 시점"
        - "화산귀환 1-50화.txt" → "화산귀환"
        - "나 혼자 소드 마스터 1-1031 (완) + 외전 1-79, 에필" → "나 혼자 소드 마스터"
        - "눈 감고 3점 슛 1-424 (완).txt" → "눈 감고 3점 슛"
        """
        # 확장자 제거
        name = os.path.splitext(filename)[0]
        
        # 숫자 범위 패턴 제거 (하이픈으로 연결된 두 숫자)
        # "트립한국 1913 1-126 (완)" → "트립한국 1913 (완)"
        # 범위 패턴: "1-247", "1~247" (하이픈/틸드로 연결된 숫자)
        # 단독 숫자는 제목의 일부이므로 유지: "1913"
        name = re.sub(r'\s+\d+[-~]\d+[화권부편]?\s*(?:\(완\))?', ' ', name)  # "1-247 (완)" 제거
        
        # 부가 정보 제거 - 괄호는 제거하되 내용은 유지
        # "[단행본]" → 제거, "(완결)" → 제거 (특정 키워드만)
        # 하지만 "(여자)" 같은 제목의 일부는 괄호만 제거하고 내용 유지
        
        # 1. 명확한 부가 정보 키워드는 괄호와 함께 제거
        name = re.sub(r'\s*\[(단행본|완결|연재중|개정판|합본|개정|특별판|장르|작가|판타지|무협|로맨스|BL)\]\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\((완결|연재중|개정판|합본|개정|특별판|완|19금|19N|19n|19|15금|15|N|n)\)\s*', '', name, flags=re.IGNORECASE)
        
        # 2. 나머지 괄호는 그대로 유지 (extract_genre_from_title에서 처리)
        # "광불화형전(화형령주)" → "광불화형전(화형령주)" (유지)
        # 괄호 내용은 부제일 수 있으므로 extract_genre_from_title에서 분리
        
        # "+ 외전", "+ 에필", "+ 특별편" 등 제거 (+ 이후 모두 제거)
        name = re.sub(r'\s*\+.*$', '', name)
        
        # 작가명 제거는 extract_genre_from_title에서 처리
        # "구룡겁 - 천중행,천중화" → "구룡겁 - 천중행,천중화" (유지)
        # 복수 저자, 단일 저자 모두 extract_genre_from_title에서 처리
        
        # 단독 화/권/부/편 번호 제거 (1화, 50권 등)
        # 패턴: 공백이나 구분자 뒤의 숫자+단위 (뒤에 조사가 없는 경우만)
        # 보존: "2부를", "3권을" (조사가 붙은 경우)
        # 제거: " 1화", " 50권" (뒤에 공백이나 끝이 오는 경우)
        name = re.sub(r'[\s_\-]+\d+[화권부편](?=\s|$)', '', name)
        
        # 끝부분의 언더스코어/하이픈 + 숫자 제거 (_001, -50 등)
        # 단, 공백 + 숫자는 제목의 일부일 수 있으므로 제거하지 않음
        # "트립한국 1913" (유지), "파일명_001" (제거)
        name = re.sub(r'[_\-]+\d+$', '', name)
        
        # 특수문자 정리 (_ 만 공백으로, - 는 유지)
        # - 는 저자명 구분자로 사용되므로 유지 (예: "제목 - 저자")
        name = re.sub(r'_+', ' ', name)
        
        # 연속된 공백을 하나로
        name = ' '.join(name.split())
        
        return name.strip()
    
    def classify_file(self, filename, use_naver=True, naver_api_config=None):
        """
        파일명으로 장르 분류
        
        Args:
            filename: 파일명
            use_naver: 네이버 검색 사용 여부
            naver_api_config: 네이버 API 설정 (dict with 'client_id', 'client_secret')
            
        Returns:
            {
                'filename': 원본 파일명,
                'title': 추출된 제목,
                'genre': 분류된 장르,
                'confidence': 신뢰도,
                'method': 분류 방법,
                'details': 상세 결과
            }
        """
        # 제목 추출
        title = self.extract_title_from_filename(filename)
        
        if not title:
            return {
                'filename': filename,
                'title': None,
                'genre': '미분류',
                'confidence': 0.0,
                'method': 'no_title',
                'details': None
            }
        
        # 장르 분류
        result = self.classifier.classify(title, use_naver=use_naver, naver_api_config=naver_api_config)
        
        return {
            'filename': filename,
            'title': title,
            'genre': result['genre'],
            'confidence': result['confidence'],
            'method': result['method'],
            'details': result
        }
    
    def close(self):
        """리소스 정리"""
        if hasattr(self.classifier, 'close'):
            self.classifier.close()


def test_title_extraction():
    """제목 추출 테스트"""
    classifier = FilenameGenreClassifier()
    
    test_cases = [
        ("나 혼자 소드 마스터 1-1031 (완) + 외전 1-79, 에필.txt", "나 혼자 소드 마스터"),
        ("눈 감고 3점 슛 1-424 (완).txt", "눈 감고 3점 슛"),
        ("화산귀환 1-50화.txt", "화산귀환"),
        ("[판타지] 전지적 독자 시점 1-551 (완).epub", "전지적 독자 시점"),
        ("금리낭자 1-141 (완).txt", "금리낭자"),
        ("나혼자만레벨업_001.txt", "나혼자만레벨업"),
    ]
    
    print("="*80)
    print("제목 추출 테스트")
    print("="*80)
    
    for filename, expected in test_cases:
        result = classifier.extract_title_from_filename(filename)
        status = "✅" if result == expected else "❌"
        print(f"\n{status} {filename}")
        print(f"   예상: {expected}")
        print(f"   결과: {result}")
        if result != expected:
            print(f"   ⚠️  불일치!")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    test_title_extraction()
