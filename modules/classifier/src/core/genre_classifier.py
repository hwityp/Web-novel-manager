"""
개선된 키워드 기반 장르 판정 시스템
- 키워드 가중치 시스템
- 장르 특화도 계산
- 정규화된 점수
- 모든 키워드는 genre_keywords.json에서 관리
"""
import sys
import os

# 현재 파일 경로 기준으로 모듈 경로 추가
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from keyword_manager import KeywordManager
from collections import Counter

# DB 관련 import는 레거시 지원용으로 유지 (실제 사용 안 함)
try:
    from database.db_manager import DatabaseManager
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("[GenreClassifier] DB 모듈 없음 - KeywordManager만 사용")

try:
    from crawler.manual_keywords import GENRE_KEYWORDS
except ImportError:
    GENRE_KEYWORDS = {}


class GenreClassifier:
    """개선된 장르 분류기 - KeywordManager 기반"""
    
    # 레거시 하드코딩 키워드 제거됨 (genre_keywords.json으로 통합)
    # 아래 주석은 참고용으로만 유지
    """
    CORE_KEYWORDS_LEGACY = {
        '현판': {
            # 헌터물
            '헌터': 10, '게이트': 10, '각성': 8, '각성자': 8,
            'S급': 7, 'A급': 5, '길드': 8, '협회': 9,
            '레이드': 7, '협회장': 10,
            
            # 현대 직업 - 예술/엔터테인먼트
            '아이돌': 10, '작곡가': 10, '연예인': 9, '배우': 9,
            '가수': 9, '프로듀서': 8, '매니저': 10,
            '감독': 10, '영화감독': 10, '드라마감독': 10, '애니메이션감독': 10,
            '영화': 8, '드라마': 8, '애니메이션': 9, '방송': 8,
            
            # 현대 직업 - 전문직
            '한의사': 10, '의사': 8, '변호사': 8, '검사': 10,
            '회계사': 10, '교수': 10,
            
            # 현대 직업 - 예술가/장인
            '도예가': 10, '화가': 9, '요리사': 8,
            
            # 현대 직업 - 비즈니스
            '재벌': 10, '사장': 8, '대표': 10, '회사': 7,
            '직장': 7, '기업': 7,
            
            # 현대 직업 - 특수
            '징수': 10, '탐정': 8,
            
            # 현대 배경
            '현대': 9, '도시': 7, '서울': 7,
            
            # 현대 시설/장소
            '편의점': 9, '카페': 7, '식당': 7,
            
            # 현대적 판타지 용어 (헌터물에서 사용)
            '힐러': 7, '서포터': 7, '탱커': 7,
        },
        '퓨판': {
            # 회귀/귀환 (핵심)
            '귀환': 10, '회귀': 10, '환생': 9, '빙의': 9,
            '전생': 9, '돌아왔다': 9, '귀환한': 9,
            
            # 나 혼자 시리즈 (가중치 낮춤 - 현판과 겹침)
            '나 혼자': 7, '혼자만': 9, '독식': 9,
            
            # 시스템/레벨업 (가중치 낮춤 - 무협과 겹침)
            '시스템': 7, '레벨업': 7, '상태창': 8,
            '스탯': 7, '스킬': 6,
            
            # 이세계
            '이세계': 9, '전이': 8, '소환': 8,
            
            # 아포칼립스 (현판에서 이동)
            '종말': 8, '아포칼립스': 9, '좀비': 9,
            
            # 현대적 판타지 용어
            '힐러': 8, '버퍼': 8, '디버퍼': 8,
            
            # 특수
            '소드마스터': 9, '마도왕': 9, '마신': 8,
            '만렙': 7, '최강': 6,
        },
        '무협': {
            '천마': 10, '무림': 10, '강호': 10, '검황': 10,
            '검성': 10, '무공': 9, '검법': 8, '내공': 8,
            '절세무공': 9, '남궁세가': 10, '제갈세가': 10,
            '무당파': 9, '소림': 9, '화산파': 9,
            '마교': 8, '정파': 7, '사파': 7,
            '금의위': 7,  # 명나라 비밀경찰 조직
            # 문파 약칭 (핵심!)
            '화산': 10, '무당': 10, '아미': 9, '곤륜': 9,
            '청성': 9, '종남': 9, '개방': 9,
            # 세가 약칭 (핵심!)
            '남궁': 10, '제갈': 10, '사천당': 9, '팽가': 9,
            '백리': 9, '황보': 9, '모용': 9,
        },
        '로판': {
            # 로맨스
            '악녀': 10, '총애': 10, '집착': 9, '독점': 9,
            '계약결혼': 10, '정략결혼': 10, '혼약': 9,
            '사랑': 6, '연애': 7,
            
            # 궁정/귀족
            '황제': 9, '황후': 10, '황태자': 9, '공주': 9,
            '공작': 9, '후궁': 10, '궁정': 10, '귀족': 8,
            '영애': 9, '백작': 8,
            
            # BL/GL
            '공': 10, '수': 10, '오메가버스': 10,
            '알파': 8, '오메가': 8,
            
            # 중국 로맨스
            '금리': 10, '낭자': 10, '공자': 8, '소저': 9,
        },
        '판타지': {
            # 마법
            '마법': 8, '마법사': 9, '대마법사': 10,
            '마법학교': 9, '마탑': 9, '마력': 7,
            
            # 몬스터/던전
            '드래곤': 9, '용': 8, '던전': 6, '몬스터': 6,
            '마왕': 7, '마물': 8,
            
            # 중세 배경
            '성기사': 8, '기사': 7, '검술': 7, '왕국': 7,
            
            # 탑/타워
            '탑': 7, '타워': 7,
            
            # 특수
            '네크로맨서': 10, '드루이드': 10, '암살자': 8,
            '용사': 8, '용사파티': 9,
        },
        '겜판': {
            # 게임
            '망겜': 10, '갓겜': 10, '게임': 7,
            'VR': 10, 'MMORPG': 10, 'RPG': 9, 'MOBA': 9,
            
            # 게임 요소
            'NPC': 9, '플레이어': 7, '게이머': 7,
            '캐릭터': 7, '아바타': 8, '접속': 8,
            
            # 게임 직업/역할 (RPG 용어)
            '힐러': 9, '탱커': 9, '딜러': 8, '서포터': 8,
            
            # 게임 장르
            '야겜': 9, '연애게임': 9,
        },
        '역사': {
            '조선': 10, '고려': 10, '삼국': 10, '삼국지': 10,
            '이성계': 10, '연개소문': 10, '황제': 7,
            '왕': 7, '세자': 8, '왕세자': 9, '대군': 8, '태조': 9,
            '단종': 10, '영조': 10, '정조': 10, '세종': 10,
            '태종': 10, '고종': 10, '선조': 10, '대원군': 10,
            '충무공': 10, '이순신': 10,
            '탐관오리': 10, '탐관': 9, '관리': 6,
            '사또': 8, '현감': 8, '부사': 8, '판서': 8,
            '러일전쟁': 10, '청일전쟁': 10, '한일합방': 10,
            '인조': 10, '명군': 9,
            '세계대전': 10, '2차대전': 10, '2차 대전': 10, '2차세계대전': 10,
            '1차대전': 10, '1차 대전': 10,
            '무솔리니': 10, '히틀러': 10, '스탈린': 10, '처칠': 10,
            '루즈벨트': 10, '나폴레옹': 10, '카이사르': 10, '알렉산더': 10,
            '부국강병': 9, '왕자': 7, '공주': 7, '왕비': 7,
            '전쟁': 7, '전장': 7, '참전': 9, '참전군인': 9,
        },
        '선협': {
            '선인': 10, '수련': 8, '도술': 9, '법술': 9,
            '영약': 8, '단약': 8, '승천': 9,
            '선계': 10, '상계': 9, '하계': 8,
        },
        'SF': {
            '우주': 10, '외계': 10, '외계인': 10,
            '로봇': 9, 'AI': 9, '인공지능': 9,
            '우주선': 9, '함선': 8, '미래': 7,
        },
        '스포츠': {
            # 축구
            '축구': 10, '골': 9, '슛': 9, '패스': 9,
            '드리블': 9, '발롱도르': 10, '월드컵': 10,
            '프리미어리그': 10, '챔피언스리그': 10,
            '스트라이커': 9, '미드필더': 9, '수비수': 9, '골키퍼': 9,
            
            # 야구
            '야구': 10, '투수': 9, '타자': 9, '홈런': 9,
            '마운드': 10, '타석': 9, '메이저리그': 10,
            '강속구': 10, '너클': 10, '커브': 10, '체인지업': 10,
            
            # 농구
            '농구': 10, '덩크': 9, '3점슛': 10, '3점 슛': 10, 'NBA': 10,
            '리바운드': 9, '어시스트': 9, '코트': 8,
            
            # 공통
            '선수': 8, '감독': 8, '코치': 8,
            '올림픽': 10, '국가대표': 9, '게이머': 9,
        },
    }
    
    COMPOUND_PATTERNS_LEGACY = {
        # 무협 최우선 (무공 관련)
        ('무공', '시스템'): ('무협', 22),
        ('무공', '레벨업'): ('무협', 22),
        ('무공', '자동사냥'): ('무협', 22),
        ('무림', '회귀'): ('무협', 20),
        ('무림', '귀환'): ('무협', 20),
        ('천마', '제자'): ('무협', 22),
        ('검법', '레벨업'): ('무협', 20),
        ('금의위', '무공'): ('무협', 20),
        ('금의위', '시스템'): ('무협', 20),
        ('남궁', '세가'): ('무협', 22),
        ('제갈', '세가'): ('무협', 22),
        ('화산', '귀환'): ('무협', 22),
        ('화산', '회귀'): ('무협', 22),
        ('소림', '귀환'): ('무협', 20),
        ('무당', '귀환'): ('무협', 20),
        
        # 현판 우선 (헌터물)
        ('헌터', '게이트'): ('현판', 22),
        ('헌터', '길드'): ('현판', 20),
        ('헌터', '협회'): ('현판', 22),
        ('각성', '헌터'): ('현판', 20),
        ('힐러', '헌터'): ('현판', 20),
        ('힐러', '길드'): ('현판', 18),
        
        # 현판 우선 (현대 직업 + 회귀)
        ('아이돌', '회귀'): ('현판', 22),
        ('작곡가', '회귀'): ('현판', 22),
        ('재벌', '회귀'): ('현판', 20),
        ('회사', '회귀'): ('현판', 18),
        ('감독', '회귀'): ('현판', 22),
        ('배우', '회귀'): ('현판', 22),
        
        # 현판 우선 (현대 직업 단독)
        ('한의사', '고침'): ('현판', 22),
        ('도예가', '빚는'): ('현판', 22),
        ('징수', '달인'): ('현판', 22),
        ('매니저', '독식'): ('현판', 20),
        ('감독', '천재'): ('현판', 22),
        ('감독', '시작'): ('현판', 20),
        ('애니메이션', '감독'): ('현판', 22),
        ('영화', '감독'): ('현판', 22),
        ('드라마', '감독'): ('현판', 22),
        
        # 현판 우선 (나 혼자 + 현대 키워드)
        ('나 혼자', '게이머'): ('현판', 20),
        ('나 혼자', '징수'): ('현판', 22),
        ('나 혼자', '기연'): ('현판', 20),
        ('나 혼자', '연금술'): ('현판', 20),
        
        # 로판 우선
        ('악녀', '황제'): ('로판', 22),
        ('총애', '황후'): ('로판', 22),
        ('계약', '결혼'): ('로판', 22),
        ('공', '수'): ('로판', 22),
        ('금리', '낭자'): ('로판', 22),
        
        # 겜판 우선
        ('망겜', '속'): ('겜판', 22),
        ('VR', '게임'): ('겜판', 22),
        ('NPC', '플레이어'): ('겜판', 20),
        ('야겜', '속'): ('겜판', 22),
        ('힐러', '게임'): ('겜판', 20),
        ('힐러', 'RPG'): ('겜판', 22),
        ('탱커', '힐러'): ('겜판', 22),
        
        # 퓨판 (나머지)
        ('나 혼자', '레벨업'): ('퓨판', 18),
        ('나 혼자', '독식'): ('퓨판', 18),
        ('소드', '마스터'): ('퓨판', 18),
        ('마도', '왕'): ('퓨판', 18),
        ('이세계', '전이'): ('퓨판', 18),
        
        # 퓨판 (아포칼립스 + 현대 시설)
        ('편의점', '종말'): ('퓨판', 20),
        ('편의점', '아포칼립스'): ('퓨판', 20),
        ('카페', '종말'): ('퓨판', 20),
        ('식당', '종말'): ('퓨판', 20),
    }
    """
    
    def __init__(self, use_db=False):
        """
        초기화
        
        Args:
            use_db: DB 사용 여부 (기본값: False, KeywordManager만 사용)
        """
        # KeywordManager 초기화 (주 데이터 소스)
        self.keyword_mgr = KeywordManager()
        
        # KeywordManager에서 키워드 로드
        self.CORE_KEYWORDS = self.keyword_mgr.get_single_keywords()
        self.COMPOUND_PATTERNS = self.keyword_mgr.get_all_compound_patterns_dict()
        
        # 장르 목록
        self.genres = list(self.CORE_KEYWORDS.keys())
        
        # 장르별 키워드 로드 (KeywordManager 기반)
        self.genre_keywords = {}
        self.genre_compound_keywords = {}
        
        for genre in self.genres:
            # 단일 키워드
            single_kw = self.keyword_mgr.get_single_keywords(genre)
            self.genre_keywords[genre] = list(single_kw.keys())
            
            # 복합 키워드
            patterns = self.keyword_mgr.get_compound_patterns(genre)
            self.genre_compound_keywords[genre] = [(p[0], p[1]) for p in patterns]
        
        # DB 초기화 (레거시 지원, 선택적)
        self.db = None
        self.use_db = use_db
        if use_db and DB_AVAILABLE:
            try:
                self.db = DatabaseManager()
                print("[GenreClassifier] DB 연결 성공 (레거시 모드)")
            except Exception as e:
                print(f"[GenreClassifier] DB 연결 실패: {e}")
                self.use_db = False
        
        # 키워드 특화도 계산 (사전 계산)
        self.keyword_specificity = self._calculate_keyword_specificity()
        
        print(f"[GenreClassifier] KeywordManager 기반 초기화 완료 (버전: {self.keyword_mgr.get_version()})")
        print(f"[GenreClassifier] 로드된 장르: {', '.join(self.genres)}")
        print(f"[GenreClassifier] DB 사용: {'예' if self.use_db else '아니오'}")
    
    def _calculate_keyword_specificity(self):
        """각 키워드가 몇 개 장르에 나타나는지 계산"""
        keyword_genres = {}
        
        for genre, keywords in self.genre_keywords.items():
            for keyword in keywords:
                if keyword not in keyword_genres:
                    keyword_genres[keyword] = []
                keyword_genres[keyword].append(genre)
        
        # 특화도 점수 계산
        specificity = {}
        for keyword, genres in keyword_genres.items():
            count = len(genres)
            if count == 1:
                specificity[keyword] = 5  # 매우 특화
            elif count == 2:
                specificity[keyword] = 3  # 특화
            elif count == 3:
                specificity[keyword] = 2  # 약간 특화
            else:
                specificity[keyword] = 1  # 공통
        
        return specificity
    
    def classify(self, text, top_n=3):
        """
        텍스트를 분석하여 장르 판정 (개선 버전)
        
        Args:
            text: 분석할 텍스트 (제목, 설명, 태그 등)
            top_n: 반환할 상위 장르 수
            
        Returns:
            [(장르, 점수, 매칭키워드), ...] 형태의 리스트
        """
        text_lower = text.lower()
        genre_scores = {}
        genre_matched_keywords = {}
        
        # 1. 복합 키워드 패턴 체크 (최우선, 매우 높은 점수)
        compound_bonus = {}
        for (kw1, kw2), (genre, score) in self.COMPOUND_PATTERNS.items():
            if kw1 in text_lower and kw2 in text_lower:
                if genre not in compound_bonus:
                    compound_bonus[genre] = 0
                compound_bonus[genre] += score
        
        for genre in self.genres:
            score = 0
            matched = []
            matched_keywords_set = set()  # 이미 매칭된 키워드 추적
            
            # 2. 핵심 키워드 매칭 (높은 가중치)
            # 긴 키워드부터 매칭 (성기사 → 기사 순서)
            if genre in self.CORE_KEYWORDS:
                # 키워드를 길이 순으로 정렬 (긴 것부터)
                sorted_keywords = sorted(self.CORE_KEYWORDS[genre].items(), key=lambda x: len(x[0]), reverse=True)
                
                for keyword, weight in sorted_keywords:
                    # 1글자 키워드는 제외 (변별력 없음)
                    if len(keyword) < 2:
                        continue
                    
                    keyword_lower = keyword.lower()
                    if keyword_lower in text_lower:
                        # 특수 케이스: "무공"은 "충무공"이 있으면 무시
                        if keyword == '무공' and '충무공' in text_lower:
                            continue
                        
                        # 이미 매칭된 더 긴 키워드에 포함되는지 확인
                        is_substring = False
                        for matched_kw in matched_keywords_set:
                            if keyword_lower in matched_kw and keyword_lower != matched_kw:
                                is_substring = True
                                break
                        
                        if not is_substring:
                            score += weight
                            matched.append(f"{keyword}({weight})")
                            matched_keywords_set.add(keyword_lower)
            
            # 3. 일반 키워드 매칭 (특화도 기반 가중치)
            # 긴 키워드부터 매칭
            sorted_general_keywords = sorted(self.genre_keywords[genre], key=len, reverse=True)
            
            for keyword in sorted_general_keywords:
                # 1글자 키워드는 제외 (변별력 없음)
                if len(keyword) < 2:
                    continue
                    
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    # 핵심 키워드에 이미 포함되어 있으면 스킵
                    if genre in self.CORE_KEYWORDS and keyword in self.CORE_KEYWORDS[genre]:
                        continue
                    
                    # 이미 매칭된 더 긴 키워드에 포함되는지 확인
                    is_substring = False
                    for matched_kw in matched_keywords_set:
                        if keyword_lower in matched_kw and keyword_lower != matched_kw:
                            is_substring = True
                            break
                    
                    if not is_substring:
                        # 특화도 기반 점수
                        specificity_score = self.keyword_specificity.get(keyword, 1)
                        score += specificity_score
                        matched.append(f"{keyword}({specificity_score})")
                        matched_keywords_set.add(keyword_lower)
            
            # 4. 복합 키워드 매칭 (manual_keywords.py의 compound_keywords)
            for compound in self.genre_compound_keywords[genre]:
                if all(kw.lower() in text_lower for kw in compound):
                    score += 8  # 복합 키워드 보너스
                    matched.append('+'.join(compound) + '(8)')
            
            # 5. 복합 패턴 보너스 추가
            if genre in compound_bonus:
                score += compound_bonus[genre]
                matched.append(f"복합패턴({compound_bonus[genre]})")
            
            # 6. 정규화 (키워드 개수로 나누기)
            # 단, 최소 점수는 유지
            keyword_count = len(self.genre_keywords[genre])
            if keyword_count > 0:
                normalized_score = score / (keyword_count ** 0.5)  # 제곱근으로 완화
            else:
                normalized_score = score
            
            genre_scores[genre] = normalized_score
            genre_matched_keywords[genre] = matched
        
        # 점수순 정렬
        sorted_genres = sorted(
            genre_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 상위 N개 반환
        results = []
        for genre, score in sorted_genres[:top_n]:
            if score > 0:  # 점수가 0보다 큰 것만
                results.append((
                    genre,
                    score,
                    genre_matched_keywords[genre]
                ))
        
        return results
    
    def classify_with_confidence(self, text):
        """
        신뢰도 포함 장르 판정
        
        Returns:
            {
                'primary_genre': 주 장르,
                'confidence': 신뢰도 (0-1),
                'all_genres': [(장르, 점수, 매칭키워드), ...],
                'matched_keywords': 전체 매칭 키워드
            }
        """
        results = self.classify(text, top_n=len(self.genres))
        
        if not results:
            return {
                'primary_genre': '미분류',
                'confidence': 0.0,
                'score': 0,
                'all_genres': [],
                'matched_keywords': []
            }
        
        # 신뢰도 계산 (개선)
        total_score = sum(score for _, score, _ in results)
        primary_genre, primary_score, primary_keywords = results[0]
        
        # 1위와 2위 점수 차이도 고려
        if len(results) > 1:
            second_genre, second_score, second_keywords = results[1]
            score_gap = primary_score - second_score
            
            # 점수 차이가 클수록 신뢰도 높음
            if total_score > 0:
                base_confidence = primary_score / total_score
                # 점수 차이가 음수가 아니도록 보정
                if primary_score > 0:
                    gap_bonus = min(abs(score_gap) / primary_score, 0.3)  # 최대 30% 보너스
                else:
                    gap_bonus = 0
                confidence = min(base_confidence + gap_bonus, 1.0)
            else:
                confidence = 0.0
        else:
            confidence = 1.0 if primary_score > 0 else 0.0
        
        # 전체 매칭 키워드
        all_matched = []
        for _, _, keywords in results:
            all_matched.extend(keywords)
        
        return {
            'primary_genre': primary_genre,
            'confidence': confidence,
            'score': primary_score,
            'all_genres': results,
            'matched_keywords': all_matched
        }
    
    def close(self):
        """DB 연결 종료 (레거시 지원)"""
        if self.db is not None:
            try:
                self.db.close()
                print("[GenreClassifier] DB 연결 종료")
            except Exception as e:
                print(f"[GenreClassifier] DB 종료 중 오류: {e}")


def test_improved_classifier():
    """개선된 분류기 테스트"""
    classifier = GenreClassifier()
    
    test_cases = [
        "나 혼자 소드 마스터",
        "귀환한 마신은 만렙 플레이어",
        "헌터 게이트",
        "금리낭자",
        "남궁세가 망나니는 천마의 제자였다",
        "이세계 게이머",
        "화산귀환",
    ]
    
    print("="*80)
    print("개선된 키워드 분류기 테스트")
    print("="*80)
    
    for title in test_cases:
        result = classifier.classify_with_confidence(title)
        print(f"\n제목: {title}")
        print(f"장르: {result['primary_genre']} (신뢰도: {result['confidence']:.1%}, 점수: {result['score']:.1f})")
        print(f"매칭: {', '.join(result['matched_keywords'][:5])}")
        
        if len(result['all_genres']) > 1:
            print(f"2위: {result['all_genres'][1][0]} (점수: {result['all_genres'][1][1]:.1f})")
    
    classifier.close()
    print("\n" + "="*80)


if __name__ == "__main__":
    test_improved_classifier()
