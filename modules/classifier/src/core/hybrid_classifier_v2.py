"""
하이브리드 장르 분류기 V2 (개선 버전)
1. 키워드 기반 분류
2. 네이버 검색 기반 분류
3. 신뢰도 임계값 적용
4. 특수 케이스 처리
5. 네이버 결과 재매핑
6. 제목 키워드 분석 (v1.3.9)
7. 제목 유사도 매칭 (v1.3.9)
8. 저자명 기반 장르 추론 (v1.3.9)
"""
from modules.classifier.src.core.genre_classifier import GenreClassifier
from modules.classifier.src.core.naver_genre_extractor_v4 import NaverGenreExtractorV4
from modules.classifier.src.core.keyword_manager import KeywordManager
from modules.classifier.src.core.utils.title_keyword_analyzer import TitleKeywordAnalyzer
from modules.classifier.src.core.utils.author_genre_db import get_author_db


class HybridClassifier:
    """하이브리드 장르 분류기 V2"""
    
    # 신뢰도 임계값
    CONFIDENCE_THRESHOLD = 0.40  # 40% 미만은 미분류
    
    # 레거시 하드코딩 제거됨 - genre_keywords.json에서 관리
    # 특수 케이스와 복합 패턴은 KeywordManager에서 로드
    """
    SPECIAL_CASES_LEGACY = {
        # 삭제됨 - genre_keywords.json의 special_cases 사용
    }
    
    COMPOUND_PATTERNS_LEGACY = {
        # 삭제됨 - genre_keywords.json의 compound_patterns 사용
    }
    """
    
    def __init__(self):
        self.keyword_classifier = GenreClassifier()
        self.naver_extractor = NaverGenreExtractorV4()
        
        # KeywordManager 초기화
        self.keyword_mgr = KeywordManager()
        
        # KeywordManager에서 데이터 로드
        self.SPECIAL_CASES = self.keyword_mgr.get_special_cases()
        self.COMPOUND_PATTERNS = self.keyword_mgr.get_all_compound_patterns_dict()
        
        # 제목 키워드 분석기 초기화 (v1.3.9)
        self.title_keyword_analyzer = TitleKeywordAnalyzer()
        
        # 저자명 DB 초기화 (v1.3.9)
        self.author_db = get_author_db()
        
        print(f"[HybridClassifier] KeywordManager 통합 완료 (버전: {self.keyword_mgr.get_version()})")
        print(f"[HybridClassifier] 제목 키워드 분석기 초기화 완료 (v1.3.9)")
        print(f"[HybridClassifier] 저자명 DB 초기화 완료 ({len(self.author_db.get_all_authors())}명 등록)")
    
    def classify(self, title, description="", use_naver=True, naver_api_config=None):
        """
        하이브리드 장르 분류 (개선 버전)
        
        Args:
            title: 소설 제목
            description: 소설 설명 (선택)
            use_naver: 네이버 검색 사용 여부
            naver_api_config: 네이버 API 설정 (dict with 'client_id', 'client_secret')
            
        Returns:
            {
                'genre': 최종 장르,
                'confidence': 신뢰도,
                'method': 사용된 방법,
                'keyword_result': 키워드 분류 결과,
                'naver_result': 네이버 검색 결과
            }
        """
        # 구분선 출력 (새 작품 시작)
        print()
        print("=" * 80)
        print()
        
        # 0-1. 저자명 추출 (v1.3.9)
        from modules.classifier.src.core.utils.title_utils import parse_title_info
        title_info = parse_title_info(title)
        author = title_info.get('author')
        
        # 0-2. 저자명 기반 장르 추론 (네이버 검색 전에 시도)
        if author:
            author_genre = self.author_db.get_genre_by_author(author)
            if author_genre:
                # 저자명 DB 조회 결과 로그 (제목 분석 직후)
                print(f"  [저자명 DB] '{author}' → {author_genre} (신뢰도: 85%)")
                
                # 저자명만으로는 확정하지 않고, 네이버 검색 실패 시 사용하기 위해 저장
                author_genre_hint = {
                    'genre': author_genre,
                    'confidence': 0.85,
                    'author': author
                }
            else:
                author_genre_hint = None
        else:
            author_genre_hint = None
        
        # 0-3. 네이버 검색 우선 (공식 플랫폼 정보가 가장 정확)
        naver_result = None
        if use_naver:
            # API 설정이 있으면 새로운 extractor 생성
            if naver_api_config:
                from modules.classifier.src.core.naver_genre_extractor_v4 import NaverGenreExtractorV4
                extractor = NaverGenreExtractorV4(naver_api_config=naver_api_config)
                naver_result = extractor.extract_genre_from_title(title)
            else:
                naver_result = self.naver_extractor.extract_genre_from_title(title)
            
            # 네이버 결과가 있고 신뢰도가 높으면 사용
            # 네이버시리즈/카카오페이지는 2차 재매핑이 필요하므로 신뢰도 기준 완화 (80%)
            # search_titles(블로그/커뮤니티 제목 추출)는 더 완화 (60%)
            source = naver_result.get('source', '') if naver_result else ''
            confidence_threshold = 0.60 if source == 'search_titles' else 0.80
            
            if naver_result and naver_result['genre'] and naver_result['confidence'] >= confidence_threshold:
                original_genre = naver_result['genre']
                source = naver_result.get('source', '')
                
                # naver_genre_extractor_v3에서 이미 제목 키워드 재매핑 완료
                # 여기서는 추가 재매핑 안 함
                remapped_genre = original_genre
                
                # 2차 재매핑: 광범위한 장르를 키워드 분류기로 세분화
                needs_second_remap = False
                remap_reason = ""
                remap_mode = ""  # "sports_only" 또는 "fantasy_full" 또는 "hyunpan_sports"
                allowed_genres = []
                
                # 네이버시리즈: "판타지", "현판" 세분화
                # 제공 장르: 로맨스, 로판, 판타지, 현판, 무협, 미스터리, 라이트노벨, BL
                # 미제공: 선협, 언정, 퓨판, 겜판, 역사, 스포츠
                if 'naver_series' in source:
                    if remapped_genre == '판타지':
                        needs_second_remap = True
                        remap_reason = "네이버시리즈 '판타지' 세분화"
                        remap_mode = "fantasy_full"
                        # 퓨판, 겜판, 역사, 판타지만 허용 (현판/무협/로판은 별도 제공)
                        allowed_genres = ['퓨판', '겜판', '역사', '판타지']
                    elif remapped_genre == '현판':
                        needs_second_remap = True
                        remap_reason = "네이버시리즈 '현판' (스포츠 분리)"
                        remap_mode = "hyunpan_sports"
                        # 스포츠, 현판만 허용
                        allowed_genres = ['스포츠', '현판']
                
                # 카카오페이지: "판타지", "현판" 세분화
                # 제공 장르: 판타지, 현판, 무협, 로판, 로맨스, BL
                # 미제공: 선협, 언정, 퓨판, 겜판, 역사, 스포츠, 미스터리, 라이트노벨
                elif 'kakao' in source:
                    if remapped_genre == '판타지':
                        needs_second_remap = True
                        remap_reason = "카카오페이지 '판타지' 세분화"
                        remap_mode = "fantasy_full"
                        # 퓨판, 겜판, 역사, 판타지만 허용 (현판/무협/로판은 별도 제공)
                        allowed_genres = ['퓨판', '겜판', '역사', '판타지']
                    elif remapped_genre == '현판':
                        needs_second_remap = True
                        remap_reason = "카카오페이지 '현판' (스포츠 분리)"
                        remap_mode = "hyunpan_sports"
                        # 스포츠, 현판만 허용
                        allowed_genres = ['스포츠', '현판']
                
                # 리디북스: "현판" 세분화 (스포츠 분리), "퓨판" 세분화 (겜판/역사 분리)
                elif 'ridibooks' in source:
                    if remapped_genre == '현판':
                        needs_second_remap = True
                        remap_reason = "리디북스 '현판' (스포츠 분리)"
                        remap_mode = "hyunpan_sports"
                        # 스포츠, 현판만 허용
                        allowed_genres = ['스포츠', '현판']
                    elif remapped_genre == '퓨판':
                        needs_second_remap = True
                        remap_reason = "리디북스 '퓨판' (겜판/역사 분리)"
                        remap_mode = "fusion_game_history"
                        # 겜판, 역사, 퓨판만 허용
                        allowed_genres = ['겜판', '역사', '퓨판']
                
                if needs_second_remap:
                    print(f"  [2차 재매핑 필요] {remap_reason}")
                
                if needs_second_remap:
                    # 키워드 분류기로 세분화
                    text = f"{title} {description}"
                    keyword_result = self.keyword_classifier.classify_with_confidence(text)
                    
                    # 키워드 분류 결과 로그
                    print(f"  [키워드 분류 결과] {keyword_result['primary_genre']} ({keyword_result['confidence']:.0%})")
                    
                    # 현판 → 스포츠 분리 모드
                    if remap_mode == "hyunpan_sports":
                        if keyword_result['primary_genre'] == '스포츠' and keyword_result['confidence'] >= 0.70:
                            final_genre = '스포츠'
                            if 'naver_series' in source:
                                source_name = "네이버시리즈"
                            elif 'kakao' in source:
                                source_name = "카카오페이지"
                            else:
                                source_name = "리디북스"
                            print(f"  [2차 재매핑] {remapped_genre} → {final_genre} (키워드 분류: {keyword_result['confidence']:.0%})")
                            print(f"  [네이버 검색 결과] {final_genre} ({min(naver_result['confidence'], keyword_result['confidence'] + 0.1):.0%}, {source}_sports_refined)")
                            print(f"  [최종선택] {source_name}(스포츠 분리): {final_genre}")
                            print()  # 공백 줄
                            
                            return {
                                'genre': final_genre,
                                'confidence': min(naver_result['confidence'], keyword_result['confidence'] + 0.1),
                                'method': f"{source.replace('_', '')}_sports_refined",
                                'keyword_result': keyword_result,
                                'naver_result': naver_result
                            }
                        else:
                            if keyword_result['primary_genre'] == '스포츠':
                                print(f"  [2차 재매핑 실패] 스포츠이지만 신뢰도 낮음 ({keyword_result['confidence']:.0%} < 70%), {remapped_genre} 유지")
                            else:
                                print(f"  [2차 재매핑 실패] 스포츠 아님, {remapped_genre} 유지")
                            
                            # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                            print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                            print()  # 공백 줄
                    
                    # 판타지 세분화 모드
                    elif remap_mode == "fantasy_full":
                        # 현판 → 퓨판 변환 (판타지 세분화 시)
                        # 카카오페이지/네이버시리즈는 현판을 별도 제공하지만,
                        # "판타지"를 세분화할 때 현판 키워드가 감지되면 퓨판으로 처리
                        classified_genre = keyword_result['primary_genre']
                        converted_from_hyunpan = False
                        if classified_genre == '현판':
                            classified_genre = '퓨판'
                            converted_from_hyunpan = True
                            print(f"  [장르 변환] 현판 → 퓨판 (판타지 세분화)")
                        
                        # 허용 장르 체크
                        if classified_genre not in allowed_genres:
                            # 판타지 세분화 대상(퓨판, 겜판, 역사, 판타지) 외의 장르가 감지된 경우
                            # → 판타지 + 다른 장르 = 퓨판으로 판정
                            # 예: 카카오페이지에서 "판타지"인데 키워드가 "무협" → 퓨판
                            # 예: 카카오페이지에서 "판타지"인데 키워드가 "선협" → 퓨판
                            if keyword_result['confidence'] >= 0.60:
                                final_genre = '퓨판'
                                source_name = "카카오페이지" if 'kakao' in source else "네이버시리즈"
                                print(f"  [판타지 + 다른 장르] 판타지 + {classified_genre} → 퓨판")
                                print(f"  [2차 재매핑] {remapped_genre} → {final_genre} (키워드: {classified_genre}, 신뢰도: {keyword_result['confidence']:.0%})")
                                print(f"  [네이버 검색 결과] {final_genre} ({min(naver_result['confidence'], keyword_result['confidence']):.0%}, {source}_fusion_refined)")
                                print(f"  [최종선택] {source_name}(퓨전 판정): {final_genre}")
                                print()  # 공백 줄
                                
                                return {
                                    'genre': final_genre,
                                    'confidence': min(naver_result['confidence'], keyword_result['confidence']),
                                    'method': f"{source.replace('_', '')}_fusion_refined",
                                    'keyword_result': keyword_result,
                                    'naver_result': naver_result
                                }
                            else:
                                print(f"  [2차 재매핑 실패] {classified_genre} 감지되었으나 신뢰도 낮음 ({keyword_result['confidence']:.0%} < 60%), {remapped_genre} 유지")
                                
                                # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                                print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                                print()  # 공백 줄
                        else:
                            # 신뢰도 임계값 결정
                            if classified_genre == '퓨판':
                                threshold = 0.60  # 퓨판은 완화된 기준
                            elif classified_genre == '판타지':
                                threshold = 0.50  # 판타지는 기본 장르이므로 더 완화
                            else:
                                threshold = 0.70  # 겜판, 역사는 완화된 기준 (75% → 70%)
                            
                            if classified_genre == '미분류' or keyword_result['confidence'] < threshold:
                                print(f"  [2차 재매핑 실패] 키워드 신뢰도 낮음 ({keyword_result['confidence']:.0%} < {threshold:.0%}), {remapped_genre} 유지")
                                
                                # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                                print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                                print()  # 공백 줄
                            else:
                                final_genre = classified_genre
                                
                                # 장르별 강력한 키워드 검증
                                # 현판 → 퓨판 변환의 경우 검증 건너뛰기 (키워드 분류기가 이미 현판을 감지함)
                                if converted_from_hyunpan:
                                    validation_result = {'valid': True, 'reason': '현판 키워드 감지 (퓨판으로 변환)'}
                                else:
                                    validation_result = self._validate_genre_remapping(title, final_genre, keyword_result['confidence'])
                                
                                if validation_result['valid']:
                                    source_name = "카카오페이지" if 'kakao' in source else "네이버시리즈"
                                    print(f"  [2차 재매핑] {remapped_genre} → {final_genre} (키워드 분류: {keyword_result['confidence']:.0%})")
                                    print(f"  [검증 통과] {validation_result['reason']}")
                                    print(f"  [네이버 검색 결과] {final_genre} ({min(naver_result['confidence'], keyword_result['confidence']):.0%}, {source}_keyword_refined)")
                                    print(f"  [최종선택] {source_name}(2차 재매핑): {final_genre}")
                                    print()  # 공백 줄
                                    
                                    return {
                                        'genre': final_genre,
                                        'confidence': min(naver_result['confidence'], keyword_result['confidence']),
                                        'method': f"{source.replace('_', '')}_keyword_refined",
                                        'keyword_result': keyword_result,
                                        'naver_result': naver_result
                                    }
                                else:
                                    print(f"  [2차 재매핑 실패] {validation_result['reason']}, {remapped_genre} 유지")
                                    
                                    # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                                    print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                                    print()  # 공백 줄
                    
                    # 퓨판 → 겜판/역사 분리 모드 (리디북스)
                    elif remap_mode == "fusion_game_history":
                        print(f"  [디버깅] fusion_game_history 모드 진입")
                        print(f"  [디버깅] 키워드 장르: {keyword_result['primary_genre']}, 신뢰도: {keyword_result['confidence']:.0%}")
                        
                        # 겜판 분리 (신뢰도 70% 이상)
                        if keyword_result['primary_genre'] == '겜판' and keyword_result['confidence'] >= 0.70:
                            final_genre = '겜판'
                            
                            # 겜판 키워드 검증
                            validation_result = self._validate_genre_remapping(title, final_genre, keyword_result['confidence'])
                            
                            if validation_result['valid']:
                                print(f"  [2차 재매핑] {remapped_genre} → {final_genre} (키워드 분류: {keyword_result['confidence']:.0%})")
                                print(f"  [검증 통과] {validation_result['reason']}")
                                print(f"  [네이버 검색 결과] {final_genre} ({min(naver_result['confidence'], keyword_result['confidence']):.0%}, ridibooks_game_refined)")
                                print(f"  [최종선택] 리디북스(겜판 분리): {final_genre}")
                                print()  # 공백 줄
                                
                                return {
                                    'genre': final_genre,
                                    'confidence': min(naver_result['confidence'], keyword_result['confidence']),
                                    'method': 'ridibooks_game_refined',
                                    'keyword_result': keyword_result,
                                    'naver_result': naver_result
                                }
                            else:
                                print(f"  [2차 재매핑 실패] {validation_result['reason']}, {remapped_genre} 유지")
                                
                                # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                                print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                                print()  # 공백 줄
                        
                        # 역사 분리 (신뢰도 70% 이상)
                        elif keyword_result['primary_genre'] == '역사' and keyword_result['confidence'] >= 0.70:
                            final_genre = '역사'
                            
                            # 역사 키워드 검증
                            validation_result = self._validate_genre_remapping(title, final_genre, keyword_result['confidence'])
                            
                            if validation_result['valid']:
                                print(f"  [2차 재매핑] {remapped_genre} → {final_genre} (키워드 분류: {keyword_result['confidence']:.0%})")
                                print(f"  [검증 통과] {validation_result['reason']}")
                                print(f"  [네이버 검색 결과] {final_genre} ({min(naver_result['confidence'], keyword_result['confidence']):.0%}, ridibooks_history_refined)")
                                print(f"  [최종선택] 리디북스(역사 분리): {final_genre}")
                                print()  # 공백 줄
                                
                                return {
                                    'genre': final_genre,
                                    'confidence': min(naver_result['confidence'], keyword_result['confidence']),
                                    'method': 'ridibooks_history_refined',
                                    'keyword_result': keyword_result,
                                    'naver_result': naver_result
                                }
                            else:
                                print(f"  [2차 재매핑 실패] {validation_result['reason']}, {remapped_genre} 유지")
                                
                                # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                                print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                                print()  # 공백 줄
                        else:
                            if keyword_result['primary_genre'] in ['겜판', '역사']:
                                print(f"  [2차 재매핑 실패] {keyword_result['primary_genre']}이지만 신뢰도 낮음 ({keyword_result['confidence']:.0%} < 70%), {remapped_genre} 유지")
                            else:
                                print(f"  [2차 재매핑 실패] 겜판/역사 아님, {remapped_genre} 유지")
                            
                            # 네이버 검색 결과 로그 (2차 재매핑 실패 시)
                            print(f"  [네이버 검색 결과] {original_genre} ({naver_result['confidence']:.0%}, {source})")
                            print()  # 공백 줄
                
                # 네이버 검색 결과 로그 (2차 재매핑 없을 시)
                print(f"  [네이버 검색 결과] {remapped_genre} ({naver_result['confidence']:.0%}, {source})")
                print(f"  [최종선택] 네이버 검색: {remapped_genre}")
                print()  # 공백 줄 (장르 추론 완료)
                return {
                    'genre': remapped_genre,
                    'confidence': naver_result['confidence'],
                    'method': f"naver_{naver_result['source']}_priority",
                    'keyword_result': None,
                    'naver_result': naver_result
                }
        
        # 2. 특수 케이스 체크
        for special_title, special_genre in self.SPECIAL_CASES.items():
            if special_title in title:
                print(f"  [특수 케이스] '{special_title}' 감지 → {special_genre}")
                print(f"  [최종선택] 특수 케이스: {special_genre}")
                print()  # 공백 줄 (장르 추론 완료)
                return {
                    'genre': special_genre,
                    'confidence': 0.95,
                    'method': 'special_case',
                    'keyword_result': None,
                    'naver_result': naver_result
                }
        
        # 3. 복합 키워드 패턴 체크 (네이버 검색 실패 시)
        # 명확한 장르 조합이 있으면 키워드 분류보다 우선
        title_lower = title.lower()
        for (kw1, kw2), (genre, conf) in self.COMPOUND_PATTERNS.items():
            if kw1 in title_lower and kw2 in title_lower:
                print(f"  [복합 패턴 감지] '{title}' → {kw1} + {kw2} → {genre} ({conf:.0%})")
                print(f"  [최종선택] 복합 패턴: {genre}")
                print()  # 공백 줄 (장르 추론 완료)
                return {
                    'genre': genre,
                    'confidence': conf,
                    'method': 'compound_pattern',
                    'keyword_result': None,
                    'naver_result': naver_result
                }
        
        # 4. 저자명 기반 장르 추론 (v1.3.9 - 네이버 검색 실패 시)
        if use_naver and (not naver_result or not naver_result['genre']) and author_genre_hint:
            print(f"  [저자명 기반 장르] 네이버 검색 실패, 저자명 DB 사용")
            print(f"  [최종선택] 저자명 DB: {author_genre_hint['genre']}")
            print()  # 공백 줄
            
            return {
                'genre': author_genre_hint['genre'],
                'confidence': author_genre_hint['confidence'],
                'method': 'author_genre_db',
                'keyword_result': None,
                'naver_result': naver_result,
                'author': author_genre_hint['author']
            }
        
        # 5. 제목 키워드 분석 (v1.3.9 - 네이버 검색 실패 시)
        # 구체적인 장르 키워드(축구, 야구, 아이돌 등)가 있으면 우선 사용
        if use_naver and (not naver_result or not naver_result['genre']):
            title_keyword_result = self.title_keyword_analyzer.analyze_title_keywords(title)
            
            if title_keyword_result['genre'] and title_keyword_result['confidence'] >= 0.8:
                print(f"  [제목 키워드 분석] {title_keyword_result['genre']} ({title_keyword_result['confidence']:.0%})")
                print(f"  [매칭 키워드] {', '.join(title_keyword_result['matched_keywords'][:3])}")
                print(f"  [분석 결과] {title_keyword_result['genre']} (신뢰도: {title_keyword_result['confidence']:.0%})")
                print(f"  [최종선택] 제목 키워드: {title_keyword_result['genre']}")
                print()  # 공백 줄
                
                return {
                    'genre': title_keyword_result['genre'],
                    'confidence': title_keyword_result['confidence'],
                    'method': 'title_keyword_analysis',
                    'keyword_result': None,
                    'naver_result': naver_result,
                    'title_keyword_result': title_keyword_result
                }
        
        # 6. 키워드 기반 분류
        text = f"{title} {description}"
        keyword_result = self.keyword_classifier.classify_with_confidence(text)
        
        # 네이버 검색 실패 시 로그
        if use_naver and (not naver_result or not naver_result['genre']):
            print(f"  [키워드 분류] 네이버 검색 실패, 키워드 기반 분류 사용")
            print(f"  [키워드 결과] {keyword_result['primary_genre']} ({keyword_result['confidence']:.0%})")
        # 네이버 결과가 있지만 신뢰도가 낮은 경우
        elif use_naver and naver_result and naver_result['genre']:
            print(f"  [키워드 분류] 네이버 신뢰도 낮음 ({naver_result['confidence']:.0%}), 키워드 분류와 비교")
            print(f"  [키워드 결과] {keyword_result['primary_genre']} ({keyword_result['confidence']:.0%})")
        
        # 7. 결과 통합 (네이버 결과가 있지만 신뢰도가 낮은 경우)
        final_result = self._merge_results(keyword_result, naver_result)
        
        # 8. 신뢰도 임계값 적용
        if final_result['confidence'] < self.CONFIDENCE_THRESHOLD:
            # 저자명 힌트가 있으면 사용 (최후의 수단)
            if author_genre_hint and final_result['genre'] == '미분류':
                print(f"  [최후의 수단] 키워드 신뢰도 낮음, 저자명 DB 사용")
                print(f"  [최종선택] 저자명 DB(fallback): {author_genre_hint['genre']}")
                print()  # 공백 줄
                return {
                    'genre': author_genre_hint['genre'],
                    'confidence': author_genre_hint['confidence'],
                    'method': 'author_genre_db_fallback',
                    'keyword_result': keyword_result,
                    'naver_result': naver_result,
                    'author': author_genre_hint['author']
                }
            
            final_result['genre'] = '미분류'
            final_result['method'] = f"{final_result['method']}_low_confidence"
        
        print()  # 공백 줄 (장르 추론 완료)
        return final_result
    
    def _validate_genre_remapping(self, title, target_genre, confidence):
        """
        장르 재매핑 검증
        
        2차 재매핑 시 장르별 강력한 키워드가 있는지 검증
        
        Args:
            title: 소설 제목
            target_genre: 재매핑할 장르
            confidence: 키워드 분류 신뢰도
            
        Returns:
            {'valid': bool, 'reason': str}
        """
        title_lower = title.lower()
        
        # 퓨판은 검증 완화 (회귀, 귀환, 환생 등 일반적인 키워드)
        # 네이버시리즈/카카오페이지 "판타지" 세분화 시 가장 흔한 케이스
        if target_genre == '퓨판':
            fusion_keywords = self.keyword_mgr.get_validation_keywords('퓨판')
            matched = [kw for kw in fusion_keywords if kw in title_lower]
            if matched:
                return {'valid': True, 'reason': f"퓨판 키워드 확인: {', '.join(matched[:3])}"}
            else:
                return {'valid': False, 'reason': f"퓨판 키워드 없음"}
        
        # 판타지는 검증 완화 (기본 장르, 세분화 실패 시 유지)
        if target_genre == '판타지':
            return {'valid': True, 'reason': f"판타지는 기본 장르 (세분화 실패)"}
        
        # 기타 장르는 강력한 키워드 필요 (KeywordManager에서 로드)
        validation_keywords = self.keyword_mgr.get_validation_keywords(target_genre)
        if validation_keywords:
            matched_keywords = [kw for kw in validation_keywords if kw in title_lower]
            if matched_keywords:
                return {'valid': True, 'reason': f"{target_genre} 키워드 확인: {', '.join(matched_keywords[:3])}"}
            else:
                return {'valid': False, 'reason': f"{target_genre} 강력한 키워드 없음"}
        
        # 정의되지 않은 장르는 신뢰도만으로 판단
        if confidence >= 0.80:
            return {'valid': True, 'reason': f"높은 신뢰도 ({confidence:.0%})"}
        else:
            return {'valid': False, 'reason': f"신뢰도 부족 ({confidence:.0%})"}
    
    def _get_remap_reason(self, original_genre, remapped_genre, title):
        """세분화 이유 설명"""
        title_lower = title.lower()
        
        # "판타지"를 세분화한 경우
        if original_genre == '판타지':
            if remapped_genre == '무협':
                keywords = []
                for kw in ['천마', '무림', '무공', '검법', '협객', '마교', '강호']:
                    if kw in title_lower:
                        keywords.append(kw)
                if keywords:
                    return f"무협 키워드 ({', '.join(keywords[:3])})"
            
            if remapped_genre == '역사':
                keywords = []
                for kw in ['조선', '고려', '황제', '황가', '제국', '연개소문', '이성계', '세계대전', '참전', '참전군인', '전쟁', '전장', '2차대전', '2차 대전', '2차세계대전', '1차대전', '무솔리니', '히틀러', '나폴레옹', '세자', '왕세자', '부국강병', '왕자', '공주', '왕비']:
                    if kw in title_lower:
                        keywords.append(kw)
                if keywords:
                    return f"역사 키워드 ({', '.join(keywords[:3])})"
            
            if remapped_genre == '현판':
                keywords = []
                for kw in ['헌터', '게이트', '각성', '던전', '타워', '협회장', '감독', '영화감독', '드라마감독', '애니메이션감독', '배우', '연예인', '아이돌']:
                    if kw in title_lower:
                        keywords.append(kw)
                if keywords:
                    return f"현대판타지 키워드 ({', '.join(keywords[:3])})"
            
            if remapped_genre == '겜판':
                keywords = []
                for kw in ['망겜', '야겜', 'npc', 'vr게임', '게임 속', '게임속', '게임', '자동사냥', '방치', 'mmorpg', '레이드', '던전', '퀘스트']:
                    if kw in title_lower:
                        keywords.append(kw)
                if keywords:
                    return f"게임판타지 키워드 ({', '.join(keywords[:3])})"
            
            if remapped_genre == '퓨판':
                keywords = []
                for kw in ['나 혼자', '이세계', '회귀', '귀환', '환생', '레벨업', '시스템']:
                    if kw in title_lower:
                        keywords.append(kw)
                if keywords:
                    return f"퓨전판타지 키워드 ({', '.join(keywords[:3])})"
        
        return "제목 키워드 기반 세분화"
    
    def _remap_naver_result(self, naver_genre, title, source=''):
        """
        네이버 결과를 제목 키워드로 재검증 (최소한의 보정만)
        
        원칙:
        1. 리디북스/노벨피아의 상세 분류는 신뢰하고 그대로 사용
        2. 네이버시리즈의 "판타지"만 제목으로 세분화
        3. 사용자가 GUI에서 최종 수정 가능
        """
        title_lower = title.lower()
        
        # 1. 이미 세분화된 장르는 그대로 신뢰 (재매핑 안 함)
        detailed_genres = ['퓨판', '현판', '겜판', '무협', '로판', '선협', 'SF', '스포츠', '역사', '언정', '소설', '현대', '공포', '패러디', '미스터리']
        if naver_genre in detailed_genres:
            # 플랫폼 분류를 신뢰하고 그대로 사용
            return naver_genre
        
        # 2. "판타지"는 출처에 따라 다르게 처리
        if naver_genre == '판타지':
            # 2-A. 네이버시리즈의 "판타지"만 세분화
            # (리디북스/노벨피아의 "판타지"는 그대로 신뢰)
            if 'naver_series' not in source:
                # 리디북스/노벨피아의 "판타지"는 그대로 유지
                return naver_genre
            
            # 2-B. 네이버시리즈의 "판타지"를 세분화
            # 네이버시리즈 장르: 로맨스, 로판, 판타지, 현판, 무협, 미스터리, 라이트노벨, BL
            # "판타지"를 → 무협, 역사, 현판, 겜판, 퓨판, 정통판타지로 세분화
            # 2-1. 무협 키워드 체크 (최우선)
            martial_keywords = self.keyword_mgr.get_fantasy_separation_keywords('무협')
            if any(kw in title_lower for kw in martial_keywords):
                return '무협'
            
            # 2-2. 역사 키워드 체크
            history_keywords = self.keyword_mgr.get_fantasy_separation_keywords('역사')
            if any(kw in title_lower for kw in history_keywords):
                return '역사'
            
            # 2-3. 현판 키워드 체크
            modern_keywords = self.keyword_mgr.get_fantasy_separation_keywords('현판')
            if any(kw in title_lower for kw in modern_keywords):
                return '현판'
            
            # 2-4. 겜판 키워드 체크 (매우 명확한 경우만)
            game_keywords = self.keyword_mgr.get_fantasy_separation_keywords('겜판')
            if any(kw in title_lower for kw in game_keywords):
                return '겜판'
            
            # 2-5. 퓨판 키워드 체크
            fusion_keywords = self.keyword_mgr.get_validation_keywords('퓨판')
            # 2개 이상의 키워드가 있으면 퓨판
            fusion_count = sum(1 for kw in fusion_keywords if kw in title_lower)
            if fusion_count >= 2:
                return '퓨판'
            
            # 2-6. 단일 키워드로 퓨판 판단 (강력한 키워드)
            strong_fusion_keywords = ['나 혼자', '이세계', '회귀', '귀환', '환생']
            if any(kw in title_lower for kw in strong_fusion_keywords):
                return '퓨판'
            
            # 2-7. 나머지는 정통 판타지로 유지
            return '판타지'
        
        # 3. 기타 장르는 그대로 반환
        return naver_genre
    
    def _merge_results(self, keyword_result, naver_result):
        """
        두 결과 통합
        """
        # 네이버 결과가 없거나 실패한 경우
        if not naver_result or not naver_result['genre']:
            print(f"  [최종 결정] 키워드 분류만 사용: {keyword_result['primary_genre']} ({keyword_result['confidence']:.0%})")
            return {
                'genre': keyword_result['primary_genre'],
                'confidence': keyword_result['confidence'],
                'method': 'keyword_only',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
        
        # 키워드 결과가 미분류인 경우
        if keyword_result['primary_genre'] == '미분류':
            print(f"  [최종 결정] 네이버 결과만 사용: {naver_result['genre']} ({naver_result['confidence']:.0%})")
            return {
                'genre': naver_result['genre'],
                'confidence': naver_result['confidence'],
                'method': 'naver_only',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
        
        # 두 결과가 일치하는 경우
        if keyword_result['primary_genre'] == naver_result['genre']:
            p_keyword = keyword_result['confidence']
            p_naver = naver_result['confidence']
            combined_confidence = 1 - (1 - p_keyword) * (1 - p_naver)
            
            print(f"  [최종 결정] 네이버+키워드 일치: {keyword_result['primary_genre']} ({min(combined_confidence, 0.95):.0%})")
            return {
                'genre': keyword_result['primary_genre'],
                'confidence': min(combined_confidence, 0.95),
                'method': 'both_agree',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
        
        # 두 결과가 다른 경우 - 신뢰도 기반 선택
        keyword_conf = keyword_result['confidence']
        naver_conf = naver_result['confidence']
        
        # 키워드 분류 신뢰도 조정: 단일 키워드 매칭은 신뢰도 낮춤
        matched_keywords_count = len(keyword_result.get('matched_keywords', []))
        if matched_keywords_count <= 1:
            # 단일 키워드 매칭: 신뢰도를 60%로 제한
            keyword_conf = min(keyword_conf, 0.60)
            print(f"  [키워드 신뢰도 조정] 단일 키워드 매칭 → {keyword_conf:.0%}")
        elif matched_keywords_count == 2:
            # 2개 키워드 매칭: 신뢰도를 75%로 제한
            keyword_conf = min(keyword_conf, 0.75)
            print(f"  [키워드 신뢰도 조정] 2개 키워드 매칭 → {keyword_conf:.0%}")
        
        # 네이버 신뢰도가 높으면 (80% 이상) 네이버 우선
        # 공식 서점(교보문고, 알라딘 85%)이나 JSON-LD(리디북스 95%) 등
        if naver_conf >= 0.80:
            print(f"  [최종 결정] 네이버 우선 (신뢰도 높음): {naver_result['genre']} ({naver_conf:.0%}) vs 키워드: {keyword_result['primary_genre']} ({keyword_conf:.0%})")
            return {
                'genre': naver_result['genre'],
                'confidence': naver_conf,
                'method': 'naver_high_confidence',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
        
        # 키워드 신뢰도가 네이버보다 20% 이상 높으면 키워드 우선
        if keyword_conf >= naver_conf + 0.20:
            print(f"  [최종 결정] 키워드 우선 (신뢰도 차이 큼): {keyword_result['primary_genre']} ({keyword_conf:.0%}) vs 네이버: {naver_result['genre']} ({naver_conf:.0%})")
            return {
                'genre': keyword_result['primary_genre'],
                'confidence': keyword_conf,
                'method': 'keyword_high_confidence',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
        
        # 둘 다 애매하면 더 높은 신뢰도 선택
        if naver_conf > keyword_conf:
            return {
                'genre': naver_result['genre'],
                'confidence': naver_conf * 0.9,  # 약간의 불일치 페널티
                'method': 'naver_higher_confidence',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
        else:
            return {
                'genre': keyword_result['primary_genre'],
                'confidence': keyword_conf * 0.9,  # 약간의 불일치 페널티
                'method': 'keyword_higher_confidence',
                'keyword_result': keyword_result,
                'naver_result': naver_result
            }
    
    def close(self):
        """리소스 정리"""
        if hasattr(self.keyword_classifier, 'close'):
            self.keyword_classifier.close()


def test_improved_classifier():
    """개선된 분류기 테스트"""
    classifier = HybridClassifier()
    
    test_cases = [
        "금리낭자",
        "나 혼자 소드 마스터",
        "귀환한 마신은 만렙 플레이어",
        "헌터 게이트",
        "이세계 게이머",
    ]
    
    print("="*70)
    print("개선된 분류기 테스트")
    print("="*70)
    
    for title in test_cases:
        result = classifier.classify(title, use_naver=False)
        print(f"\n제목: {title}")
        print(f"장르: {result['genre']} ({result['confidence']:.0%}, {result['method']})")
    
    classifier.close()


if __name__ == "__main__":
    test_improved_classifier()
