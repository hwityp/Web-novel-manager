"""
==============================================================================
파일: core/utils/novel_origin_detector.py
역할 및 목적:
    소설의 파일명, 제목, 괄호 CJK 원문, 본문 헤더, 텍스트 인코딩 및 고유 클리셰 어휘를
    다각도로 분석하여 소설의 원산지 국적(KR: 한국, CN: 중국, JP: 일본, US: 영미 등)을
    자동으로 판별하는 소설 국적 감지 모듈.
주요 구성 요소:
    - OriginResult: 판별 결과 데이터클래스 (country, confidence, reasons, is_foreign)
    - NovelOriginDetector: 다계층 국적 판별 엔진 클래스
상호 연관 관계 및 의존성:
    - Caller: core.adapters.genre_classifier_adapter.GenreClassifierAdapter
    - Callee: core.utils.content_header_extractor.ContentHeaderResult, re, pathlib.Path
수정 시 주의사항:
    - 단서가 상충할 경우 가중치(번역 태그/원문 문자셋 > 본문 헤더 > 어휘/클리셰)를 우선 적용합니다.
    - 순수 한글로만 구성된 일반 소설은 기본적으로 'KR'(한국)로 판정하되, 불확실할 경우 'UNKNOWN'을 반환합니다.
==============================================================================
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Set
import re

from core.utils.content_header_extractor import ContentHeaderResult


@dataclass
class OriginResult:
    """소설 국적 판별 결과"""
    country: str = "UNKNOWN"          # 'KR', 'CN', 'JP', 'US', 'UNKNOWN'
    confidence: str = "none"          # 'high', 'medium', 'low', 'none'
    reasons: List[str] = field(default_factory=list)
    is_foreign: bool = False          # 해외 소설 여부 (True if country in ['CN', 'JP', 'US'])


class NovelOriginDetector:
    """한국 소설 vs 해외(중국/일본/영미) 소설 원산지 감지기"""

    # 1. 번역 마커 태그 정규식
    TRANSLATION_TAGS = re.compile(
        r'(?:\[|\()(?:[Aa][Ii]번역|번역본?|파파고|DeepL|구글번역|원서|번역)(?:\]|\))',
        re.IGNORECASE
    )

    # 2. 국가별 특정 출처/플랫폼 태그
    CN_SOURCE_TAGS = re.compile(
        r'(?:\[|\()(?:치뎬|치디엔|진장|진장문학|qidian|jjwxc|중소설|중국소설|중웹소)(?:\]|\))',
        re.IGNORECASE
    )
    JP_SOURCE_TAGS = re.compile(
        r'(?:\[|\()(?:나로우|소설가가\s*되자|카쿠요무|syosetu|kakuyomu|일소설|일본소설|일웹소|라노벨)(?:\]|\))',
        re.IGNORECASE
    )

    # 3. 일본어 가나 정규식 (히라가나, 카타카나)
    JAPANESE_KANA_REGEX = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')

    # 4. 한자 정규식 (CJK 통합 한자)
    CHINESE_CHAR_REGEX = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

    # 5. 중국 소설 고유 클리셰 및 어휘 패턴
    CN_TRAIT_KEYWORDS: Dict[str, str] = {
        # 시대/배경/여성향
        "사합원": "베이징 전통가옥(사합원)",
        "四合院": "베이징 전통가옥(四合院)",
        "지청": "하향 청년(지청/知青)",
        "知青": "하향 청년(知青)",
        "칠령": "70년대(칠령/七零)",
        "七零": "70년대(七零)",
        "팔령": "80년대(팔령/八零)",
        "八零": "80년대(八零)",
        "구령": "90년대(구령/九零)",
        "九零": "90년대(九零)",
        "농가복매": "농가복매(农家福妹)",
        "농문": "농문(农门)",
        "단총": "달달물(단총/甜宠)",
        "교처": "애교 아내(교처/娇妻)",
        "복보": "복덩이(복보/福宝)",
        "진천금": "진짜 딸(진천금/真千金)",
        "가천금": "가짜 딸(가천금/假千金)",
        "공간물자": "차원 공간/물자 비축",
        "수신공간": "휴대 공간(수신공간/随身空间)",
        "随身空间": "휴대 공간(随身空间)",
        "궁투": "황궁 암투(궁투/宫斗)",
        "宫斗": "황궁 암투(宫斗)",
        "택투": "가문 암투(택투/宅斗)",
        "宅斗": "가문 암투(宅斗)",
        "섭정왕": "섭정왕(摄政王)",
        "금의위": "황제 직속 호위(금의위)",
        "锦衣卫": "황제 직속 호위(锦衣卫)",
        "문혁": "문화대혁명",
        "개혁개방": "개혁개방",
        # 선협/수선
        "선협": "선협(仙侠)",
        "仙侠": "선협(仙侠)",
        "수선": "수선(修仙)",
        "修仙": "수선(修仙)",
        "수진": "수진(修真)",
        "修真": "수진(修真)",
        "축기": "수선 경지(축기/筑基)",
        "筑基": "수선 경지(筑基)",
        "원영": "수선 경지(원영/元婴)",
        "元婴": "수선 경지(元婴)",
        "금단": "수선 경지(금단/金丹)",
        "金丹": "수선 경지(金丹)",
        "비승": "선계 승천(비승/飞升)",
        "飞升": "선계 승천(飞升)",
        "도우": "수선자 호칭(도우/道友)",
        "道友": "수선자 호칭(道友)",
        "종문": "수선 문파(종문/宗门)",
        "宗门": "수선 문파(宗门)",
        "천겁": "천벌 겁화(천겁/天劫)",
        "渡劫": "겁화 극복(도겁/渡劫)",
        "선존": "선계 존자(선존/仙尊)",
        "仙尊": "선계 존자(仙尊)",
        # 직역투
        "적맹왕": "중국어 조사 '~적(的)' 직역",
        "~세계적": "중국어 조사 '~적(的)' 직역",
        "개국": "초반 전개(개국/开局)",
        "开局": "초반 전개(开局)",
        "출석체크": "시스템 싸인(签到)",
        "签到": "시스템 싸인(签到)",
    }

    # 6. 일본 소설 고유 클리셰 및 어휘 패턴
    JP_TRAIT_KEYWORDS: Dict[str, str] = {
        "악역영애": "여성향 악역영애(悪役令嬢)",
        "悪役令嬢": "여성향 악역영애(悪役令嬢)",
        "약혼파기": "약혼 파기(婚約破棄)",
        "婚約破棄": "약혼 파기(婚約破棄)",
        "단죄": "단죄 이벤트(断罪)",
        "断罪": "단죄 이벤트(断罪)",
        "익애": "무조건적 사랑(익애/溺愛)",
        "溺愛": "무조건적 사랑(溺愛)",
        "추방물": "파티 추방물(追放)",
        "追放": "파티 추방물(追放)",
        "슬로우라이프": "이세계 슬로우라이프",
        "スローライフ": "이세계 슬로우라이프",
        "이세계": "이세계(異世界)",
        "異世界": "이세계(異世界)",
        "전생": "전생(転生)",
        "転生": "전생(転生)",
        "치트": "치트 능력(チート)",
        "チート": "치트 능력(チート)",
        "무자각": "무자각 최강",
        "마왕": "판타지 마왕(魔王)",
        "용사": "소환된 용사(勇者)",
        "라이트노벨": "일본 라이트노벨",
        "라노벨": "일본 라이트노벨",
    }

    # 7. 한국 소설 고유 클리셰 및 어휘 패턴
    KR_TRAIT_KEYWORDS: Dict[str, str] = {
        "헌터": "K-현판 헌터",
        "각성자": "K-현판 각성자",
        "게이트": "K-현판 차원 게이트",
        "레이드": "K-현판 보스 레이드",
        "S급": "K-현판 랭크 시스템",
        "헌터협회": "K-현판 헌터협회",
        "길드장": "K-현판 길드",
        "국밥": "한국 고유 문화(국밥)",
        "재벌가": "한국 현대물(재벌가 막내 등)",
        "아이돌": "한국 연예계/엔터물",
        "작곡가": "한국 현대 전문직",
        "대한민국": "한국 배경",
        "서울": "한국 수도 배경",
        "조선": "한국 역사 배경",
        "고려": "한국 역사 배경",
        "신무협": "한국 창작 신무협",
    }

    @classmethod
    def detect(
        cls,
        title: str = "",
        raw_name: str = "",
        foreign_title: str = "",
        file_path: Optional[Path] = None,
        header_result: Optional[ContentHeaderResult] = None,
        genre: str = ""
    ) -> OriginResult:
        """
        다각적 단서를 결합하여 소설 원산지(국적) 판별
        
        Args:
            title: 소설 제목
            raw_name: 원본 파일명 (태그 포함)
            foreign_title: 괄호 CJK 원문 제목 (예: "四合院：重生54年...")
            file_path: 파일 경로 (인코딩 검사용)
            header_result: 본문 헤더 추출 결과
            genre: 현재까지 추론된 장르
            
        Returns:
            OriginResult(country, confidence, reasons, is_foreign)
        """
        result = OriginResult()
        full_text = f"{raw_name} {title}".strip()

        cn_score = 0
        jp_score = 0
        kr_score = 0
        reasons = []

        # -------------------------------------------------------------
        # 1. 특정 출처/플랫폼 태그 검사 (최우선 확정)
        # -------------------------------------------------------------
        if cls.CN_SOURCE_TAGS.search(full_text):
            cn_score += 100
            reasons.append("중국 플랫폼/출처 태그 감지 (치뎬/진장 등)")

        if cls.JP_SOURCE_TAGS.search(full_text):
            jp_score += 100
            reasons.append("일본 플랫폼/출처 태그 감지 (나로우/카쿠요무 등)")

        # -------------------------------------------------------------
        # 2. CJK 원문 제목 분석
        # -------------------------------------------------------------
        cjk_source = foreign_title
        if not cjk_source:
            # 제목 또는 파일명에서 괄호 CJK 추출 시도
            match = re.search(r'[\(\[\{（【〔［《〈｛]\s*([^\(\)\[\]\{\}（）【】〔〕［］《》〈〉｛｝]*[\u4e00-\u9fff\u3040-\u30ff][^\(\)\[\]\{\}（）【】〔〕［］《》〈〉｛｝]*)\s*[\)\]\}）】〕］》〉｝]', full_text)
            if match:
                cjk_source = match.group(1).strip()

        if cjk_source:
            if cls.JAPANESE_KANA_REGEX.search(cjk_source):
                jp_score += 80
                reasons.append(f"원문 제목에 일본어 가나(히라가나/카타카나) 포함: '{cjk_source}'")
            elif cls.CHINESE_CHAR_REGEX.search(cjk_source):
                cn_score += 70
                reasons.append(f"원문 제목에 한자(CJK) 표기 포함: '{cjk_source}'")

        # -------------------------------------------------------------
        # 3. 본문 헤더 및 텍스트 인코딩 검사
        # -------------------------------------------------------------
        if header_result:
            if header_result.is_foreign:
                # 헤더 원시 장르가 CJK인 경우
                if cls.JAPANESE_KANA_REGEX.search(header_result.raw_genre + " ".join(header_result.tags)):
                    jp_score += 60
                    reasons.append(f"본문 헤더에 일본어 메타데이터 감지 ({header_result.raw_genre})")
                elif cls.CHINESE_CHAR_REGEX.search(header_result.raw_genre + " ".join(header_result.tags)):
                    cn_score += 60
                    reasons.append(f"본문 헤더에 중국어 메타데이터 감지 ({header_result.raw_genre})")

        # 번역 마커 태그 감지
        has_translation_tag = bool(cls.TRANSLATION_TAGS.search(full_text))
        if has_translation_tag:
            reasons.append("번역 마커 태그([AI번역], (번역) 등) 감지")
            # 번역 태그가 있으면 중국 또는 일본 가산점 부여
            if cn_score > jp_score:
                cn_score += 30
            elif jp_score > cn_score:
                jp_score += 30
            else:
                cn_score += 20
                jp_score += 20

        # -------------------------------------------------------------
        # 4. 장르 기반 판별 가산점
        # -------------------------------------------------------------
        genre_clean = genre.strip(" []()")
        if "선협" in genre_clean:
            cn_score += 50
            reasons.append("고유 장르 '선협' (중국 오리지널 99%)")
        elif "언정" in genre_clean:
            cn_score += 50
            reasons.append("고유 장르 '언정' (중국 여성향 100%)")

        # -------------------------------------------------------------
        # 5. 고유 어휘 및 클리셰 패턴 검사
        # -------------------------------------------------------------
        combined_text = f"{full_text} {cjk_source}".strip()

        # (A) 중국 고유 어휘 검사
        for kw, desc in cls.CN_TRAIT_KEYWORDS.items():
            if kw in combined_text:
                cn_score += 40
                reasons.append(f"중국 고유 클리셰 어휘: {kw} ({desc})")
                break

        # (B) 일본 고유 어휘 검사
        for kw, desc in cls.JP_TRAIT_KEYWORDS.items():
            if kw in combined_text:
                jp_score += 40
                reasons.append(f"일본 고유 클리셰 어휘: {kw} ({desc})")
                break

        # (C) 한국 고유 어휘 검사 (해외 단서가 약할 때 유효)
        for kw, desc in cls.KR_TRAIT_KEYWORDS.items():
            if kw in full_text:
                kr_score += 25
                reasons.append(f"한국 고유 클리셰 어휘: {kw} ({desc})")
                break

        # -------------------------------------------------------------
        # 6. 최종 종합 점수 판정
        # -------------------------------------------------------------
        max_score = max(cn_score, jp_score, kr_score)

        if max_score >= 60:
            if cn_score >= max_score and cn_score > jp_score:
                result.country = "CN"
                result.confidence = "high"
                result.is_foreign = True
            elif jp_score >= max_score and jp_score > cn_score:
                result.country = "JP"
                result.confidence = "high"
                result.is_foreign = True
            elif kr_score >= max_score:
                result.country = "KR"
                result.confidence = "high"
                result.is_foreign = False
        elif max_score >= 25:
            if cn_score >= max_score and cn_score > jp_score:
                result.country = "CN"
                result.confidence = "medium"
                result.is_foreign = True
            elif jp_score >= max_score and jp_score > cn_score:
                result.country = "JP"
                result.confidence = "medium"
                result.is_foreign = True
            elif kr_score >= max_score:
                result.country = "KR"
                result.confidence = "medium"
                result.is_foreign = False
        else:
            # 해외 단서(cn_score, jp_score)가 전혀 없는 순수 한글 소설인 경우만 KR
            if cn_score == 0 and jp_score == 0 and not cjk_source and not has_translation_tag and re.search(r'[가-힣]{2,}', title or raw_name):
                result.country = "KR"
                result.confidence = "low"
                result.is_foreign = False
                reasons.append("해외 단서 부재, 순수 한글 명명 소설")
            else:
                result.country = "UNKNOWN"
                result.confidence = "none"
                result.is_foreign = False

        result.reasons = reasons
        return result
