"""
==============================================================================
파일: core/utils/chinese_phonetic_analyzer.py
역할 및 목적:
    중국 웹소설(치뎬, 진장 등)이 기계 번역 또는 한국식 한자음(음독/음차)으로 직역된
    특유의 파일명 패턴을 감지하고, 어휘 구조와 클리셰를 정밀 분석하여
    올바른 장르(현판, 선협, 무협, 판타지, 겜판, 언정 등)를 추론하는 전용 분석기.
주요 구성 요소:
    - ChinesePhoneticResult: 분석 결과 데이터클래스 (genre, confidence, matched_pattern, reason)
    - ChinesePhoneticAnalyzer: 음독/번역투 패턴 분석 엔진 클래스
==============================================================================
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import re


@dataclass
class ChinesePhoneticResult:
    """중국 소설 음독/번역투 분석 결과"""
    genre: str = "미분류"
    confidence: str = "none"         # 'high', 'medium', 'low', 'none'
    matched_pattern: str = ""
    reason: str = ""
    is_detected: bool = False


class ChinesePhoneticAnalyzer:
    """중국 웹소설 번역투 및 음독 제목 정밀 분석기"""

    # 1. 대표적인 중국어 문장형 제목 음독/직역 접두사 (Regex)
    PREFIX_PATTERNS = [
        # 这个 (Zhège) -> 이석, 저개, 이거
        (r'^(?:이석|저개|이개|이거)', '이석(这个: 이...)'),
        # 我真没想 (Wǒ zhēn méi xiǎng) -> 이신몰상, 아진몰상, 아몰상, 아진불상
        (r'^(?:이신몰상|아진몰상|아몰상|아진불상|이진몰상)', '이신몰상/아진몰상(我真没想: 내가 진짜 ~할 생각은 없었는데)'),
        # 我的 (Wǒ de) -> 이적, 아적
        (r'^(?:이적|아적)', '이적/아적(我的: 나의...)'),
        # 这就是 / 我就是 (Zhè jiùshì / Wǒ jiùshì) -> 이취시, 저취시, 아취시
        (r'^(?:이취시|저취시|아취시)', '이취시/아취시(这就是/我就是: 이것이 바로/내가 바로...)'),
        # 穿成 / 穿书 (Chuānchéng / Chuānshū) -> 천성, 천서, 천서후
        (r'^(?:천성|천서후|천서)', '천성/천서(穿成/穿书: ~로 빙의하다/책빙의...)'),
        # 别惹 (Biérě) -> 별야
        (r'^(?:별야)', '별야(别惹: ~를 건드리지 마라)'),
        # 全家 (Quánjiā) -> 전가
        (r'^(?:전가)', '전가(全家: 온 가족이...)'),
        # 我太想 (Wǒ tài xiǎng) -> 아태상, 아태
        (r'^(?:아태상|아태)', '아태상(我太想: 내가 너무...)'),
        # 我被迫 (Wǒ bèipò) -> 아피박
        (r'^(?:아피박)', '아피박(我被迫: 내가 억지로/강제로...)'),
        # 我合法 (Wǒ héfǎ) -> 아합법
        (r'^(?:아합법)', '아합법(我合法: 내가 합법적으로...)'),
        # 我成为 (Wǒ chéngwéi) -> 아성위, 아하위
        (r'^(?:아성위|아하위)', '아성위(我成为: 내가 ~가 된...)'),
        # 从...开始 (Cóng... kāishǐ) -> 종...개시, ...개시
        (r'^(?:종.+?개시|개시)', '종~개시(从~开始: ~부터 시작하다)'),
        # 开局 (Kāijú) -> 개국
        (r'^(?:개국)', '개국(开局: 시작부터...)'),
        # 妻子 / 娇妻 (Qīzi / Jiāoqī) -> 악자, 교처
        (r'^(?:악자|교처)', '악자/교처(妻子/娇妻: 아내/애교아내...)'),
    ]

    # 2. 음독 및 특수 어휘 기반 장르 매핑 규칙
    # (키워드 목록, 장르, 우선순위 가중치, 설명)
    TRAIT_RULES: List[Tuple[List[str], str, float, str]] = [
        # 선협 / 수선 (최고 우선순위 고유 장르)
        (
            [
                '수선', '修仙', '수진', '修真', '선협', '仙侠', '마두', '魔头',
                '대승기', '大乘期', '비승', '飞升', '도우', '道友', '선종', '종문',
                '축기', '금단', '원영', '화신', '연허', '합체', '천겁', '도겁',
                '선존', '선인', '단약', '영초', '영맥', '영근', '구도', '苟到',
                '불안투로', '척패', '자귀'
            ],
            '선협', 0.95, '선협/수선 고유 어휘'
        ),
        # 여성향 언정 (단총, 교처, 궁투, 택투, 리혼 등)
        (
            [
                '단총', '甜宠', '교처', '娇妻', '리혼', '이혼', '수부', '首富',
                '궁투', '宫斗', '택투', '宅斗', '복보', '福宝', '진천금', '가천금',
                '포태', '소내포', '시집', '시어머니', '부군', '낭자', '규수', '모친',
                '포회', '炮灰', '전처', '前妻', '천성', '穿成', '천서', '穿书',
                '천서후', '대도황', '逃荒', '도황', '대노', '大佬', '제전'
            ],
            '언정', 0.95, '중국 여성향(언정) 고유 클리셰'
        ),
        # 게임판타지 (생존유희, NPC, 유희 등)
        (
            [
                '생존유희', '生存游戏', 'NPC', '가상현실', '유희', '游戏', '로그인',
                '클래스', '퀘스트', '인던', '던전', '레벨업', '공략', '플레이어'
            ],
            '겜판', 0.90, '게임판타지/생존게임 클리셰'
        ),
        # 현대판타지: 말세 / 아포칼립스 / 좀비 / 생존
        (
            [
                '말세', '末世', '아포칼립스', '좀비', '생존', '대재앙', '빙하기',
                '멸망', '괴수', '변이', '돌연변이', '안식처', '피난처'
            ],
            '현판', 0.92, '말세(아포칼립스) 현대판타지'
        ),
        # 현대판타지: 무한류 / 복제 / 시스템 / 이능력 / 연예계 / 도시
        (
            [
                '무한 복제', '복제', '무한', '무한류', '스킬복사', '능력복사',
                '어신', '어장', '계통', '系统', '골드핑거', '사인', '출석체크',
                '역습', '모의기', '인생시뮬', '시뮬레이터', '신호', '재벌', '스타',
                '아이돌', '연예인', '감독', '배우', '상인'
            ],
            '현판', 0.88, '현대판타지/무한류/능력자 클리셰'
        ),
        # 판타지: 서양 판타지 / 악마 / 감옥 / 마왕
        (
            [
                '세모', '恶魔', '악마', '감옥', '교도소', '마왕', '용사', '마법',
                '소환', '이세계', '차원', '소드마스터', '드래곤', '엘프', '오크',
                '비아니스', '빌아니시'
            ],
            '판타지', 0.88, '서양 판타지/악마/이세계 클리셰'
        ),
        # 무협: 고전 무협 / 난세서 / 강호
        (
            [
                '난세서', '난세', '강호', '무림', '검황', '검성', '무신', '협객',
                '검협', '도협', '풍운', '비급', '소림', '무당', '화산', '마교'
            ],
            '무협', 0.92, '전통 무협/강호 클리셰'
        ),
        # 패러디
        (
            [
                '두라', '두라지', '斗罗', '마인크래프트', '포켓몬', '나루토', '원피스',
                '해리포터', '아이언맨', '에일리언', '마블'
            ],
            '패러디', 0.95, '원작 패러디'
        ),
    ]

    # 특정 유명 작품 직접 매핑
    KNOWN_TITLES: Dict[str, Tuple[str, str]] = {
        '난세서': ('무협', '희차 작가 명작 무협 소설 《乱世书》'),
        '이신몰상중생이': ('현판', '치뎬 메가히트 현대 일상/경영 회귀 소설 《我真没想重生啊》'),
        '아진몰상중생아': ('현판', '치뎬 메가히트 현대 일상/경영 회귀 소설 《我真没想重生啊》'),
        '아태상중생료': ('현판', '치뎬 현대 도시 회귀 소설 《我太想重生了》'),
        '빌아니시 귀': ('판타지', '판타지/코노스바 악마 패러디 계열 소설'),
        '빌아니시': ('판타지', '판타지/코노스바 악마 패러디 계열 소설'),
    }

    @classmethod
    def analyze(cls, text: str, pure_title: str = "") -> ChinesePhoneticResult:
        """
        중국 웹소설 기계번역/음독 제목을 분석하여 장르 판정
        
        Args:
            text: 원본 파일명 또는 파싱된 텍스트
            pure_title: 순수 제목 (옵션)
            
        Returns:
            ChinesePhoneticResult
        """
        result = ChinesePhoneticResult()
        
        # 1. 제목 정제
        target_title = (pure_title or text).strip()
        # 확장자 및 회차 제거
        cleaned = re.sub(r'\.[a-zA-Z0-9]+$', '', target_title)
        cleaned = re.sub(r'[\(\[\{].*?[\)\]\}]', '', cleaned).strip()
        cleaned = re.sub(r'\s*\d+[-~]\d+.*$', '', cleaned).strip()
        cleaned = re.sub(r'\s*\(완\).*$', '', cleaned).strip()

        # 2. 유명 작품 DB 직접 매칭
        for known_k, (genre, reason) in cls.KNOWN_TITLES.items():
            if known_k in target_title or known_k in cleaned:
                result.genre = genre
                result.confidence = "high"
                result.matched_pattern = known_k
                result.reason = reason
                result.is_detected = True
                return result

        # 3. 중국어 음독 접두사 감지
        has_prefix = False
        prefix_desc = ""
        for pat, desc in cls.PREFIX_PATTERNS:
            if re.search(pat, cleaned):
                has_prefix = True
                prefix_desc = desc
                break

        full_context = f"{text} {pure_title} {cleaned}".strip()

        # 4. 특별 클리셰: 사합원(四合院) 판정
        if any(kw in full_context for kw in ['사합원', '四合院', '4합원']):
            female_kws = ['여주', '교처', '낭자', '단총', '복보', '천금', '궁투', '택투', '시어머니', '시집', '포태', '이혼', '리혼']
            is_female = any(fk in full_context for fk in female_kws)
            result.genre = '언정' if is_female else '현판'
            result.confidence = 'high'
            result.matched_pattern = '사합원'
            result.reason = f"중국 시대극 사합원물 ({'여성향 언정' if is_female else '남성향 현대연대물'})"
            result.is_detected = True
            return result

        # 5. 특별 클리셰: 중생(重生 - 회귀/환생) 문맥 분기
        # '중생'은 남성향 도시물과 여성향 언정물 양쪽에서 가장 흔한 클리셰임!
        if any(kw in full_context for kw in ['중생', '重生']):
            female_kws = ['교처', '단총', '낭자', '궁투', '택투', '여주', '이혼', '리혼', '복보', '천금', '시어머니', '시집', '포태']
            has_female = any(fk in full_context for fk in female_kws)
            if has_female:
                result.genre = '언정'
                result.confidence = 'high'
                result.matched_pattern = '중생 + 여성향'
                result.reason = '중국 여성향 회귀 로맨스(언정)'
                result.is_detected = True
                return result
            else:
                # 남성향 도시/경영/일상/선협 중생
                if any(sk in full_context for sk in ['수선', '수진', '선협', '마두', '구도']):
                    result.genre = '선협'
                    result.reason = '수선 중생(선협 회귀물)'
                else:
                    result.genre = '현판'
                    result.reason = '도시/현대 중생(회귀물)'
                result.confidence = 'high' if has_prefix else 'medium'
                result.matched_pattern = '중생 (남성향/도시)'
                result.is_detected = True
                return result

        # 6. 특화 규칙 테이블 대조 (우선순위 순)
        for keywords, genre, conf_score, desc in cls.TRAIT_RULES:
            for kw in keywords:
                if kw in full_context:
                    result.genre = genre
                    result.confidence = "high" if (has_prefix or conf_score >= 0.92) else "medium"
                    result.matched_pattern = kw
                    result.reason = f"{desc} ('{kw}' 매칭{f', 접두사: {prefix_desc}' if has_prefix else ''})"
                    result.is_detected = True
                    return result

        # 7. 접두사만 매칭되고 세부 키워드는 없을 때의 기본 추론
        if has_prefix:
            # 이석(这个) / 이신몰상(我真没想) / 이취시(这就是) 등은 기본적으로 치뎬 남성향 현판/판타지가 대다수
            result.genre = "현판"
            result.confidence = "medium"
            result.matched_pattern = prefix_desc
            result.reason = f"중국 소설 음독 접두사({prefix_desc}) 감지, 현대/퓨전 기본 판정"
            result.is_detected = True
            return result

        return result
