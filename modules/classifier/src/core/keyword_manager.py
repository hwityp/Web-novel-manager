"""
통합 키워드 관리자
모든 분류 모듈이 이 클래스를 통해 키워드에 접근
"""
import json
import os


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
