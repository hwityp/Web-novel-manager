"""
==============================================================================
파일: core/utils/sino_korean_phonetics.py
역할 및 목적:
    한자어의 음운변화(두음법칙, 렬/열, 율/률, 不(부/불) 음운변화, 관용음, 활음조)
    및 중/일식 한자어의 한국식 독음 오기/혼용에 대한 표준 교정 및 변형 생성,
    음운 정규형(Canonical) 변환 엔진.
주요 기능:
    1. correct_sino_korean_orthography(text):
       - 한국어 어문 규정에 따른 두음법칙, 열/렬, 율/률, 不(부/불), 관용음 자동 교정
    2. get_phonetic_search_variants(text):
       - 검색(네이버, 구글, 플랫폼)용 음운 변형 쿼리 리스트 생성
    3. to_phonetic_canonical(text):
       - 제목 유사도 검증(TitleSimilarityChecker, fuzzy_match) 및 캐시 키 매칭을 위한
         단일 음운 정규형(Canonical Form) 변환
    4. is_phonetic_match(text1, text2):
       - 두 텍스트가 음운변화 차이만으로 일치하는지 판정
    5. phonetic_similarity(text1, text2):
       - 음운 정규형 기반 유사도와 원본 유사도의 최댓값 반환
==============================================================================
"""

import re
from functools import lru_cache
from typing import List, Tuple, Set, Optional, Dict

# 한글 자모 정의
CHOSUNG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
JUNGSUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
JONGSUNG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

# 모음 [j] 계열 및 'ㅣ' (두음법칙에서 'ㄹ' -> 'ㅇ', 'ㄴ' -> 'ㅇ'으로 변하는 모음)
J_VOWELS = {'ㅑ', 'ㅕ', 'ㅖ', 'ㅛ', 'ㅠ', 'ㅣ'}

# 그 외 모음 (두음법칙에서 'ㄹ' -> 'ㄴ'으로 변하는 모음)
OTHER_VOWELS = {'ㅏ', 'ㅐ', 'ㅓ', 'ㅔ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅡ', 'ㅢ'}


@lru_cache(maxsize=2048)
def decompose_hangul(char: str) -> Optional[Tuple[str, str, str]]:
    """완성형 한글 1글자를 (초성, 중성, 종성)으로 분해"""
    if not char or len(char) != 1:
        return None
    code = ord(char)
    if not (0xAC00 <= code <= 0xD7A3):
        return None
    offset = code - 0xAC00
    jong = offset % 28
    jung = (offset // 28) % 21
    cho = (offset // 28) // 21
    return CHOSUNG[cho], JUNGSUNG[jung], JONGSUNG[jong]


@lru_cache(maxsize=2048)
def compose_hangul(cho: str, jung: str, jong: str = '') -> str:
    """(초성, 중성, 종성)을 완성형 한글 1글자로 조합"""
    cho_idx = CHOSUNG.index(cho)
    jung_idx = JUNGSUNG.index(jung)
    jong_idx = JONGSUNG.index(jong) if jong in JONGSUNG else 0
    return chr(0xAC00 + (cho_idx * 21 + jung_idx) * 28 + jong_idx)


def is_hangul_syllable(char: str) -> bool:
    """완성형 한글 1글자인지 확인"""
    return bool(char and len(char) == 1 and (0xAC00 <= ord(char) <= 0xD7A3))


# ==============================================================================
# 1. 두음법칙 변환 코어
# ==============================================================================

def apply_initial_sound_rule(char: str) -> str:
    """
    단어 첫머리에 적용되는 두음법칙 변환
    - 'ㄹ' 초성:
        - [j], [i] 계열 모음 앞: 'ㄹ' -> 'ㅇ' (량->양, 려->여, 례->예, 료->요, 류->유, 리->이, 룡->용, 린->인, 림->임, 립->입, 련->연, 렬->열, 력->역, 령->영 등)
        - 그 외 모음 앞: 'ㄹ' -> 'ㄴ' (라->나, 락->낙, 란->난, 랄->날, 람->남, 랍->납, 래->내, 로->노, 록->녹, 론->논, 뢰->뇌, 루->누, 륵->늑, 름->늠, 릉->능 등)
    - 'ㄴ' 초성:
        - [j], [i] 계열 모음 앞: 'ㄴ' -> 'ㅇ' (녀->여, 년->연, 뇨->요, 뉴->유, 니->이, 닉->익, 념->염, 녕->영, 녜->예 등)
    """
    decomp = decompose_hangul(char)
    if not decomp:
        return char
    cho, jung, jong = decomp

    if cho == 'ㄹ':
        if jung in J_VOWELS:
            return compose_hangul('ㅇ', jung, jong)
        else:
            return compose_hangul('ㄴ', jung, jong)
    elif cho == 'ㄴ':
        if jung in J_VOWELS:
            return compose_hangul('ㅇ', jung, jong)

    return char


# ==============================================================================
# 2. 不 (부/불) 규칙 및 열/렬, 율/률 규칙
# ==============================================================================

# 不(부)로 발음되는 대표 한자어 어근 (불 -> 부 교정용: ㄷ, ㅈ 계열 한자어)
BU_SINO_ROOTS = {
    '동산', '정', '당', '실', '조리', '자유', '적절', '전승', '진', '도덕',
    '주의', '득이', '등호', '등', '재', '전', '체', '작용', '결', '합격'
}

# 不(불)로 발음되어야 하는 대표 한자어 어근 및 복합어 (부 -> 불 교정용)
BUL_SINO_PATTERNS = {
    '부멸': '불멸',
    '부사조': '불사조',
    '부사지체': '불사지체',
    '부사우': '불사우',
    '부패신화': '불패신화',
    '백전부패': '백전불패',
    '전승부패': '전승불패',
    '부굴의': '불굴의',
    '부공평': '불공평',
    '부안한': '불안한',
    '부안투로': '불안투로',
}

# 관용음 및 활음조 교정 사전
IDIOMATIC_CORRECTIONS = {
    '희노애락': '희로애락',
    '토노': '토로',       # '吐露'
    '승락': '승낙',       # '承諾'
    '응락': '응낙',       # '應諾'
    '허낙': '허락',       # '許諾'
    '라침반': '나침반',
    '말일락원': '말일낙원',
}

# 중/일 소설 특유의 대표 오기/직역 독음 교정 사전
SINO_COMMON_MISSPELLINGS = {
    # 龍 (용/룡)
    '룡왕': '용왕', '룡황': '용황', '룡제': '용제', '룡문': '용문', '룡기사': '용기사',
    '룡신': '용신', '룡마': '용마', '룡족': '용족', '룡혈': '용혈', '룡투': '용투',
    '청용': '청룡', '쌍용': '쌍룡', '마용': '마룡', '신용': '신룡', '독용': '독룡',
    '화용': '화룡', '흑용': '흑룡', '백용': '백룡', '황용': '황룡', '폭용': '폭룡',
    '뇌용': '뇌룡', '구용': '구룡',
    # 女 (여/녀)
    '녀제': '여제', '녀주': '여주', '녀협': '여협', '녀황': '여황', '녀신': '여신',
    '녀왕': '여왕', '녀배': '여배', '녀인': '여인', '녀자': '여자', '녀무': '여무',
    '마여': '마녀', '미여': '미녀', '악여': '악녀', '선여': '선녀', '성여': '성녀',
    '소녀주': '소여주', '신녀제': '신여제', '대녀주': '대여주',
    # 柳 (유/류)
    '류씨': '유씨', '류성': '유성',
    # 年 (년/연)
    '년대문': '연대문', '년대물': '연대물', '년대고정': '연대고정', '청연': '청년', '소연': '소년',
    # 冷 (냉/랭)
    '랭정': '냉정', '랭혹': '냉혹', '랭담': '냉담', '랭혈': '냉혈', '랭각': '냉각', '랭면': '냉면',
    # 來 (내/래)
    '래일': '내일', '래년': '내년', '래객': '내객', '래세': '내세', '래방': '내방',
    '미내': '미래', '왕내': '왕래', '도내': '도래', '유내': '유래',
    # 樂 (낙/락)
    '락원': '낙원', '락도': '낙도', '극낙': '극락', '쾌낙': '쾌락', '안낙': '안락',
    # 羅 (나/라)
    '라한': '나한', '라열': '나열', '라마': '나마',
    '수나': '수라', '아수나': '아수라', '신나': '신라',
    # 陸 (육/륙)
    '륙지': '육지', '륙군': '육군', '륙로': '육로',
    '대육': '대륙', '상육': '상륙', '착육': '착륙',
    # 輪 (윤/륜)
    '륜회': '윤회', '환윤': '환륜', '삼윤': '삼륜',
    # 泥 (이/니)
    '니탄': '이탄',
    # 離 (이/리)
    '리혼': '이혼', '리유': '이유', '리과': '이과',
    # 靈 (영/령)
    '령도': '영도', '령원구': '영원구', '령능자': '영능자',
    # 禮 (예/례)
    '례절': '예절', '례의': '예의',
    # 糧/良 (양/량)
    '량심': '양심', '량호': '양호', '략탈': '약탈',
    # 旅/麗 (여/려)
    '려행': '여행', '려관': '여관', '려객': '여객',
    '고여': '고려', '화여': '화려',
    # 料 (요/료)
    '료금': '요금', '료법': '요법',
    # 勞/老/路 (노/로)
    '로인': '노인', '로선': '노선', '로동': '노동', '로후': '노후',
    # 錄 (녹/록)
    '록음': '녹음', '록색': '녹색',
    # 論 (논/론)
    '론리': '논리', '론쟁': '논쟁',
    # 雷 (뇌/뢰)
    '뢰우': '뇌우', '뢰성': '뇌성',
    # 樓 (누/루)
    '루각': '누각', '루선': '누선',
}

# 한글 맞춤법 두음법칙 안전 적용 어두 접두사 (외래어 침범 없는 확실한 한자어 어근)
SINO_INITIAL_PREFIXES = {
    '룡': '용',  # 룡왕, 룡제 등 외래어 전무
}


@lru_cache(maxsize=4096)
def correct_sino_korean_orthography(text: str) -> str:
    """
    한자어의 음운변화 및 한국식 독음 오기를 한국어 표준 맞춤법에 맞게 교정.
    
    1. 관용음 및 활음조 교정 (희노애락 -> 희로애락 등)
    2. 중/일 소설 특유의 대표 오기 어휘 교정 (룡왕 -> 용왕, 녀제 -> 여제, 대육 -> 대륙 등)
    3. 어두 두음법칙 안전 적용 (룡 -> 용 등 외래어 오인 없는 순수 한자어)
    4. 열/렬, 율/률 규칙 교정 (모음/ㄴ 뒤 렬->열, 율->율 / 기타 받침 뒤 열->렬, 율->률)
    5. 不(부/불) 음운 규칙 교정 (ㄷ, ㅈ 앞 불->부 / 멸, 사, 패, 굴 등 앞 부->불)
    """
    if not text:
        return text

    result = text

    # 1. 관용음 및 활음조 교정
    for err, corr in IDIOMATIC_CORRECTIONS.items():
        if err in result:
            result = result.replace(err, corr)

    # 2. 중/일 대표 오기 어휘 교정
    for err, corr in SINO_COMMON_MISSPELLINGS.items():
        if err in result:
            result = result.replace(err, corr)

    # 3. 어두 두음법칙 안전 접두사 교정 ('룡'으로 시작하는 어절은 100% 龍)
    words = re.split(r'(\s+|[^\w가-힣])', result)
    new_words = []
    for w in words:
        if w and w[0] in SINO_INITIAL_PREFIXES:
            w = SINO_INITIAL_PREFIXES[w[0]] + w[1:]
        new_words.append(w)
    result = ''.join(new_words)

    # 4. 열/렬, 율/률 음운 규칙 정밀 교정
    # 모음 또는 'ㄴ' 받침 뒤: '열', '율' (나열, 분열, 치열, 파열, 비율, 백분율, 선율, 전율)
    # 기타 받침 뒤: '렬', '률' (행렬, 결렬, 맹렬, 격렬, 법률, 능률, 확률)
    chars = list(result)
    for i in range(1, len(chars)):
        prev_c = chars[i - 1]
        curr_c = chars[i]

        prev_decomp = decompose_hangul(prev_c)
        curr_decomp = decompose_hangul(curr_c)

        if not prev_decomp or not curr_decomp:
            continue

        prev_jong = prev_decomp[2]
        is_vowel_or_nieun = (prev_jong == '' or prev_jong == 'ㄴ')

        # '렬' / '열' 체크
        if curr_c == '렬' and is_vowel_or_nieun:
            chars[i] = '열'
        elif curr_c == '열' and not is_vowel_or_nieun:
            chars[i] = '렬'

        # '률' / '율' 체크
        elif curr_c == '률' and is_vowel_or_nieun:
            chars[i] = '율'
        elif curr_c == '율' and not is_vowel_or_nieun:
            chars[i] = '률'

    result = ''.join(chars)

    # 5. 不(부/불) 규칙 교정
    # 5-1. 사전 정의된 부 -> 불 패턴 치환
    for err, corr in BUL_SINO_PATTERNS.items():
        if err in result:
            result = result.replace(err, corr)

    # 5-2. 불 + [ㄷ, ㅈ 한자어 어근] -> 부 + [어근] (순우리말 '불닭', '불장난' 등 보존)
    for root in BU_SINO_ROOTS:
        target = '불' + root
        if target in result:
            result = result.replace(target, '부' + root)

    return result


# ==============================================================================
# 3. 검색(Naver, Google, 플랫폼)용 음운 변형 쿼리 생성기
# ==============================================================================

def get_phonetic_search_variants(title: str) -> List[str]:
    """
    주어진 제목에 대해 가능한 모든 한자어 음운 변형(두음법칙, 렬/열, 율/률, 부/불, 관용음)
    검색어 리스트를 생성.
    
    예:
    - "룡왕전설" -> ["룡왕전설", "용왕전설"]
    - "용왕전설" -> ["용왕전설", "룡왕전설"]
    - "녀제강림" -> ["녀제강림", "여제강림"]
    - "불동산투자" -> ["불동산투자", "부동산투자"]
    - "나열" -> ["나열", "나렬"]
    - "행렬" -> ["행렬", "행열"]
    - "락원" -> ["락원", "낙원"]
    - "희로애락" -> ["희로애락", "희노애락"]
    """
    if not title:
        return []

    variants: List[str] = [title]
    corrected = correct_sino_korean_orthography(title)
    if corrected != title and corrected not in variants:
        variants.append(corrected)

    # 역방향 변형 (표준어 -> 두음법칙 미적용 형태)
    # 1. 어두 '용' <-> '룡', '유' <-> '류', '여' <-> '녀', '연' <-> '년', '내' <-> '래', '낙' <-> '락', '노' <-> '로', '나' <-> '라'
    rev_mapping = {
        '용': '룡', '유': '류', '여': '녀', '연': '년', '내': '래',
        '낙': '락', '노': '로', '나': '라', '육': '륙', '윤': '륜',
        '이': '리', '예': '례', '양': '량', '역': '력', '영': '령',
    }

    # 단어 첫머리 글자 치환 변형
    words = title.split(' ')
    for i, w in enumerate(words):
        if not w:
            continue
        c0 = w[0]
        # 표준 -> 비표준
        if c0 in rev_mapping:
            cand = rev_mapping[c0] + w[1:]
            new_words = list(words)
            new_words[i] = cand
            cand_title = ' '.join(new_words)
            if cand_title not in variants:
                variants.append(cand_title)
        # 비표준 -> 표준
        c0_std = apply_initial_sound_rule(c0)
        if c0_std != c0:
            cand = c0_std + w[1:]
            new_words = list(words)
            new_words[i] = cand
            cand_title = ' '.join(new_words)
            if cand_title not in variants:
                variants.append(cand_title)

    # 열 <-> 렬, 율 <-> 률 치환 변형
    if '열' in title:
        v = title.replace('열', '렬')
        if v not in variants:
            variants.append(v)
    if '렬' in title:
        v = title.replace('렬', '열')
        if v not in variants:
            variants.append(v)
    if '율' in title:
        v = title.replace('율', '률')
        if v not in variants:
            variants.append(v)
    if '률' in title:
        v = title.replace('률', '율')
        if v not in variants:
            variants.append(v)

    # 不 부 <-> 불 치환 변형
    if '부' in title:
        v = title.replace('부', '불')
        if v not in variants:
            variants.append(v)
    if '불' in title:
        v = title.replace('불', '부')
        if v not in variants:
            variants.append(v)

    # 수라 <-> 수나, 나한 <-> 라한
    if '수라' in title:
        v = title.replace('수라', '수나')
        if v not in variants:
            variants.append(v)
    if '수나' in title:
        v = title.replace('수나', '수라')
        if v not in variants:
            variants.append(v)
    if '나한' in title:
        v = title.replace('나한', '라한')
        if v not in variants:
            variants.append(v)
    if '라한' in title:
        v = title.replace('라한', '나한')
        if v not in variants:
            variants.append(v)

    # 활음조 역변형
    if '희로애락' in title:
        v = title.replace('희로애락', '희노애락')
        if v not in variants:
            variants.append(v)

    return variants


# ==============================================================================
# 4. 음운 정규형(Canonical Form) 변환 (유사도 검증 및 캐시 매칭용)
# ==============================================================================

@lru_cache(maxsize=4096)
def to_phonetic_canonical(text: str, keep_spaces: bool = True) -> str:
    """
    모든 한자어 음운변화 대립쌍(두음법칙, 렬/열, 율/률, 부/불, 관용음)을
    단 하나의 표준 정규형(Canonical Representation)으로 축약 변환.
    
    특징:
    - to_phonetic_canonical("룡왕전설") == to_phonetic_canonical("용왕전설")
    - to_phonetic_canonical("녀제강림") == to_phonetic_canonical("여제강림")
    - to_phonetic_canonical("나렬") == to_phonetic_canonical("나열")
    - to_phonetic_canonical("행열") == to_phonetic_canonical("행렬")
    - to_phonetic_canonical("불동산") == to_phonetic_canonical("부동산")
    - to_phonetic_canonical("희노애락") == to_phonetic_canonical("희로애락")
    - to_phonetic_canonical("수나") == to_phonetic_canonical("수라")
    """
    if not text:
        return ""

    # 1. 기본 맞춤법 정규화 선행
    norm = correct_sino_korean_orthography(text)

    # 2. 공백 및 특수문자 처리, 소문자화
    if keep_spaces:
        norm = re.sub(r'[^\w가-힣\s]', ' ', norm).lower()
        norm = re.sub(r'\s+', ' ', norm).strip()
    else:
        norm = re.sub(r'[^\w가-힣]', '', norm).lower()

    # 3. 대립쌍을 단일 표준형으로 통일
    chars = list(norm)
    for i, c in enumerate(chars):
        if c == ' ':
            continue
        decomp = decompose_hangul(c)
        if decomp:
            cho, jung, jong = decomp
            # 룡/용 -> 용
            if cho == 'ㄹ' and jung in J_VOWELS:
                chars[i] = compose_hangul('ㅇ', jung, jong)
            elif cho == 'ㄹ' and jung not in J_VOWELS:
                chars[i] = compose_hangul('ㄴ', jung, jong)
            elif cho == 'ㄴ' and jung in J_VOWELS:
                chars[i] = compose_hangul('ㅇ', jung, jong)

    canon = ''.join(chars)

    # 열/렬, 율/률 단일화
    canon = canon.replace('렬', '열').replace('률', '율')

    # 不(부/불) 단일화 (ㄷ, ㅈ 또는 특정 한자어 앞)
    canon = canon.replace('불동', '부동').replace('불정', '부정').replace('불당', '부당').replace('불실', '부실').replace('불조', '부조')
    canon = canon.replace('부멸', '불멸').replace('부사', '불사').replace('부패', '불패').replace('부굴', '불굴')

    # 수나 -> 수라
    canon = canon.replace('수나', '수라')
    canon = canon.replace('라한', '나한')

    return canon


def is_phonetic_match(text1: str, text2: str) -> bool:
    """두 텍스트가 한자어 음운변화 차이만으로 서로 일치하는지 판정"""
    if not text1 or not text2:
        return False
    if text1 == text2:
        return True
    return to_phonetic_canonical(text1, keep_spaces=False) == to_phonetic_canonical(text2, keep_spaces=False)


def phonetic_similarity(text1: str, text2: str) -> float:
    """
    음운 정규형(Canonical) 기반 유사도 계산 (difflib SequenceMatcher 기반)
    두 제목이 음운변화 차이만 있는 경우 1.0 반환.
    """
    if not text1 or not text2:
        return 0.0
    if text1 == text2:
        return 1.0

    c1 = to_phonetic_canonical(text1, keep_spaces=False)
    c2 = to_phonetic_canonical(text2, keep_spaces=False)
    if c1 == c2:
        return 1.0

    from difflib import SequenceMatcher
    return SequenceMatcher(None, c1, c2).ratio()
