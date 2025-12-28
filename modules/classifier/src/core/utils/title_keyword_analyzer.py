"""
제목 키워드 기반 장르 분석
제목에 포함된 키워드로 장르 추정
"""

import json
import re
from pathlib import Path


class TitleKeywordAnalyzer:
    """제목 키워드 분석기"""
    
    def __init__(self, keywords_file: str = "genre_keywords.json"):
        """
        Args:
            keywords_file: 키워드 데이터 파일 경로
        """
        self.keywords_file = keywords_file
        self.keywords_data = self._load_keywords()
        
        # 특수 장르 키워드 (구체적인 키워드만)
        self.specific_genre_keywords = {
            "스포츠": [
                "축구", "야구", "농구", "복싱", "복서", "격투기",
                "킥복싱", "무에타이", "MMA", "UFC", "태권도", "유도",
                "배구", "테니스", "골프", "수영", "마라톤",
                "풋볼", "베이스볼", "바스켓볼",
                "투수", "타자", "골키퍼", "스트라이커",
                "리베로", "세터", "스파이커",
                "호타", "준족"
            ],
            "현판": [
                "아이돌", "작곡가", "가수", "배우", "연예인",
                "감독", "영화감독", "드라마감독", "애니메이션감독",
                "프로듀서", "매니저",
                "한의사", "의사", "변호사", "검사",
                "도예가", "화가", "요리사",
                "재벌", "회계사", "교수", "탐정", "징수"
            ],
            "역사": [
                "조선", "고려", "삼국", "삼국지", "고조선",
                "백제", "신라", "가야", "발해", "고구려",
                "임진왜란", "병자호란", "갑신정변", "동학농민운동",
                "광복", "독립운동", "항일",
                "세계대전", "2차대전", "1차대전",
                "나폴레옹", "히틀러", "무솔리니"
            ]
        }
    
    def _load_keywords(self) -> dict:
        """키워드 데이터 로드"""
        try:
            keywords_path = Path(self.keywords_file)
            if keywords_path.exists():
                with open(keywords_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"  [경고] 키워드 파일 로드 실패: {e}")
        
        return {}
    
    def analyze_title_keywords(self, title: str) -> dict:
        """제목에서 장르 키워드 추출 및 분석
        
        Args:
            title: 분석할 제목
            
        Returns:
            {
                'genre': str or None,
                'confidence': float (0.0 ~ 1.0),
                'matched_keywords': list,
                'reason': str
            }
        """
        title_lower = title.lower()
        
        # 1단계: 특수 장르 키워드 검사 (구체적인 키워드만)
        for genre, keywords in self.specific_genre_keywords.items():
            matched = []
            for keyword in keywords:
                if keyword in title or keyword.lower() in title_lower:
                    matched.append(keyword)
            
            if matched:
                return {
                    'genre': genre,
                    'confidence': 0.9,  # 높은 신뢰도
                    'matched_keywords': matched,
                    'reason': f"제목에 구체적인 {genre} 키워드 포함"
                }
        
        # 2단계: 일반 키워드 검사 (낮은 신뢰도)
        if not self.keywords_data:
            return {
                'genre': None,
                'confidence': 0.0,
                'matched_keywords': [],
                'reason': "키워드 데이터 없음"
            }
        
        single_keywords = self.keywords_data.get('single_keywords', {})
        genre_scores = {}
        genre_matches = {}
        
        for genre, keywords_dict in single_keywords.items():
            score = 0
            matches = []
            
            for keyword, weight in keywords_dict.items():
                if keyword in title:
                    score += weight
                    matches.append(keyword)
            
            if score > 0:
                genre_scores[genre] = score
                genre_matches[genre] = matches
        
        if genre_scores:
            best_genre = max(genre_scores, key=genre_scores.get)
            best_score = genre_scores[best_genre]
            
            # 일반 키워드는 낮은 신뢰도
            confidence = min(0.6, best_score / 20.0)
            
            return {
                'genre': best_genre,
                'confidence': confidence,
                'matched_keywords': genre_matches[best_genre],
                'reason': f"제목에 {best_genre} 키워드 포함 (낮은 신뢰도)"
            }
        
        return {
            'genre': None,
            'confidence': 0.0,
            'matched_keywords': [],
            'reason': "매칭되는 키워드 없음"
        }
