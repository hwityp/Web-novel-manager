"""
제목 유사도 매칭 유틸리티
약간의 오차가 있어도 같은 제목으로 인식
"""

from difflib import SequenceMatcher
import re


def normalize_title_for_matching(title: str) -> str:
    """매칭을 위한 제목 정규화
    
    - 공백 제거
    - 특수문자 제거
    - 소문자 변환
    """
    # 특수문자 제거
    title = re.sub(r'[^\w가-힣]', '', title)
    # 공백 제거
    title = title.replace(' ', '')
    # 소문자 변환
    title = title.lower()
    return title


def calculate_similarity(str1: str, str2: str) -> float:
    """두 문자열의 유사도 계산 (0.0 ~ 1.0)
    
    Args:
        str1: 첫 번째 문자열
        str2: 두 번째 문자열
        
    Returns:
        유사도 (0.0 ~ 1.0)
    """
    if not str1 or not str2:
        return 0.0
    
    # 정규화
    norm1 = normalize_title_for_matching(str1)
    norm2 = normalize_title_for_matching(str2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # SequenceMatcher로 유사도 계산
    return SequenceMatcher(None, norm1, norm2).ratio()


def is_similar_title(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """두 제목이 유사한지 판단
    
    Args:
        title1: 첫 번째 제목
        title2: 두 번째 제목
        threshold: 유사도 임계값 (기본값: 0.85)
        
    Returns:
        유사 여부
        
    Examples:
        >>> is_similar_title("영웅왕 그 미래는", "영웅왕 그의 미래는")
        True
        >>> is_similar_title("영마스터여행기", "영 마스터 여행기")
        True
        >>> is_similar_title("올 리셋 라이프", "올리셋라이프")
        True
    """
    similarity = calculate_similarity(title1, title2)
    return similarity >= threshold


def find_best_match(target_title: str, candidate_titles: list, threshold: float = 0.85) -> tuple:
    """후보 제목 중 가장 유사한 제목 찾기
    
    Args:
        target_title: 찾고자 하는 제목
        candidate_titles: 후보 제목 리스트
        threshold: 유사도 임계값
        
    Returns:
        (best_match, similarity) 또는 (None, 0.0)
    """
    best_match = None
    best_similarity = 0.0
    
    for candidate in candidate_titles:
        similarity = calculate_similarity(target_title, candidate)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = candidate
    
    if best_similarity >= threshold:
        return (best_match, best_similarity)
    else:
        return (None, 0.0)
