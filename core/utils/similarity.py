"""
Title Similarity Checker

Levenshtein Distance 알고리즘을 사용하여 제목 유사도를 검증합니다.
검색 결과의 작품명이 원본 제목과 충분히 유사한지 확인하여 오분류를 방지합니다.

Validates: Requirements 10.1, 10.2, 10.3, 10.4
"""
import re
from typing import Tuple


class TitleSimilarityChecker:
    """제목 유사도 검증 클래스"""
    
    # 기본 유사도 임계값
    DEFAULT_THRESHOLD = 0.85  # 85%
    
    # 저자명 일치 시 완화된 임계값
    AUTHOR_MATCH_THRESHOLD = 0.75  # 75%
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        두 문자열 간의 Levenshtein Distance 계산
        
        Args:
            s1: 첫 번째 문자열
            s2: 두 번째 문자열
            
        Returns:
            편집 거리 (삽입, 삭제, 대체 연산의 최소 횟수)
        """
        if len(s1) < len(s2):
            return TitleSimilarityChecker.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # 삽입, 삭제, 대체 중 최소 비용 선택
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """
        제목 정규화 (비교를 위한 전처리)
        
        - 소문자 변환
        - 공백 정규화
        - 특수문자 제거
        
        Args:
            title: 원본 제목
            
        Returns:
            정규화된 제목
        """
        if not title:
            return ""
        
        # 소문자 변환
        normalized = title.lower()
        
        # 특수문자 제거 (한글, 영문, 숫자만 유지)
        normalized = re.sub(r'[^\w\s가-힣]', '', normalized)
        
        # 연속 공백을 단일 공백으로
        normalized = ' '.join(normalized.split())
        
        return normalized.strip()
    
    @classmethod
    def calculate_similarity(cls, title1: str, title2: str) -> float:
        """
        두 제목의 유사도 계산 (Levenshtein Distance 기반)
        
        Args:
            title1: 원본 제목
            title2: 비교 대상 제목
            
        Returns:
            0.0 ~ 1.0 사이의 유사도 (1.0 = 완전 일치)
        """
        # 정규화
        norm1 = cls.normalize_title(title1)
        norm2 = cls.normalize_title(title2)
        
        # 빈 문자열 처리
        if not norm1 and not norm2:
            return 1.0
        if not norm1 or not norm2:
            return 0.0
        
        # Levenshtein Distance 계산
        distance = cls.levenshtein_distance(norm1, norm2)
        
        # 유사도 계산 (1 - 정규화된 거리)
        max_len = max(len(norm1), len(norm2))
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, min(1.0, similarity))
    
    @classmethod
    def is_similar(cls, title1: str, title2: str, author_match: bool = False) -> bool:
        """
        제목이 충분히 유사한지 확인
        
        Args:
            title1: 원본 제목
            title2: 비교 대상 제목
            author_match: 저자명 일치 여부 (True면 임계값 완화)
            
        Returns:
            유사도가 임계값 이상이면 True
        """
        threshold = cls.AUTHOR_MATCH_THRESHOLD if author_match else cls.DEFAULT_THRESHOLD
        similarity = cls.calculate_similarity(title1, title2)
        return similarity >= threshold
    
    @classmethod
    def check_similarity_with_details(cls, title1: str, title2: str, 
                                       author_match: bool = False) -> Tuple[bool, float, float]:
        """
        유사도 검사 결과와 상세 정보 반환
        
        Args:
            title1: 원본 제목
            title2: 비교 대상 제목
            author_match: 저자명 일치 여부
            
        Returns:
            (is_similar, similarity, threshold) 튜플
        """
        threshold = cls.AUTHOR_MATCH_THRESHOLD if author_match else cls.DEFAULT_THRESHOLD
        similarity = cls.calculate_similarity(title1, title2)
        is_similar = similarity >= threshold
        
        return is_similar, similarity, threshold
