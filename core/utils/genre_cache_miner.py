"""
==============================================================================
파일: core/utils/genre_cache_miner.py
역할 및 목적:
    `config/genre_cache.json`에 축적된 고신뢰도(high confidence) 검색 결과 및
    사용자 수동 수정 이력으로부터 신규 장르 키워드와 중국어 음독/번역투 패턴을
    자동으로 마이닝하고 분석하여 승인 대기 후보군(candidate_keywords.json)을 도출하는 모듈.
주요 구성 요소:
    - GenreCandidate: 추출된 키워드 후보 데이터클래스
    - GenreCacheMiner: 캐시 마이닝 및 장르 독점도(Purity) 계산 엔진
==============================================================================
"""
import re
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict


@dataclass
class GenreCandidate:
    """추출된 신규 장르 키워드 후보"""
    keyword: str
    genre: str
    count: int
    purity: float               # 해당 장르 출현 독점도 (0.0 ~ 1.0)
    suggested_weight: int       # 제안 가중치 (1 ~ 8, 안전 상한선 준수)
    source_type: str            # 'cjk_pair', 'ngram', 'phonetic_prefix'
    cjk_source: Optional[str] = None  # 원문 CJK 한자 표기 (존재하는 경우)


class GenreCacheMiner:
    """장르 캐시 데이터 마이닝 및 신규 패턴 분석기"""

    # 기본 불용어 (일반 조사, 관용어, 확장자 등)
    DEFAULT_STOPWORDS = {
        '다운로드', '텍본', '완결', '전권', '외전', '시즌', '화', '권',
        '이야기', '시작', '정말', '사람', '하루', '세계', '다시', '어느',
        '내가', '나의', '그의', '그녀', '우리', '모든', '대한', '위한',
        '그리고', '하지만', '위해', '에서', '으로', '까지', '부터'
    }

    # CJK 괄호 태그 정규식: (我真没想...), [乱世书] 등
    CJK_BRACKET_REGEX = re.compile(r'[\(\[\{]([\u4e00-\u9fff\u3400-\u4dbf]+)[\)\]\}]')

    # 한글 및 알파벳 단어 추출 정규식
    WORD_REGEX = re.compile(r'[가-힣a-zA-Z0-9]+')

    # 한국어 주요 조사 접미사
    JOSA_REGEX = re.compile(r'(?:으로|에서|부터|까지|하고|이며|의|을|를|은|는|이|가|에|과|와|로)$')

    def __init__(self, cache_file: Optional[Path] = None, stopwords: Optional[Set[str]] = None):
        self.cache_file = cache_file or Path("config/genre_cache.json")
        self.stopwords = set(self.DEFAULT_STOPWORDS)
        if stopwords:
            self.stopwords.update(stopwords)

    def _strip_josa(self, word: str) -> str:
        """단어 끝의 조사 제거 (예: '수선자의' -> '수선자', '부자가' -> '부자')"""
        if len(word) >= 3:
            stripped = self.JOSA_REGEX.sub('', word)
            if len(stripped) >= 2:
                return stripped
        return word

    def load_cache_entries(self) -> Dict[str, Dict]:
        """캐시 파일에서 엔트리 로드"""
        if not self.cache_file.exists():
            return {}
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('entries', {})
        except Exception as e:
            print(f"[GenreCacheMiner] 캐시 파일 로드 실패: {e}")
            return {}

    def extract_cjk_pairs(self, title: str) -> List[Tuple[str, str]]:
        """
        제목에서 괄호 표기 CJK 원문과 한글 음독/제목 쌍 추출
        예: '이신몰상(我真没想) ...' -> [('我真没想', '이신몰상')]
        """
        matches = self.CJK_BRACKET_REGEX.findall(title)
        pairs = []
        for cjk in matches:
            # 괄호 앞의 한글 어휘 탐색
            before_cjk = title.split(cjk)[0].rstrip('([<{ ')
            korean_words = self.WORD_REGEX.findall(before_cjk)
            if korean_words:
                phonetic_hangul = korean_words[-1]
                if len(phonetic_hangul) >= 2:
                    pairs.append((cjk, phonetic_hangul))
        return pairs

    def mine(self, min_count: int = 1, min_purity: float = 0.6) -> List[GenreCandidate]:
        """
        캐시 데이터를 분석하여 장르 후보 키워드 목록 생성
        
        Args:
            min_count: 최소 출현 빈도 (기본 1회)
            min_purity: 최소 장르 독점도 (기본 0.6)
            
        Returns:
            List[GenreCandidate]: 정렬된 후보군 목록
        """
        entries = self.load_cache_entries()
        if not entries:
            return []

        # 단어별 장르 카운트: word -> {genre: count}
        word_genre_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        word_cjk_sources: Dict[str, str] = {}
        word_sources: Dict[str, str] = {}

        for title, info in entries.items():
            genre_str = info.get('genre', '')
            confidence = info.get('confidence', '')
            
            # 신뢰도가 너무 낮거나 미분류인 경우는 단어 학습에서 제외
            if confidence == 'none' or not genre_str or genre_str == '미분류':
                continue

            # 대표 1차 장르 추출 (예: '퓨판, 종말' -> '퓨판')
            primary_genre = [g.strip() for g in genre_str.split(',') if g.strip()][0]

            # 1. CJK 원문-음독 쌍 탐색
            cjk_pairs = self.extract_cjk_pairs(title)
            for cjk, hangul in cjk_pairs:
                if hangul not in self.stopwords and len(hangul) >= 2:
                    word_genre_counts[hangul][primary_genre] += 2 # CJK 페어는 가중치 추가
                    word_cjk_sources[hangul] = cjk
                    word_sources[hangul] = 'cjk_pair'

            # 2. 어절/단어 n-gram 탐색
            cleaned_title = self.CJK_BRACKET_REGEX.sub('', title)
            words = self.WORD_REGEX.findall(cleaned_title)
            
            for w in words:
                w_clean = self._strip_josa(w.strip())
                if len(w_clean) < 2 or w_clean in self.stopwords:
                    continue
                # 순수 숫자는 제외
                if w_clean.isdigit():
                    continue
                word_genre_counts[w_clean][primary_genre] += 1
                if w_clean not in word_sources:
                    word_sources[w_clean] = 'ngram'

        # 후보군 계산
        candidates: List[GenreCandidate] = []
        for word, genres in word_genre_counts.items():
            total_count = sum(genres.values())
            if total_count < min_count:
                continue

            # 가장 많이 출현한 장르 선정
            top_genre, top_count = max(genres.items(), key=lambda item: item[1])
            purity = top_count / total_count

            if purity < min_purity:
                continue

            # 가중치 자동 계산 (안전 상한선: 8점)
            if purity >= 0.9 and total_count >= 2:
                suggested_weight = 8
            elif purity >= 0.8:
                suggested_weight = 7
            elif purity >= 0.7:
                suggested_weight = 6
            else:
                suggested_weight = 5

            candidate = GenreCandidate(
                keyword=word,
                genre=top_genre,
                count=total_count,
                purity=round(purity, 2),
                suggested_weight=suggested_weight,
                source_type=word_sources.get(word, 'ngram'),
                cjk_source=word_cjk_sources.get(word)
            )
            candidates.append(candidate)

        # 정렬: 빈도수 내림차순 -> 순도 내림차순
        candidates.sort(key=lambda c: (c.count, c.purity), reverse=True)
        return candidates

    def export_candidates(self, output_path: Path, candidates: Optional[List[GenreCandidate]] = None) -> bool:
        """후보군 목록을 JSON 파일로 내보내기"""
        if candidates is None:
            candidates = self.mine()
        
        output_data = {
            "version": "1.0.0",
            "candidate_count": len(candidates),
            "candidates": [asdict(c) for c in candidates]
        }
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[GenreCacheMiner] 후보군 내보내기 실패: {e}")
            return False
