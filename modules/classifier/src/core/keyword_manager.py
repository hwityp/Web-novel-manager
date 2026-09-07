"""
통합 키워드 관리자
모든 분류 모듈이 이 클래스를 통해 키워드에 접근
"""
import sys
import os
import json

# Windows 콘솔 한글 깨짐 방지 (UTF-8 CP65001 강제 설정)
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


class KeywordManager:
    """통합 키워드 관리 클래스"""
    
    _instance = None
    _keywords = None
    
    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """초기화"""
        if self._keywords is None:
            self.load_keywords()
    
    def load_keywords(self):
        """JSON 파일에서 키워드 로드"""
        # 여러 경로 시도
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'data', 'genre_keywords.json'),  # src/data/
            os.path.join(os.path.dirname(__file__), 'genre_keywords.json'),  # src/core/
            os.path.join(os.path.dirname(__file__), '..', '..', 'genre_keywords.json'),  # 루트
        ]
        
        json_path = None
        for path in possible_paths:
            if os.path.exists(path):
                json_path = path
                break
        
        if json_path is None:
            raise FileNotFoundError("genre_keywords.json 파일을 찾을 수 없습니다.")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            self._keywords = json.load(f)
        print(f"[KeywordManager] 키워드 로드 완료 (버전: {self._keywords['version']})")
    
    def get_single_keywords(self, genre=None):
        """단일 키워드 가져오기"""
        if genre:
            return self._keywords['single_keywords'].get(genre, {})
        return self._keywords['single_keywords']
    
    def get_compound_patterns(self, genre=None):
        """복합 패턴 가져오기"""
        if genre:
            return self._keywords['compound_patterns'].get(genre, [])
        return self._keywords['compound_patterns']
    
    def get_all_compound_patterns_dict(self):
        """복합 패턴을 딕셔너리 형태로 변환"""
        result = {}
        for genre, patterns in self._keywords['compound_patterns'].items():
            for pattern in patterns:
                kw1, kw2, conf = pattern
                result[(kw1, kw2)] = (genre, conf)
        return result
    
    def get_special_cases(self):
        """특수 케이스 가져오기"""
        return self._keywords['special_cases']
    
    def get_validation_keywords(self, genre):
        """검증 키워드 가져오기"""
        return self._keywords['validation_keywords'].get(genre, [])
    
    def get_fantasy_separation_keywords(self, genre):
        """판타지 세분화 키워드 가져오기"""
        return self._keywords['fantasy_separation_keywords'].get(genre, [])
    
    def get_all_keywords_for_genre(self, genre):
        """특정 장르의 모든 키워드 가져오기 (단일 + 복합)"""
        keywords = set()
        
        # 단일 키워드
        single = self.get_single_keywords(genre)
        keywords.update(single.keys())
        
        # 복합 패턴
        patterns = self.get_compound_patterns(genre)
        for pattern in patterns:
            keywords.add(pattern[0])
            keywords.add(pattern[1])
        
        return list(keywords)
    
    def check_keyword_match(self, text, genre):
        """텍스트에 특정 장르의 키워드가 있는지 확인"""
        text_lower = text.lower()
        keywords = self.get_single_keywords(genre)
        
        matched = []
        for keyword, weight in keywords.items():
            if keyword in text_lower:
                matched.append((keyword, weight))
        
        return matched
    
    def check_compound_pattern_match(self, text, genre):
        """텍스트에 특정 장르의 복합 패턴이 있는지 확인"""
        text_lower = text.lower()
        patterns = self.get_compound_patterns(genre)
        
        for pattern in patterns:
            kw1, kw2, conf = pattern
            if kw1 in text_lower and kw2 in text_lower:
                return (kw1, kw2, conf)
        
        return None
    
    def calculate_scores(self, text, genre=None, normalize=False):
        """
        주어진 텍스트에서 키워드를 매칭하여 각 장르별 점수를 계산
        
        Args:
            text (str): 분석할 소설 제목 또는 텍스트
            genre (str, optional): 특정 장르만 점수를 계산할 경우 지정 (기본값: None)
            normalize (bool, optional): 키워드 수 기반 정규화 여부 (기본값: False)
            
        Returns:
            dict or float: genre가 지정되면 해당 장르의 float 점수,
                          genre가 None이면 점수 내림차순 정렬된 dict {genre: score, ...}
        """
        if not text or not isinstance(text, str):
            if genre:
                return 0.0
            single_kw = self._keywords.get('single_keywords', {}) if self._keywords else {}
            return {g: 0.0 for g in single_kw.keys()}
        
        text_lower = text.lower()
        single_kw_dict = self._keywords.get('single_keywords', {}) if self._keywords else {}
        all_genres = list(single_kw_dict.keys())
        
        genre_scores = {g: 0.0 for g in all_genres}
        
        # 1. 복합 패턴 매칭 (높은 가중치 부여)
        compound_patterns_dict = self.get_all_compound_patterns_dict()
        for (kw1, kw2), (p_genre, conf) in compound_patterns_dict.items():
            if kw1.lower() in text_lower and kw2.lower() in text_lower:
                if p_genre in genre_scores:
                    genre_scores[p_genre] += conf
                else:
                    genre_scores[p_genre] = conf
        
        # 2. 특수 케이스 매칭
        special_cases = self.get_special_cases()
        for sc_title, sc_genre in special_cases.items():
            if sc_title.lower() in text_lower:
                if isinstance(sc_genre, str):
                    if sc_genre in genre_scores:
                        genre_scores[sc_genre] += 30.0
                    else:
                        genre_scores[sc_genre] = 30.0
                elif isinstance(sc_genre, dict):
                    for g, w in sc_genre.items():
                        genre_scores[g] = genre_scores.get(g, 0.0) + w
        
        # 3. 단일 키워드 매칭
        for g in all_genres:
            keywords = single_kw_dict.get(g, {})
            # 긴 키워드부터 매칭 (예: '남궁세가' -> '남궁')
            sorted_keywords = sorted(keywords.items(), key=lambda x: len(x[0]), reverse=True)
            matched_keywords_set = set()
            
            for keyword, weight in sorted_keywords:
                if len(keyword) < 2:
                    continue
                
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    # 특수 케이스: '무공'은 '충무공'에 포함되면 무시
                    if keyword == '무공' and '충무공' in text_lower:
                        continue
                    
                    # 이미 매칭된 더 긴 키워드에 포함되는 부분 문자열이면 스킵
                    is_sub = False
                    for m_kw in matched_keywords_set:
                        if keyword_lower in m_kw and keyword_lower != m_kw:
                            is_sub = True
                            break
                    if is_sub:
                        continue
                    
                    genre_scores[g] += float(weight)
                    matched_keywords_set.add(keyword_lower)
        
        # 4. 정규화 (선택적)
        if normalize:
            for g in all_genres:
                kw_count = len(single_kw_dict.get(g, {}))
                if kw_count > 0:
                    genre_scores[g] = genre_scores[g] / (kw_count ** 0.5)
        
        # 소수점 둘째자리 반올림
        for g in genre_scores:
            genre_scores[g] = round(genre_scores[g], 2)
            
        if genre:
            return genre_scores.get(genre, 0.0)
            
        # 점수 내림차순 정렬된 딕셔너리 반환
        return dict(sorted(genre_scores.items(), key=lambda x: x[1], reverse=True))
    
    def get_version(self):
        """키워드 버전 정보"""
        return self._keywords['version']
    
    def get_last_updated(self):
        """마지막 업데이트 날짜"""
        return self._keywords['last_updated']
    
    def get_blog_community_keywords(self, genre=None):
        """블로그/커뮤니티 키워드 가져오기"""
        if genre:
            return self._keywords.get('blog_community_keywords', {}).get(genre, [])
        return self._keywords.get('blog_community_keywords', {})


# 전역 인스턴스
keyword_manager = KeywordManager()


if __name__ == '__main__':
    # 테스트
    km = KeywordManager()
    print(f"버전: {km.get_version()}")
    print(f"마지막 업데이트: {km.get_last_updated()}")
    print(f"\n무협 키워드: {list(km.get_single_keywords('무협').keys())[:10]}")
    print(f"\n현판 복합 패턴: {km.get_compound_patterns('현판')[:5]}")
    print(f"\n'무공 시스템' 매칭: {km.check_compound_pattern_match('무공 시스템', '무협')}")
