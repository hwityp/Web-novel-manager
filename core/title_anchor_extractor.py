"""
==============================================================================
파일: core/title_anchor_extractor.py
역할 및 목적:
    복잡하고 오염된 원본 파일명에서 웹소설의 순수 핵심 제목(Title Anchor)을 추출하고,
    잔여 문자열에서 권수, 부/화 범위, 완결 여부, 외전 정보, 저자명을 고도로 정밀하게 분리 파싱.
    한글 자소 분리 복구(compose_korean_jamo), 외국어/외래어 및 한자 병기 표기([외국어/한자] 한글제목),
    대괄호/소괄호 메타데이터 정제 및 제목 보호 규칙을 전담합니다.
주요 구성 요소:
    - TitleAnchorExtractor: 메인 제목/메타데이터 추출기 클래스
    - ParsedTitleResult: 파싱 결과 데이터클래스 (title, author, volume_info, range_info, is_completed, side_story 등)
    - compose_korean_jamo(): 자소 분리 및 시각적 변형 복구 함수
상호 연관 관계 및 의존성:
    - Caller: core.adapters.filename_normalizer_adapter, core.adapters.genre_classifier_adapter,
              core.utils.novel_trait_extractor, scripts.*
    - Callee: re, unicodedata
수정 시 주의사항:
    - 제목 내부의 숫자(예: '100층의 올마스터', '1번가 기적')가 권수/범위 정규식에 의해 잘려나가지 않도록 Title Anchor 선추출 원칙을 엄수해야 합니다.
    - 외래어/한자 병기(예: "[선협] 구성성인, 선관소아양마(번역제목)") 파싱 시 원제와 번역제목의 맥락을 보존해야 합니다.
==============================================================================
"""
import re
import os
from dataclasses import dataclass
from typing import Tuple, Optional, List


def compose_korean_jamo(text: str) -> str:
    """
    한글 자소 분리 및 시각적 변형(야민정음식 알파벳 치환 등) 복구
    예: 'ㄷH공ㅂlㄱr' -> '대공비가'
    """
    if not text:
        return text
        
    # 1. 시각적 변형 영문자 -> 한글 자소 치환
    replacements = {
        'r': 'ㅏ', 'R': 'ㅏ', 'l': 'ㅣ', 'I': 'ㅣ', 'H': 'ㅐ', 'k': 'ㅏ',
        'o': 'ㅐ', 'i': 'ㅑ', 'j': 'ㅓ', 'p': 'ㅔ', 'u': 'ㅕ', 'h': 'ㅗ',
        'y': 'ㅛ', 'n': 'ㅜ', 'b': 'ㅠ', 'm': 'ㅡ'
    }
    
    chars = list(text)
    def is_hangul(c): return 0x3131 <= ord(c) <= 0x318E or 0xAC00 <= ord(c) <= 0xD7A3
    
    for idx, c in enumerate(chars):
        if c in replacements:
            # 영문자가 독립적인 단어가 아니라 한글과 붙어있을 때만 치환 (해리포터 등의 영문 오작동 방지)
            prev_is_hangul = idx > 0 and is_hangul(chars[idx-1])
            next_is_hangul = idx < len(chars)-1 and is_hangul(chars[idx+1])
            # [Fix] 영문 단어/단위(km, mb, rpm 등)의 일부인 경우 치환하지 않음
            # 인접한 다른 영문자가 있으면 영문 단어의 일부로 판단
            prev_is_alpha = idx > 0 and chars[idx-1].isascii() and chars[idx-1].isalpha()
            next_is_alpha = idx < len(chars)-1 and chars[idx+1].isascii() and chars[idx+1].isalpha()
            if prev_is_alpha or next_is_alpha:
                continue  # 영문 단어의 일부이므로 치환하지 않음
            if prev_is_hangul or next_is_hangul:
                chars[idx] = replacements[c]
                
    text = ''.join(chars)
    
    # 2. 자소 조합 로직
    CHOSUNG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    JUNGSUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
    JONGSUNG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    
    VOWEL_COMBINE = {('ㅗ', 'ㅣ'): 'ㅚ', ('ㅜ', 'ㅣ'): 'ㅟ', ('ㅡ', 'ㅣ'): 'ㅢ', ('ㅏ', 'ㅣ'): 'ㅐ', ('ㅓ', 'ㅣ'): 'ㅔ',
                     ('ㅗ', 'ㅏ'): 'ㅘ', ('ㅜ', 'ㅓ'): 'ㅝ', ('ㅜ', 'ㅔ'): 'ㅞ', ('ㅗ', 'ㅐ'): 'ㅙ'}
    
    def get_parts(char):
        if '가' <= char <= '힣':
            offset = ord(char) - 0xAC00
            j = offset % 28
            m = (offset // 28) % 21
            c = (offset // 28) // 21
            return c, m, j
        return None
        
    def make_char(c, m, j=0):
        return chr(0xAC00 + c * 588 + m * 28 + j)
        
    chars = list(text)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(chars) - 1:
            c1, c2 = chars[i], chars[i+1]
            # 초성 + 중성 -> 완성형
            if c1 in CHOSUNG and c2 in JUNGSUNG:
                c_idx = CHOSUNG.index(c1)
                m_idx = JUNGSUNG.index(c2)
                chars[i:i+2] = [make_char(c_idx, m_idx, 0)]
                changed = True
                break
            
            parts1 = get_parts(c1)
            # 완성형(종성없음) + 종성/중성 결합
            if parts1 and parts1[2] == 0:
                c, m, _ = parts1
                # 종성 결합
                if c2 in JONGSUNG and c2 != '':
                    # 뒤에 모음이 오면 종성이 아니라 다음 글자의 초성이어야 함
                    if i + 2 < len(chars) and chars[i+2] in JUNGSUNG:
                        pass
                    else:
                        j_idx = JONGSUNG.index(c2)
                        chars[i:i+2] = [make_char(c, m, j_idx)]
                        changed = True
                        break
                # 이중 모음 결합 (ㅗ+ㅣ = ㅚ 등)
                vowel1 = JUNGSUNG[m]
                if (vowel1, c2) in VOWEL_COMBINE:
                    new_vowel = VOWEL_COMBINE[(vowel1, c2)]
                    m_idx = JUNGSUNG.index(new_vowel)
                    chars[i:i+2] = [make_char(c, m_idx, 0)]
                    changed = True
                    break
            i += 1
    return ''.join(chars)


CJK_CHAR_REGEX = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff]')


def parse_foreign_title_info(text: str) -> dict:
    """
    해외(중/일) 웹소설 제목 분석 및 3가지 유형 구분
    1) sino_korean: 원문 제목(간체/번체)을 한국식 한자음으로 적은 경우 (예: 아가낭자타강산(我家娘子打江山))
    2) translation: 원문 제목을 한국어로 번역해서 적은 경우 (예: 말세: 여인이 소모한 물자는 만 배로 돌려받는다 (末世：女人消耗的物资万倍返还))
    3) parallel: 원문 제목과 번역문(또는 한자음)을 함께 적은 경우 (예: 아가낭자타강산 : 말세: 여인이 소모한 물자는 만 배로 돌려받는다 (我家娘子打江山))
    """
    result = {
        'clean_title': text,
        'original_foreign_title': '',
        'foreign_type': '',  # 'sino_korean', 'translation', 'parallel'
    }
    
    if not text or not CJK_CHAR_REGEX.search(text):
        return result

    # 1. 괄호 안의 CJK 원문 추출
    paren_cjk_match = re.search(r'[\(\[\{]\s*([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\s：:，,！!？?·]+)\s*[\)\]\}]', text)
    cjk_title = ""
    korean_part = text
    
    if paren_cjk_match:
        cjk_title = paren_cjk_match.group(1).strip()
        korean_part = (text[:paren_cjk_match.start()] + " " + text[paren_cjk_match.end():]).strip()
    else:
        # 괄호 없이 한자가 포함된 경우
        cjk_match = re.search(r'([\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff]{2,}[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\s：:，,！!？?·]*)', text)
        if cjk_match:
            cjk_title = cjk_match.group(1).strip()
            korean_part = (text[:cjk_match.start()] + " " + text[cjk_match.end():]).strip()
            korean_part = re.sub(r'^\s*[-–—:]\s*|\s*[-–—:]\s*$', '', korean_part).strip()

    CJK_MARKER_CHARS = set("完外番全卷部編篇結終上下中0123456789一二三四五六七八九十백천만")

    if not cjk_title or all(c in CJK_MARKER_CHARS or c.isspace() or c in "+-~,.:/[]()_·" for c in cjk_title):
        return result

    result['original_foreign_title'] = cjk_title
    korean_part_clean = re.sub(r'[\s_]+', ' ', korean_part).strip()
    
    # 2. 유형 판단 (sino_korean, translation, parallel)
    has_particles = bool(re.search(r'(?:가|이|은|는|을|를|의|에|에서|로|으로|와|과|도|만|한|적|하는|받는다|다)(?:\s|:|$)', korean_part_clean))
    
    # 병기(parallel)는 한자음 제목과 번역문 제목이 구분자('-', '[ ]', '/')로 조합된 형태
    is_parallel = False
    if '-' in korean_part_clean or ('[' in korean_part_clean and ']' in korean_part_clean) or '/' in korean_part_clean:
        is_parallel = True

    if is_parallel:
        result['foreign_type'] = 'parallel'
    elif has_particles:
        result['foreign_type'] = 'translation'
    else:
        result['foreign_type'] = 'sino_korean'

    result['clean_title'] = korean_part_clean
    return result


@dataclass
class TitleParseResult:
    """제목 파싱 결과 데이터클래스"""
    title: str                    # 추출된 핵심 제목
    author: str = ""              # 저자명
    volume_info: str = ""         # 권/부 정보 (예: "1-2부")
    range_info: str = ""          # 범위 정보 (예: "1-536")
    is_completed: bool = False    # 완결 여부
    side_story: str = ""          # 외전 정보 (예: "외전 1-5")
    extension: str = ""           # 파일 확장자
    original_genre: str = ""      # 파일명에서 추출한 장르 (예: "현판")
    edition_info: str = ""        # 판본 정보 (예: "[개정판]") - 파일명에 보존
    original_foreign_title: str = ""  # 원문 제목 (예: "我家娘子打江山" 또는 "末世：女人消耗的物资万倍返还")
    foreign_title_type: str = ""      # "sino_korean", "translation", "parallel", ""
    
    def to_normalized_filename(self, genre: str = "") -> str:
        """
        정규화된 파일명 생성
        형식: [장르] 제목 부정보 범위 (완) + 외전.확장자
        """
        parts = []
        
        # 장르 (입력된 장르 > 원본 추출 장르 순)
        final_genre = genre or self.original_genre
        if final_genre:
            clean_g = final_genre.strip(" []()")
            parts.append(f"[{clean_g}]")
        
        # 제목 및 원문 제목 조합
        title_str = self.title
        if self.original_foreign_title and self.original_foreign_title not in title_str:
            title_str = f"{title_str} ({self.original_foreign_title})"
            
        parts.append(title_str)

        # 판본 정보 (제목 바로 뒤 - 예: [개정판])
        if self.edition_info:
            parts.append(self.edition_info)
        
        # 부 정보
        if self.volume_info:
            parts.append(self.volume_info)
        
        # 범위 정보
        if self.range_info:
            parts.append(self.range_info)
        
        # 완결 여부
        if self.is_completed:
            parts.append("(완)")
        
        # 외전 정보
        if self.side_story:
            parts.append(f"+ {self.side_story}")
        
        filename = " ".join(parts)
        
        # 확장자
        if self.extension:
            filename += self.extension
        
        return filename


class TitleAnchorExtractor:
    """제목 앵커 추출 및 잔여 문자열 파싱 클래스"""

    # 장르 정규화 맵 (복합 번역 태그에서 추출한 장르 토큰 → 표준 장르)
    GENRE_NORMALIZATION_MAP = {
        '현대 판타지': '현판', '현대판타지': '현판', '현판': '현판',
        '무협': '무협', '신무협': '무협', '퓨전무협': '무협', '퓨전 무협': '무협',
        '판타지': '판타지',
        '로맨스 판타지': '로판', '로맨스판타지': '로판', '로판': '로판',
        '게임 판타지': '겜판', '게임판타지': '겜판', '겜판': '겜판',
        '퓨전 판타지': '퓨판', '퓨전판타지': '퓨판', '퓨판': '퓨판',
        '선협': '선협', '역사': '역사',
        '공포': '공포', '스포츠': '스포츠', '언정': '언정',
    }
    
    # 노이즈 패턴 (저자명, 번역 정보 등)
    AUTHOR_PATTERNS = [
        r'@\S+',                           # @닉네임
        r'ⓒ\S+',                           # ⓒ닉네임
        r'©\S+',                           # ©닉네임
        r'(?<!\S)저자[:\s]*\S+',           # 저자: 이름 (단어 앞 경계 확인)
        r'(?<!\S)작가[:\s]*\S+',           # 작가: 이름
        r'(?<!\S)글[:\s]*\S+',             # 글: 이름
        r'(?<!\S)by\s+\S+',                # by Author
    ]
    
    # 사이트/카페 정보 패턴
    SITE_PATTERNS = [
        r'(?:www\.)?[\w-]+\.(?:com|net|co\.kr|kr|cafe)',  # 도메인
        r'네이버\s*카페',
        r'다음\s*카페',
        r'문피아',
        r'조아라',
        r'카카오페이지',
        r'시리즈',
    ]
    
    # 번역 정보 패턴
    TRANSLATOR_PATTERNS = [
        r'(?<!\S)번역[:\s]*\S+',
        r'(?<!\S)역자[:\s]*\S+',           # "역자: 이름" (면역자 등 오매칭 방지)
        r'\[번역\]',
        r'\(번역\)',
    ]
    
    # 장르 태그 패턴 (장르로 추출 + 제거 대상) - 완결/판본 태그는 제외
    GENRE_TAG_PATTERNS = [
        r'\[(?:판타지|무협|현판|퓨판|로판|겜판|역사|선협|언정|공포|스포츠|소설|패러디|현대|미스터리|밀리터리|단행본|연재중|미분류)(?:[\s,]+[^\]]+)*\]',
        r'\((?:판타지|무협|현판|퓨판|로판|겜판|역사|선협|언정|공포|스포츠|소설|패러디|현대|미스터리|밀리터리|단행본|연재중|미분류)(?:[\s,]+[^\)]+)*\)',
    ]

    # 판본/에디션 태그 (제거하되 장르로 추출하지 않음 - 제목에도 포함하지 않음)
    # 단, [개정판]처럼 TitleParseResult.volume_info에 메모하지 않음 (현재 구조상 단순 제거)
    EDITION_TAG_PATTERNS = [
        r'\[(?:개정판|완전판|수정판|합본|특별판|무삭제판|개정증보판)\]',
        r'\((?:개정판|완전판|수정판|합본|특별판|무삭제판|개정증보판)\)',
    ]
    
    # 성인 등급 태그 패턴 (제거 대상)
    ADULT_TAG_PATTERNS = [
        r'\(\s*19금\s*\)',                  # (19금)
        r'\[\s*19금\s*\]',                  # [19금]
        r'\(\s*15금\s*\)',                  # (15금)
        r'\[\s*15금\s*\]',                  # [15금]
        r'\(\s*성인\s*\)',                  # (성인)
        r'\[\s*성인\s*\]',                  # [성인]

    ]
    
    # 플랫폼/번역자 태그 패턴 (제거 대상)
    PLATFORM_TAG_PATTERNS = [
        r'\[임아소\]',
        r'\[네이버시리즈\]',
        r'\[카카오페이지\]',
        r'\[문피아\]',
        r'\[조아라\]',
        r'\[리디북스\]',
        r'\[노벨피아\]',
        r'\(\s*AI번역\s*\)',                 # (AI번역) 단독
        r'\[\s*AI번역\s*\]',                 # [AI번역] 단독
        r'\(\s*AI\s*번역\s*\)',
        r'\[\s*AI\s*번역\s*\]',
        r'\[\s*(?:소설|웹소설)\s*(?:-\s*텍|텍본|txt)?\s*\]',
        r'\(\s*(?:소설|웹소설)\s*(?:-\s*텍|텍본|txt)?\s*\)',
        r'\[\s*텍본\s*\]',
        r'\(\s*텍본\s*\)',
    ]

    
    # 완결 마커 패턴
    COMPLETION_PATTERNS = [
        r'(?<!\S)(?:完|완)[\s,]*\+?[\s,]*(?:外|외(?:전|포)?)(?!\S)',  # 完外, 완+외전, 完+外 등 복합 마커
        r'\(\s*완결\s*\)',                  # (완결)
        r'\[\s*완결\s*\]',                  # [완결]
        r'\(\s*完\s*\)',                    # (完)
        r'\[\s*完\s*\]',                    # [完]
        r'\(\s*완\s*\)',                    # (완)
        r'\[\s*완\s*\]',                    # [완]
        r'(?<!\S)完(?!\S)',                 # 完 (독립된 문자)
        r'(?<!\S)완(?!\S)',                 # 완 (독립된 문자)
        r'(?<!\S)완결(?!\S)',               # 완결 (독립된 문자)
        r'(?<!\S)完\s*(?=\+)',              # 完 (뒤에 +가 오는 경우) [NEW]
        r'(?<!\S)완\s*(?=\+)',              # 완 (뒤에 +가 오는 경우) [NEW]
        r'\(\s*Complete\s*\)',              # (Complete)
        r'\(\s*END\s*\)',                   # (END)
        r'\(\s*Fin\s*\)',                   # (Fin)
        r'본편\s*완결',                      # 본편 완결
        
        # [Fix] 숫자나 단위 뒤에 붙은 완결 마커 지원 (예: 1부完, 5권완)
        r'(?<=[0-9화권부편회장])完(?!\S)',    # 숫자/단위 뒤에 붙은 完
        r'(?<=[0-9화권부편회장])완(?!\S)',    # 숫자/단위 뒤에 붙은 완
        r'(?<=[0-9화권부편회장])완결(?!\S)',  # 숫자/단위 뒤에 붙은 완결
    ]
    
    # 외전 마커 패턴
    SIDE_STORY_PATTERNS = [
        r'番外',                            # 번외 (한자)
        r'번외',                            # 번외 (한글) [NEW]
        r'외전',
        r'후기',
        r'에필로그',
        r'에필',
        r'특별편',
        r'번외편',
        r'스핀오프',
        r'후일담',
        r'특외',
        r'외포',                             # 외전 포함 [NEW]
        r'外',                              # 外 (외전 단축) [NEW]
        r'번외포함',                         # 번외포함 [NEW]
    ]
    
    # 중국 소설 제목 패턴 (~지, ~기로 끝나는 제목)
    # 주의: "역전기"는 한국어 제목이므로 제외
    CHINESE_TITLE_ENDINGS = [
        '지', '록', '담', '기담', '전기', '열전', '비록', '야사',
        '연의', '지전', '기전', '행기', '유기', '몽기', '환기', '선기',
    ]
    
    # 중국 소설 패턴에서 제외할 한국어 단어
    KOREAN_TITLE_EXCEPTIONS = [
        '역전기',  # 인생 역전기
        '전기',    # 전기 (electricity)
        '일기',    # 일기 (diary)
        '세기',    # 세기 (century)
        '용기',    # 용기 (courage)
        '인기',    # 인기 (popularity)
        '무도',    # 무도 인생
    ]
    
    def __init__(self):
        """TitleAnchorExtractor 초기화"""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """정규식 패턴 컴파일"""
        all_noise = self.AUTHOR_PATTERNS + self.SITE_PATTERNS + self.TRANSLATOR_PATTERNS
        self.noise_pattern = re.compile('|'.join(all_noise), re.IGNORECASE)
        
        # 장르 태그 패턴 (장르 추출 후 제거)
        self.genre_tag_pattern = re.compile('|'.join(self.GENRE_TAG_PATTERNS), re.IGNORECASE)

        # 판본 태그 패턴 (장르 추출 없이, 파일명에서 제거하되 edition_info로 보존)
        self.edition_tag_pattern = re.compile('|'.join(self.EDITION_TAG_PATTERNS), re.IGNORECASE)

        # 장르+번역 복합 태그 패턴 (장르 부분만 추출하여 genre로 사용)
        # 예: [현대 판타지 AI번역] → 장르: '현판', 태그 전체 제거
        self.genre_translation_pattern = re.compile(
            r'\[([가-힣\s]+?)\s*(?:[Aa][Iㅣl]?번역|AI번역|기계번역|손번역|번역)\]',
            re.IGNORECASE
        )
        
        # 성인 등급 태그 패턴
        self.adult_tag_pattern = re.compile('|'.join(self.ADULT_TAG_PATTERNS), re.IGNORECASE)
        
        # 플랫폼/번역자 태그 패턴
        self.platform_tag_pattern = re.compile('|'.join(self.PLATFORM_TAG_PATTERNS), re.IGNORECASE)
        
        # 완결 마커 패턴
        self.completion_pattern = re.compile('|'.join(self.COMPLETION_PATTERNS), re.IGNORECASE)
        
        # 외전 마커 패턴 (+ 외전, + 에필 등)
        self.side_story_pattern = re.compile(
            r'\s*\+\s*(?:' + '|'.join(self.SIDE_STORY_PATTERNS) + r').*',
            re.IGNORECASE
        )
        
        # [NEW] 단독 외전 패턴 (compile dynamically from SIDE_STORY_PATTERNS)
        # 예: " 제목 ... 외전 1" 또는 "외전"
        self.standalone_side_pattern = re.compile(
            r'(?:^|\s+)(' + '|'.join(self.SIDE_STORY_PATTERNS) + r')(?:\s*\d*[-~]?\d*)?(?:\s|$)',
            re.IGNORECASE
        )
        
        # 범위 패턴 (1-536, 1~536, 1-536화, 1-536권, _1_536 등)
        self.range_pattern = re.compile(r'(\d+)\s*[-~_]\s*(\d+)\s*[화권부편회장]?')
        
        # 단일 숫자 패턴 (120, 126 등 - 끝에 있는 단일 숫자)
        # [UPDATED] 뒤에 부/권 등의 단위가 오거나 완결 마커, 또는 외전/에필/번외 등, 또는 문자열 끝인 경우 매칭
        # 단, '회차가'처럼 단위 뒤에 다른 문자가 연달아 나오는 경우는 제외
        self.single_number_pattern = re.compile(
            r'\s+(\d+)(?=\s*(?:完|완|\(완\)|\(完\)|\s*(?:[화권부편회장]|본편)(?:\s|$|完|완|\(완\)|\(完\)|[,\(\[\+])|\s*\d+\s*(?:[화권부편회장]|본편)(?:\s|$|完|완|\(완\)|\(완\)|[,\(\[\+])|\s*(?:에필|에필로그|외전|번외|특별편|番外|번외포함|본편)|\s*$))'
        )
        
        # 저자 구분자 패턴 (제목 - 저자)
        self.author_separator_pattern = re.compile(r'\s+[-–—]\s+([^-–—]+)$')
    
    def extract(self, raw_name: str) -> TitleParseResult:
        """파일명에서 제목과 메타데이터 추출"""
        # 1. 확장자 분리
        name, extension = self._split_extension(raw_name)
        
        # 빈 이름 처리
        if not name:
            return TitleParseResult(title="", extension=extension)
            
        # [NEW] 한글 자소 분리 및 시각적 변형 텍스트를 정상 한글로 조립
        name = compose_korean_jamo(name)
        
        # 2. 노이즈 제거 및 장르/판본 추출
        cleaned, author, original_genre, edition_info = self._remove_noise(name)
        
        # [NEW] 해외(중/일) 소설 제목 파싱 (원문 한자 제목 및 3가지 유형 추출)
        foreign_info = parse_foreign_title_info(cleaned)
        original_foreign_title = foreign_info['original_foreign_title']
        foreign_title_type = foreign_info['foreign_type']
        if foreign_info['clean_title']:
            cleaned = foreign_info['clean_title']
        
        # 3. 제목 앵커 추출
        title, residual = self._extract_title_anchor(cleaned)
        
        # 4. 잔여 문자열에서 메타데이터 파싱
        volume_info, range_info, is_completed, side_story, author_from_res = self._parse_residual(residual)
        
        final_author = author or author_from_res
        
        return TitleParseResult(
            title=title.strip(),
            author=final_author.strip(),
            volume_info=volume_info,
            range_info=range_info,
            is_completed=is_completed,
            side_story=side_story,
            extension=extension,
            original_genre=original_genre,
            edition_info=edition_info,
            original_foreign_title=original_foreign_title,
            foreign_title_type=foreign_title_type
        )
    
    def _split_extension(self, filename: str) -> Tuple[str, str]:
        """파일명에서 확장자 분리"""
        if not filename:
            return "", ""
        # 파일명이 확장자로만 시작하는 경우 (예: ".txt")
        if filename.startswith('.') and '.' not in filename[1:]:
            return "", filename
        
        name, ext = os.path.splitext(filename)
        
        # 유효한 확장자인지 확인 (알파벳으로만 구성, 최대 10자)
        # 예: .txt, .epub, .zip 등은 유효, ". (완)" 같은 것은 무효
        if ext and len(ext) <= 11:  # . 포함 최대 11자
            ext_without_dot = ext[1:]  # . 제거
            if ext_without_dot.isalnum():
                return name, ext
        
        # 유효하지 않은 확장자면 전체를 이름으로 반환
        return filename, ""
    
    def _remove_noise(self, name: str) -> Tuple[str, str, str, str]:
        """노이즈 제거, 저자명 추출, 장르 태그 추출, 판본 정보 추출"""
        author = ""
        genre = ""
        edition_info = ""
        
        # [0] 첨언에서 장르 우선 추출 (해시태그, 대괄호 태그 등)
        if not genre:
            from core.utils.novel_trait_extractor import NovelTraitExtractor
            extracted_g = NovelTraitExtractor.extract_from_annotations(name)
            if extracted_g:
                genre = extracted_g

        # [0.1] 해시태그 패턴 제거 (#패러디, #해리포터, #명탐정 코난 등)
        name = re.sub(r'#([가-힣a-zA-Z0-9_]+(?:\s+(?!\d+|완결?|完|외전|후기|에필)[가-힣a-zA-Z0-9_]+)*)', '', name)

        # 노이즈 패턴 제거
        name = self.noise_pattern.sub('', name)

        # [0.5] 선행 연속 대괄호 메타데이터 태그 감지 및 제거 ([언정][AI번역][연대], [나루토패러디 시스템 AI번역] 등)
        META_TAG_KEYWORDS = [
            'AI번역', '기계번역', '손번역', '번역', '텍본', '소설', '웹소설',
            '패러디', '언정', '선협', '무협', '현판', '로판', '겜판', '판타지', '퓨판', 'SF', '역사', '스포츠', '공포', '미스터리', '밀리터리',
            '시스템', '연대', '사합원', '궁투', '빙의', '책빙의', '공간', '농촌', '말세', '종말',
            '해리포터', '나루토', '원피스', '드래곤볼', '포켓몬', '코난', '명탐정 코난', '명탐정코난', '주술회전', '귀멸의 칼날'
        ]
        while True:
            prefix_bracket = re.match(r'^\s*\[([^\]]+)\]', name)
            if not prefix_bracket:
                break
            bracket_content = prefix_bracket.group(1).strip()
            # 판본 태그인 경우 edition_match에서 별도 처리하도록 break
            if re.match(r'^(?:개정판|완전판|수정판|합본|특별판|무삭제판|개정증보판)$', bracket_content):
                break
            is_meta = any(kw in bracket_content for kw in META_TAG_KEYWORDS)
            if is_meta or ',' in bracket_content:
                if not genre:
                    from core.utils.novel_trait_extractor import NovelTraitExtractor
                    extracted_g = NovelTraitExtractor.extract_from_annotations(prefix_bracket.group(0))
                    if extracted_g:
                        genre = extracted_g
                name = name[prefix_bracket.end():].lstrip()
            else:
                break

        # [1] 장르+번역 복합 태그 처리 (최우선)
        # 예: [현대 판타지 AI번역] → 장르='현판', 태그 제거
        if not genre:
            trans_match = self.genre_translation_pattern.search(name)
            if trans_match:
                raw_genre_part = trans_match.group(1).strip()
                genre = self._normalize_genre_token(raw_genre_part)
                name = name[:trans_match.start()] + name[trans_match.end():]

        # [2] 순수 장르 태그 추출 ([현판], [무협] 등)
        if not genre:
            genre_match = self.genre_tag_pattern.search(name)
            if genre_match:
                raw_genre = genre_match.group(0)
                genre = re.sub(r'[\[\]\(\)]', '', raw_genre).strip()
                name = self.genre_tag_pattern.sub('', name)

        # [3] 판본 태그 처리 ([개정판], [합본] 등 - 장르 추출 없이 파일명에 보존)
        edition_match = self.edition_tag_pattern.search(name)
        if edition_match:
            edition_info = edition_match.group(0).strip()  # 예: "[개정판]"
            # 태그 제거 후 양쪽 공백 정리
            name = name[:edition_match.start()].rstrip() + " " + name[edition_match.end():].lstrip()

        # 성인 등급 태그 제거
        name = self.adult_tag_pattern.sub('', name)
        
        # 플랫폼/번역자 태그 제거
        name = self.platform_tag_pattern.sub('', name)
        
        # 연속 공백 정리
        name = ' '.join(name.split())
        
        return name.strip(), author, genre, edition_info

    def _normalize_genre_token(self, raw: str) -> str:
        """장르 토큰을 표준 장르로 정규화 (GENRE_NORMALIZATION_MAP 참조)"""
        raw = raw.strip()
        if raw in self.GENRE_NORMALIZATION_MAP:
            return self.GENRE_NORMALIZATION_MAP[raw]
        # 공백 제거 후 재시도 (예: '현대 판타지' → '현대판타지')
        raw_no_space = raw.replace(' ', '')
        for key, val in self.GENRE_NORMALIZATION_MAP.items():
            if key.replace(' ', '') == raw_no_space:
                return val
        return raw  # 알 수 없는 장르면 원본 반환

    def _extract_title_anchor(self, cleaned: str) -> Tuple[str, str]:
        """제목 앵커 추출"""
        if not cleaned:
            return "", ""
        
        # 중국 소설 패턴 확인
        if self._is_chinese_novel_title(cleaned):
            return self._extract_chinese_title(cleaned)
        
        return self._extract_general_title(cleaned)
    
    def _is_chinese_novel_title(self, name: str) -> bool:
        """중국 소설 제목 패턴인지 확인"""
        # 외전/에필 등의 키워드가 있으면 중국 소설 패턴이 아님
        if re.search(r'\+\s*(?:외전|에필|번외|특별편)', name):
            return False
        
        # 한국어 예외 단어 확인
        for exception in self.KOREAN_TITLE_EXCEPTIONS:
            if exception in name:
                return False
        
        # 제목 끝이 중국 소설 특유의 패턴인지 확인
        # 패턴: 한글제목 + 중국식 어미 + 공백/숫자 (제목 시작 부분에서만)
        for ending in self.CHINESE_TITLE_ENDINGS:
            # 제목 시작 부분에서 중국식 어미를 찾음
            pattern = rf'^[\uAC00-\uD7A3]+{ending}(?:\s+\d|\s*$)'
            if re.search(pattern, name):
                return True
        return False
    
    def _extract_chinese_title(self, name: str) -> Tuple[str, str]:
        """중국 소설 제목 추출"""
        for ending in self.CHINESE_TITLE_ENDINGS:
            pattern = rf'([\uAC00-\uD7A3\s]+{ending})(\s+.*)$'
            match = re.search(pattern, name)
            if match:
                title = match.group(1).strip()
                residual = match.group(2).strip() if match.group(2) else ""
                return title, residual
        return self._extract_general_title(name)
    
    def _extract_general_title(self, name: str) -> Tuple[str, str]:
        """일반 제목 추출"""
        # 1. 외전/에필 + 패턴 먼저 분리 (+ 기호가 있는 경우)
        # 패턴: "제목 1-100 (완) + 외전 1-79"
        side_pattern_str = r'\s+\+\s+(?:' + '|'.join(self.SIDE_STORY_PATTERNS) + r').*'
        plus_match = re.search(side_pattern_str, name, re.IGNORECASE)
        if plus_match:
            main_part = name[:plus_match.start()].strip()
            side_part = name[plus_match.start():].strip()
            title, residual = self._extract_title_from_main(main_part)
            residual = (residual + " " + side_part).strip()
            return title, residual
        
        return self._extract_title_from_main(name)
    
    def _extract_title_from_main(self, name: str) -> Tuple[str, str]:
        """메인 파트에서 제목 추출 (Earliest Match Strategy)"""
        # 검색할 패턴 목록과 식별자
        # (패턴 객체, 우선순위 설명)
        candidates = []
        
        # 1. 단위 패턴 (1화, 50권, 1부, 165본편 등)
        unit_match = re.search(r'(?:[\s_]|(?<=[.!?？!！]))\s*\d+\s*(?:[화권부편회장]|본편)(?:\s|$|[,\(\[\+])', name)
        if unit_match:
            candidates.append(unit_match)
            
        # 2. 숫자 범위 패턴 (1-536, 1~100, _1_222 등)
        range_match = re.search(r'(?:[\s_]|(?<=[.!?？!！]))\s*\d+\s*[-~_]\s*\d+', name)
        if range_match:
            candidates.append(range_match)
            
        # 3. 단일 숫자 패턴 (120, 126 등 - 끝에 있는 단일 숫자)
        # [UPDATED] Use compiled pattern
        single_num_match = self.single_number_pattern.search(name)
        if single_num_match:
            candidates.append(single_num_match)
            
        # 4. 완결 마커 패턴 (괄호형)
        paren_completion_match = re.search(r'\.?\s*[\(\[]\s*완(?:결)?\s*[\)\]]\.?\s*$', name)
        if paren_completion_match:
            candidates.append(paren_completion_match)
        # 5. 일반 완결 마커
        completion_match = self.completion_pattern.search(name)
        if completion_match:
            candidates.append(completion_match)
            
        # 후보가 없다면 전체가 제목
        if not candidates:
            return name.strip(), ""
            
        # 가장 앞서 등장하는 매칭 선택 (Earliest Match)
        # start() 인덱스가 가장 작은 것을 선택
        best_match = min(candidates, key=lambda m: m.start())
        
        title = name[:best_match.start()].strip()
        # 제목 끝의 마침표 제거 (완결 마커인 경우에만 주로 해당하지만 안전하게 처리)
        if best_match == paren_completion_match:
            title = title.rstrip('.')
            
        # 제목 끝의 연재/련재 상태 노이즈 제거
        title = re.sub(r'[\s_]+(?:련재|연재|연재중|련재중)$', '', title)
            
        residual = name[best_match.start():].strip()
        
        return title, residual
    
    def _parse_residual(self, residual: str) -> Tuple[str, str, bool, str, str]:
        """잔여 문자열에서 메타데이터 파싱"""
        residual = residual.strip(" _")
        if not residual:
            return "", "", False, "", ""
        
        volume_info = ""
        range_info = ""
        is_completed = False
        side_story_parts = []  # 외전, 후기 등 여러 부가 정보 수집
        complex_found = False
        author_from_res = ""

        # [Fix] 잔여 문자열 끝에 있는 " - 저자명" 패턴 추출 (완결/화수 이후에 있는 경우만 저자명으로 간주)
        author_match = self.author_separator_pattern.search(residual)
        if author_match:
            potential_author = author_match.group(1).strip()
            if len(potential_author) < 20 and not re.search(r'\d{2,}', potential_author):
                author_from_res = potential_author
                residual = residual[:author_match.start()].strip()

        # [Special Case] Range + Comp + Volume + Range (e.g. "1-546 完 2부 212")
        # 처리가 복잡한 다중 파트/범위 패턴을 통째로 잡아내어 순서를 보존함
        # Regex: Range(1-546) + Comp(完) + Volume(2부) + Range(212 or 1-212)
        complex_match = re.search(r'^(\d+\s*[-~]\s*\d+)\s*(?:完|완|완결)\s*(\d+\s*부)\s*(\d+(?:\s*[-~]\s*\d+)?)', residual)
        if complex_match:
            part1_range = complex_match.group(1).replace(' ', '')
            part2_vol = complex_match.group(2).replace(' ', '')
            part2_range_raw = complex_match.group(3).replace(' ', '')
            
            # Part 2 Range Normalization (e.g. 212 -> 1-212)
            if '-' not in part2_range_raw and '~' not in part2_range_raw:
                part2_range = f"1-{part2_range_raw}"
            else:
                part2_range = part2_range_raw
                
            # Construct formatted string as 'range_info'
            # Format: 1-546 (완) 2부 1-212
            combined_info = f"{part1_range} (완) {part2_vol} {part2_range}"
            
            range_info = combined_info
            
            # 매칭된 부분 제거 (외전 등 추가 파싱을 위해 loop continue)
            residual = residual[complex_match.end():].strip()
            complex_found = True

        # [NEW] N 完 외전 N-M (Bug 7)
        # 예시: "1000 完 외전 1-98" -> range=1-1000, side=외전 1-98, complete=True
        m = re.search(r'^(\d{1,5})\s+(完|완|Complete)\s+(외전|外)\s+(\d{1,4})\s*[-~]\s*(\d{1,4})', residual, re.IGNORECASE)
        if m and not complex_found:
            range_info = f"1-{int(m.group(1))}"
            side_story_parts.append(f"외전 {int(m.group(4))}-{int(m.group(5))}")
            is_completed = True
            complex_found = True
            residual = residual[m.end():].strip()
            
        # [NEW] N 에필로그 N-M 完 (Bug 4)
        # 예시: "052 에필로그1-3 完" -> range=1-52, side=에필 1-3, complete=True
        m = re.search(r'^(\d{1,5})\s*(에필로그|에필)\s*(\d{1,4})\s*[-~]\s*(\d{1,4})\s*(完|완|Complete)\b', residual, re.IGNORECASE)
        if m and not complex_found:
            range_info = f"1-{int(m.group(1))}"
            side_story_parts.append(f"에필 {int(m.group(3))}-{int(m.group(4))}")
            is_completed = True
            complex_found = True
            residual = residual[m.end():].strip()

        # 0. "1-324본편" 같은 붙어있는 패턴 분리
        residual = re.sub(r'(\d+)(본편)', r'\1 \2', residual)
        
        # 1. "본편 및 외전" (+完/(완) 유무 무관) 패턴 처리 (완결 패턴보다 먼저!)
        match_bon = re.search(r'본편\s*및\s*외전(?:\s*[\(\[]?\s*(?:完|완(?:결)?)\s*[\)\]]?)?', residual)
        if match_bon:
            is_completed = True
            if "외전" not in side_story_parts:
                side_story_parts.append("외전")
            residual = residual[:match_bon.start()] + " " + residual[match_bon.end():]
        
        # 1.5 "완+외" / "完+外" / "完外" 패턴 처리 [NEW]
        elif re.search(r'(?:完|완)[\s,]*\+?[\s,]*(?:外|외(?:전|포)?)', residual):
            is_completed = True
            residual = re.sub(r'(?:完|완)[\s,]*\+?[\s,]*(?:外|외(?:전|포)?)(?!\S)?', ' 외전 ', residual)

        # 2. "본편 및 외전" 패턴 처리 (위에서 안 걸린 변형 대응)
        elif re.search(r'본편\s*및\s*외전', residual):
            is_completed = True
            if "외전" not in side_story_parts:
                side_story_parts.append("외전")
            residual = re.sub(r'본편\s*및\s*외전[,\s]*', '', residual)
        
        # 3. 완결 여부 확인 (위에서 처리 안 된 경우)
        # Bug 8: 完 뒤에 쉼표가 있을 때도 매칭되도록 "완결 마커" 추출 시 연재중/미완 여부만 체크하고 쉼표 무관하게
        # 근데 연재중/미완이 있으면 완결 취소
        # [Fix] 외전 N 연재중 같은 경우 본편은 완결이므로 연재중 플래그 무시
        is_ongoing = False
        if re.search(r'(?<!외전)\s*(?:연재\s*중|미완)(?!\s*외전)', residual) and not re.search(r'(?:외전|外)\s*(?:\d{1,4}(?:\s*[-~]\s*\d{1,4})?\s*)?(?:연재\s*중|미완)', residual):
            is_ongoing = True
            
        if not is_completed and self.completion_pattern.search(residual) and not is_ongoing:
            is_completed = True
        residual = self.completion_pattern.sub('', residual)
        
        # 연재중/미완 키워드 자체는 제거
        residual = re.sub(r'(?:연재\s*중|미완)', ' ', residual)
        
        # 4. "후기 포함" 패턴 처리
        if re.search(r'후기\s*포함', residual):
            if not is_ongoing:
                is_completed = True
            side_story_parts.append("후기")
            residual = re.sub(r'[,\s]*후기\s*포함', '', residual)
        
        # 5. 단독 "후기" 패턴 처리 (포함 없이 단독으로 있는 경우)
        elif re.search(r'\s+후기(?:\s|$)', residual):
            if not is_ongoing:
                is_completed = True
            if "후기" not in side_story_parts:
                side_story_parts.append("후기")
            residual = re.sub(r'\s+후기(?:\s|$)', ' ', residual)
        
        
        # [NEW] Pre-cleaning: Remove noise words like "및", "포함", "comp"
        # This allows separated components like "에필 및 외전" to be parsed as "에필 외전"
        residual = re.sub(r'(?:\s|^)및(?:\s|$)', ' ', residual)
        residual = re.sub(r'(?:포함|comp|only)(?:\s|$)', ' ', residual, flags=re.IGNORECASE)

        # 6. 단독 "외전" 패턴 처리 (+ 없이 단독으로 있는 경우) - 여러 개일 수 있으므로 while loop
        # 예: "1-294 完 외전 에필" → 외전, 에필 추출
        while True:
            standalone_side_match = self.standalone_side_pattern.search(residual)
            if not standalone_side_match:
                break
            
            side_text_raw = standalone_side_match.group(0).strip()
            # 정규화 (외전 1, 에필로그 등) - group(0) 전체를 넘겨서 처리
            # group(1)은 키워드만, group(0)은 뒤의 숫자까지 포함
            
            # 주의: group(1)만 쓰면 뒤의 숫자가 잘림. group(0) 전체를 써야 함.
            side_text = self._normalize_side_story(side_text_raw)
            
            if side_text and side_text not in side_story_parts:
                side_story_parts.append(side_text)
            
            # 매칭된 부분 제거 (다음 루프를 위해)
            residual = residual[:standalone_side_match.start()] + " " + residual[standalone_side_match.end():]
        
        # 7. 외전 정보 추출 (+ 패턴) - +로 연결된 외전
        while True:
            side_match = self.side_story_pattern.search(residual)
            if not side_match:
                break
            side_text = self._normalize_side_story(side_match.group(0))
            if side_text and side_text not in side_story_parts:
                side_story_parts.append(side_text)
            residual = residual[:side_match.start()] + " " + residual[side_match.end():]
        
        # 7.5 후기/에필 등 완결성 마커가 부가 정보에 포함되어 있으면 완결 확정
        if not is_completed and not is_ongoing:
            if any(k in part for part in side_story_parts for k in ['후기', '에필', '후일담']):
                is_completed = True
        
        # Standard Volume/Range Parsing (Skip if complex pattern was found)
        if not complex_found:
            # 8. 부 정보 추출 (1-2부, 1부 등)
            volume_match = re.search(r'(\d+)\s*[-~]\s*(\d+)\s*부|(\d+)\s*부', residual)
            if volume_match:
                if volume_match.group(1) and volume_match.group(2):
                    volume_info = f"{volume_match.group(1)}-{volume_match.group(2)}부"
                elif volume_match.group(3):
                    volume_info = f"{volume_match.group(3)}부"
                residual = residual[:volume_match.start()] + residual[volume_match.end():]
            
            # 9. 범위 정보 추출 (1-536, 1-536화 등)
            range_match = self.range_pattern.search(residual)
            if range_match:
                try:
                    start = str(int(range_match.group(1)))
                    end = str(int(range_match.group(2)))
                    range_info = f"{start}-{end}"
                except ValueError:
                    # Fallback in case of non-integer (unlikely due to regex \d)
                    range_info = f"{range_match.group(1)}-{range_match.group(2)}"

            else:
                # 단일 숫자 범위 (120, 126 등)
                single_match = re.search(r'(\d+)', residual)
                if single_match:
                    num = single_match.group(1)
                    # 2자리 이상 숫자만 범위로 인식
                    if len(num) >= 2:
                        range_info = f"1-{int(num)}"  # Bug 5: leading zero 제거

        
        # 10. 외전 정보 조합
        side_story = ", ".join(side_story_parts) if side_story_parts else ""
        
        return volume_info, range_info, is_completed, side_story, author_from_res
    
    def _normalize_side_story(self, side_text: str) -> str:
        """외전 정보 정규화"""
        side_text = re.sub(r'^\s*\+\s*', '', side_text)
        for pattern in ['番外', '번외편', '번외']:
            side_text = re.sub(pattern, '외전', side_text, flags=re.IGNORECASE)
        
        # [NEW] Handle specific abbreviations
        if '외포' in side_text: side_text = side_text.replace('외포', '외전')
        if '外' in side_text: side_text = side_text.replace('外', '외전')
        if '번외포함' in side_text: side_text = side_text.replace('번외포함', '번외')

        side_text = re.sub(r'에필로그', '에필', side_text, flags=re.IGNORECASE)
        return side_text.strip()
    
    def format_normalized_filename(self, parse_result: TitleParseResult, genre: str = "") -> str:
        """정규화된 파일명 생성"""
        return parse_result.to_normalized_filename(genre)
