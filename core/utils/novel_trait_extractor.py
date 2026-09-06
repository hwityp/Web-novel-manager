"""
==============================================================================
파일: core/utils/novel_trait_extractor.py
역할 및 목적:
    소설의 세부 서브 특징 키워드(사합원, 연대물, 공간, 농촌, 시스템, 빙의 등)를 감지하고,
    메인 장르(선협, 언정, 현판 등)와 결합하여 다중 태그 형식(예: [언정, 궁투, 빙의])을 구성하는 특성 분석 모듈.
주요 구성 요소:
    - extract_traits(): 텍스트/스니펫/제목에서 특징 키워드 목록 추출
    - combine_genre_with_traits(): 메인 장르와 세부 특성을 결합하여 최종 장르 태그 문자열 생성
    - TRAIT_PATTERNS: 특성 감지 정규식 패턴 및 우선순위 테이블
상호 연관 관계 및 의존성:
    - Caller: core.adapters.genre_classifier_adapter, core.adapters.filename_normalizer_adapter, tests.*
    - Callee: re
수정 시 주의사항:
    - 메인 장르와 결합 시 최대 허용 키워드 개수(메인 1개 + 특징 최대 2개) 제약을 준수해야 합니다.
==============================================================================
"""
import re
from typing import List, Tuple, Optional, Set

# 표준 메인 장르 목록
PRIMARY_GENRES = {
    "현판", "퓨판", "무협", "로판", "겜판", "판타지",
    "역사", "선협", "언정", "스포츠", "소설", "패러디", "현대",
    "공포", "미스터리", "밀리터리"
}

# 특징 키워드 정의 (우선순위 순서대로 배열)
TRAIT_PATTERNS: List[Tuple[str, List[str]]] = [
    # 0. 사합원 / 여주 / 하렘 (사용자 명시 핵심 키워드)
    ("사합원", [r"사합원", r"4합원", r"四合院"]),
    ("여주", [r"여주물", r"여주", r"여성주인공", r"여주인공", r"女主"]),
    ("하렘", [r"하렘", r"역하렘", r"남주", r"男主", r"后宫"]),
    # 1. 연대물 (70년대, 80년대, 칠령, 지청 등)
    ("연대물", [
        r"연대물", r"연대", r"70년대", r"80년대", r"90년대", r"칠령", r"팔령", r"구령",
        r"1970", r"1980", r"1990", r"지청", r"年代", r"七零", r"八零", r"九零", r"知青"
    ]),
    # 2. 공간 (수신공간, 공간물자)
    ("공간", [r"공간물자", r"수신공간", r"차원공간", r"공간물", r"공간", r"随身空间", r"空间"]),
    # 3. 농촌 (농가, 농문, 귀농)
    ("농촌", [r"농촌", r"농가복매", r"농문", r"농사", r"귀농", r"农家", r"农门", r"种田"]),
    # 4. 종말 / 말세
    ("종말", [r"종말", r"무한열차", r"아포칼립스", r"멸망", r"재앙"]),
    ("말세", [r"말세", r"말일", r"末世", r"末日", r"도계시"]),
    # 5. 책빙의 / 빙의
    ("책빙의", [r"책빙의", r"소설빙의", r"책\s*속", r"소설\s*속", r"천서후", r"천서", r"穿书", r"穿書"]),
    ("빙의", [r"빙의물", r"빙의", r"악역", r"천월", r"당태의", r"穿越", r"附身"]),
    # 6. 궁투 / 궁정
    ("궁투", [r"궁투극", r"궁투", r"후궁", r"宫斗", r"后宫"]),
    ("궁정", [r"궁정", r"궁궐", r"황궁", r"왕궁", r"조정", r"궤비", r"태의", r"宫廷", r"皇宫"]),
    # 7. 시스템 / 치트
    ("시스템", [
        r"시스템", r"계통", r"系統", r"系统", r"치트", r"출석\s*체크", r"상태창", r"퀘스트",
        r"스킬", r"패널", r"로그인", r"유희모조", r"게임모드", r"개시", r"반파", r"당신탐", r"금리처", r"锦鲤"
    ]),
    # 8. 재테크
    ("재테크", [r"재테크", r"주식", r"투자", r"재벌", r"건물주", r"자산", r"창업", r"돈벌기", r"가가1990", r"1990", r"致富", r"炒股"]),
    # 9. 가족
    ("가족", [r"복보유량전", r"단총소내포", r"복보", r"소내포", r"가족물", r"육아물", r"가족", r"육아", r"团宠", r"育儿"]),
    # 10. 이세계
    ("이세계", [r"이세계", r"이계", r"차원", r"이차원", r"异界", r"异세계"]),
    # 11. 군사 / 첩보
    ("군사", [r"군사", r"군대", r"전쟁", r"밀리터리", r"장군", r"제국", r"전함", r"서난종명", r"军事", r"军旅"]),
    ("첩보", [r"첩보", r"스파이", r"공작원", r"암살자", r"특수요원", r"국정원", r"서난종명", r"諜報", r"谍报", r"特工"]),
    # 12. 감성 / 분위기
    ("로맨스", [r"로맨스", r"련애유희", r"련애", r"연애", r"사랑", r"순정", r"恋爱", r"甜宠"]),
    ("코미디", [r"코미디", r"개그", r"유머", r"웃긴", r"해학", r"련애유희", r"첨도", r"첨부", r"搞笑", r"爆笑"]),
    ("힐링", [r"힐링", r"치유", r"소소한", r"따뜻한", r"청천일자", r"청천", r"治愈"]),
    ("일상", [r"일상물", r"일상", r"평범적청천일자", r"평범", r"청천일자", r"일자", r"日常"]),
    # 13. 패러디 상세 소재
    ("드래곤볼", [r"드래곤볼", r"손오공", r"베지터", r"초사이어인", r"카카로트", r"나메크"]),
    ("원피스", [r"원피스", r"루피", r"조로", r"해적왕"]),
    ("나루토", [r"나루토", r"사스케", r"닌자", r"나뭇잎마을"]),
    ("해리포터", [r"해리포터", r"호그와트", r"볼드모트"]),
    ("포켓몬", [r"포켓몬", r"피카츄", r"몬스터볼"]),
    ("명탐정 코난", [r"명탐정\s*코난", r"코난", r"쿠도\s*신이치", r"남도일", r"검은\s*조직"]),
    ("주술회전", [r"주술회전", r"고죠\s*사토루", r"이타도리", r"스쿠나"]),
    ("귀멸의 칼날", [r"귀멸의\s*칼날", r"귀칼", r"탄지로", r"네즈코"]),
    # 14. 기타 세부 특징
    ("학원", [r"학원", r"아카데미", r"학교", r"学院", r"学园"]),
    ("생존", [r"생존물", r"생존자", r"살아남기", r"아포칼립스\s*생존", r"生存"]),
    ("착각", [r"착각물", r"착각"]),
    ("방송", [r"방송", r"스트리머", r"BJ", r"유튜버", r"인플루언서", r"直播"]),
    ("헌터", [r"헌터", r"게이트", r"마수"]),
    ("던전", [r"던전", r"미궁"]),
    ("요리", [r"요리", r"쉐프", r"셰프", r"식당", r"미식", r"美食", r"厨神"]),
]

# 장르 별칭 및 정규화 매핑
GENRE_ALIAS_MAP = {
    "현대판타지": "현판", "현대 판타지": "현판", "현판": "현판",
    "퓨전판타지": "퓨판", "퓨전 판타지": "퓨판", "퓨판": "퓨판",
    "게임판타지": "겜판", "게임 판타지": "겜판", "겜판": "겜판",
    "로맨스판타지": "로판", "로맨스 판타지": "로판", "로판": "로판",
    "퓨전무협": "무협", "퓨전 무협": "무협", "신무협": "무협", "무협": "무협",
    "판타지": "판타지", "선협": "선협", "언정": "언정", "스포츠": "스포츠",
    "패러디": "패러디", "역사": "역사", "SF": "SF", "공포": "공포",
    "미스터리": "미스터리", "밀리터리": "밀리터리", "현대": "현대", "소설": "소설"
}

# 첨언 노이즈 단어
ANNOTATION_NOISE_WORDS = {
    "ai번역", "ai 번역", "기계번역", "기계 번역", "손번역", "번역",
    "txt", "텍본", "소설", "웹소설", "완결", "완", "完", "19금", "15금",
    "개정판", "완전판", "합본", "스캔", "단행본", "텍스트", "연재", "련재"
}

# 패러디 대표 작품/소재 매핑
PARODY_FANDOM_MAP = {
    "해리포터": "해리포터", "호그와트": "해리포터",
    "나루토": "나루토", "사스케": "나루토",
    "원피스": "원피스", "루피": "원피스",
    "드래곤볼": "드래곤볼", "손오공": "드래곤볼",
    "포켓몬": "포켓몬", "피카츄": "포켓몬",
    "명탐정코난": "명탐정 코난", "명탐정 코난": "명탐정 코난", "코난": "명탐정 코난",
    "주술회전": "주술회전", "주술 회전": "주술회전",
    "귀멸의칼날": "귀멸의 칼날", "귀멸의 칼날": "귀멸의 칼날", "귀칼": "귀멸의 칼날",
    "헌터x헌터": "헌터x헌터", "헌터X헌터": "헌터x헌터", "헌터헌터": "헌터x헌터",
    "블리치": "블리치"
}


class NovelTraitExtractor:
    """소설 특징 키워드 추출기"""

    @classmethod
    def extract_from_annotations(cls, raw_name: str) -> Optional[str]:
        """
        파일명의 앞 접두사 태그([...]) 또는 뒤 첨언(#해시태그, (...))에서 장르 및 특성을 추출합니다.
        웹 검색보다 우선하여 장르 태그(예: '패러디, 해리포터', '언정, 연대물', '패러디, 나루토, 시스템')를 확정합니다.
        
        예)
        - '아도성곽격옥자교수료, 계통재래 1-267 完 (AI번역) #패러디 #해리포터.txt' -> '패러디, 해리포터'
        - '가남：개국절호명미，와저주창 1-740 完 (AI번역) #패러디 #명탐정 코난.txt' -> '패러디, 명탐정 코난'
        - '[언정][AI번역] 중생낭자전 1~1466(완).txt' -> '언정'
        - '[언정][AI번역][연대] 중생낭자재종전 1~1466(완).txt' -> '언정, 연대물'
        - '[나루토패러디 시스템 AI번역] 푸른 용 1-633 완결.txt' -> '패러디, 나루토, 시스템'
        """
        if not raw_name:
            return None

        # 확장자 제거
        name = re.sub(r'\.[a-zA-Z0-9]{1,10}$', '', raw_name).strip()

        # 1. 태그/첨언 후보군 추출
        # (1) 해시태그 (다중 단어로 구성된 #명탐정 코난 등 지원, 수치/완결 마커는 제외)
        hashtags = [
            m.strip() for m in re.findall(
                r'#([가-힣a-zA-Z0-9_]+(?:\s+(?!\d+|완결?|完|외전|후기|에필)[가-힣a-zA-Z0-9_]+)*)',
                name
            ) if m.strip()
        ]
        
        # (2) 대괄호 태그
        brackets = re.findall(r'\[([^\]]+)\]', name)
        
        # (3) 소괄호 태그 (단순 숫자 범위나 '완' 단독 제외)
        parens = re.findall(r'\(([^\)]+)\)', name)
        valid_parens = []
        for p in parens:
            p_strip = p.strip()
            if not re.match(r'^(?:\d+[\s\-~_]+\d+|\d+[화권부편회장]?|완결?|完|외전.*)$', p_strip):
                valid_parens.append(p_strip)

        candidate_sources = brackets + valid_parens + hashtags
        if not candidate_sources:
            return None

        # 2. 토큰 분해 및 정리
        tokens: List[str] = []
        for source in candidate_sources:
            # 먼저 쉼표나 슬래시로 1차 분리
            comma_parts = re.split(r'[,/]+', source)
            for cp in comma_parts:
                cp_strip = cp.strip()
                if not cp_strip:
                    continue
                # 복합어(예: "명탐정 코난", "해리 포터")가 매핑에 직접 존재하면 단일 토큰으로 보존
                if (cp_strip in PARODY_FANDOM_MAP or 
                    cp_strip in GENRE_ALIAS_MAP or 
                    any(cp_strip == trait_name or any(re.fullmatch(pat, cp_strip, re.IGNORECASE) for pat in patterns) for trait_name, patterns in TRAIT_PATTERNS)):
                    tokens.append(cp_strip)
                else:
                    # 공백으로 추가 분해
                    parts = re.split(r'\s+', cp_strip)
                    for part in parts:
                        cleaned = part.strip()
                        if cleaned:
                            tokens.append(cleaned)

        primary_genre: Optional[str] = None
        extracted_traits: List[str] = []

        def add_trait(t: str):
            if t and t not in extracted_traits:
                extracted_traits.append(t)

        for token in tokens:
            token_lower = token.lower()
            # 노이즈 단어 건너뛰기
            if token_lower in ANNOTATION_NOISE_WORDS:
                continue
            if re.match(r'^(?:\d+.*|[Aa][Ii]번역|번역.*)$', token):
                continue

            # (A) 복합어 확인 1: ~패러디 (예: "나루토패러디" -> 주 장르: 패러디, 특성: 나루토)
            if "패러디" in token and token != "패러디":
                primary_genre = "패러디"
                prefix = token.replace("패러디", "").strip()
                if prefix:
                    norm_prefix = PARODY_FANDOM_MAP.get(prefix, prefix)
                    add_trait(norm_prefix)
                continue

            # (B) 복합어 확인 2: 주 장르 (예: 현대판타지, 퓨전판타지, 언정 등)
            if token in GENRE_ALIAS_MAP:
                if not primary_genre:
                    primary_genre = GENRE_ALIAS_MAP[token]
                continue

            # (C) 팬덤 키워드인 경우 (해리포터, 나루토 등) -> 해당 팬덤 특성 추가
            if token in PARODY_FANDOM_MAP:
                add_trait(PARODY_FANDOM_MAP[token])
                continue

            # (D) 특성 패턴 매핑 (TRAIT_PATTERNS 순회)
            matched_trait = None
            for trait_name, patterns in TRAIT_PATTERNS:
                for pat in patterns:
                    if re.fullmatch(pat, token, re.IGNORECASE) or token == trait_name:
                        matched_trait = trait_name
                        break
                if matched_trait:
                    break

            if matched_trait:
                add_trait(matched_trait)
            else:
                # 특별 매핑: '연대' -> '연대물'
                if token in ["연대", "연대물", "칠령", "팔령", "구령"]:
                    add_trait("연대물")
                elif len(token) >= 2 and not token.isdigit():
                    # 만약 장르명이 내포되어 있다면
                    for g_key, g_val in GENRE_ALIAS_MAP.items():
                        if g_key in token:
                            if not primary_genre:
                                primary_genre = g_val
                            break

        # 만약 패러디 관련 특성이 있는데 primary_genre가 없다면 패러디로 설정
        if not primary_genre:
            for t in extracted_traits:
                if t in PARODY_FANDOM_MAP.values():
                    primary_genre = "패러디"
                    break

        # primary_genre가 식별되지 않았다면 None 반환 (웹 검색 등으로 위임)
        if not primary_genre:
            return None

        # primary_genre와 중복되는 특성 제거
        final_traits = [t for t in extracted_traits if t != primary_genre][:2]

        return cls.format_genre_tag(
            primary_genre=primary_genre,
            existing_keywords=final_traits
        )

    @staticmethod
    def parse_existing_tag(tag_str: str) -> Tuple[str, List[str]]:
        """
        태그 문자열 (예: "SF, 시스템" 또는 "언정, 궁투, 빙의" 또는 "현판 시스템")을 파싱하여
        메인 장르와 특징 키워드 목록으로 분리
        """
        if not tag_str:
            return "", []
            
        clean_tag = tag_str.strip(" []()")
        
        if "," in clean_tag:
            tokens = [t.strip() for t in clean_tag.split(",") if t.strip()]
        else:
            tokens = [t.strip() for t in clean_tag.split() if t.strip()]
            
        if not tokens:
            return "", []
            
        primary_genre = tokens[0]
        additional_keywords = []
        
        for kw in tokens[1:]:
            if kw and kw != primary_genre and kw not in additional_keywords:
                additional_keywords.append(kw)
                if len(additional_keywords) >= 2:
                    break
                    
        return primary_genre, additional_keywords

    @classmethod
    def extract_traits(
        cls,
        primary_genre: str,
        title: str = "",
        web_snippet: str = "",
        web_tags: Optional[List[str]] = None,
        existing_keywords: Optional[List[str]] = None
    ) -> List[str]:
        """
        메인 장르와 콘텍스트(제목, 웹 스니펫, 웹 태그 등)로부터 특징 키워드 추출 (최대 2개)
        """
        # 1. 기존 원본 태그 키워드가 지정되어 있으면 그대로 보존 (최우선)
        if existing_keywords is not None:
            return existing_keywords[:2]

        selected_traits: List[str] = []
        selected_set: Set[str] = set()
        selected_set.add(primary_genre)

        search_text_parts = [title]
        if web_tags:
            search_text_parts.extend(web_tags)
        if web_snippet:
            search_text_parts.append(web_snippet)
            
        combined_text = " ".join(search_text_parts)
        if not combined_text.strip():
            return selected_traits

        for trait_name, patterns in TRAIT_PATTERNS:
            if trait_name in selected_set:
                continue
                
            if trait_name == "빙의" and "책빙의" in selected_set:
                continue
            if trait_name == "말세" and "종말" in selected_set:
                continue
            if trait_name == "종말" and "말세" in selected_set:
                continue
            if trait_name == "궁정" and "궁투" in selected_set:
                continue
                
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    selected_traits.append(trait_name)
                    selected_set.add(trait_name)
                    if trait_name == "책빙의" and "빙의" in selected_traits:
                        selected_traits.remove("빙의")
                        selected_set.remove("빙의")
                    break
                    
            if len(selected_traits) >= 2:
                break
                
        return selected_traits[:2]

    @classmethod
    def format_genre_tag(
        cls,
        primary_genre: str,
        title: str = "",
        web_snippet: str = "",
        web_tags: Optional[List[str]] = None,
        existing_keywords: Optional[List[str]] = None
    ) -> str:
        """
        메인 장르와 추출된 특징 키워드를 포맷팅된 장르 문자열로 반환
        """
        if not primary_genre or primary_genre == "미분류":
            return primary_genre or "미분류"

        # 로판/로맨스의 경우 중국 웹소설 판단 시 '언정'으로 전환
        if primary_genre in ['로판', '로맨스', '로맨스판타지']:
            from core.utils.genre_mapping import GenreMappingLoader
            text_ctx = f"{web_snippet} {' '.join(web_tags or [])}"
            if GenreMappingLoader.is_chinese_romance(title, text_ctx):
                primary_genre = "언정"

        traits = cls.extract_traits(
            primary_genre=primary_genre,
            title=title,
            web_snippet=web_snippet,
            web_tags=web_tags,
            existing_keywords=existing_keywords
        )
        
        all_items = [primary_genre] + traits
        return ", ".join(all_items)
