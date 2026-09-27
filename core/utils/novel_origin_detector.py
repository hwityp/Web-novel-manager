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

    # 2. 국가별 특정 출처/플랫폼/고유 장르 태그
    CN_SOURCE_TAGS = re.compile(
        r'(?:\[|\()(?:언정|선협|사합원|4합원|치뎬|치디엔|진장|진장문학|qidian|jjwxc|faloo|비로|비로소설|중소설|중국소설|중웹소)(?:\]|\))',
        re.IGNORECASE
    )
    JP_SOURCE_TAGS = re.compile(
        r'(?:\[|\()(?:나로우|소설가가\s*되자|카쿠요무|하멜른|hameln|syosetu|kakuyomu|일소설|일본소설|일웹소|라노벨)(?:\]|\))',
        re.IGNORECASE
    )
    KR_SOURCE_TAGS = re.compile(
        r'(?:\[|\()(?:문피아|시리즈|네이버시리즈|리디|리디북스|노벨피아|조아라|카카오|카카오페이지|소설넷)(?:\]|\))',
        re.IGNORECASE
    )

    # 3. 일본어 가나 정규식 (히라가나, 카타카나)
    JAPANESE_KANA_REGEX = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')

    # 3-1. 일본어 고유 신자체(新字体, JIS) 한자 정규식
    JAPANESE_SHINJITAI_REGEX = re.compile(
        r'[\u8ee2\u6c17\u5b66\u4f53\u56fd\u7adc\u5e83\u5b9f\u9244\u6e0b\u6e05\u52b1\u4e88\u4f59\u6075\u6765\u60aa'
        r'\u4e0e\u4e89\u4ecf\u5150\u5186\u5263\u53d8\u56f3\u58f0\u58f2\u5909\u5b9f\u6075\u6170\u6226\u629e\u636e'
        r'\u654e\u65ad\u65f6\u685c\u697d\u6b69\u6b74\u6c17\u6ca2\u6d5c\u6f54\u70b9\u72ec\u756a\u767a\u76d7\u771e'
        r'\u793c\u795e\u796fc\u79d8\u79c1\u7a42\u7b87\u7c8b\u7d75\u7d99\u7dd2\u7f72\u8056\u80a9\u8133\u8107\u82b8'
        r'\u8584\u866b\u8853\u8863\u898b\u89c8\u8a00\u8a33\u8a3c\u8b5c\u8b66\u9055\u9162\u91d1\u9280\u92ed\u96a0'
        r'\u970a\u9858\u99c1\u9a0e\u9a19\u9ed2]'
    )

    # 4. 한자 정규식 (CJK 통합 한자)
    CHINESE_CHAR_REGEX = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

    # 4-1. 중국어 고유 전각 문장부호 정규식 (전각 쉼표: '，', 전각 콜론: '：', 모점: '、')
    CHINESE_PUNCTUATION_REGEX = re.compile(r'[\uFF0C\uFF1A\u3001]')

    # 4-2. 중국어 한자음 문법 어소 (무공백 한자 독음 제목에서 흔히 나타나는 한자음)
    CN_PHONETIC_GRAMMAR_REGEX = re.compile(
        r'(?:리적|후적|지력|료마|시수|불사우|관선료|풍료|붕료|매방료|흔난|타적|나저|회리적|니설|저시|척능|'
        r'적맹왕|아적|이적|아시|아취시|이취시|천성|천서|천서후|포회|별야|불안투로|척패|가급|가유|개착|외괘|'
        r'흘육|아태상|아피박|아합법|아성위|아진몰상|이신몰상|개국|종.+?개시|개시|인재|시가사|쾌천지|두라지|항종지|'
        r'성료|함어료|별태리보|국사대인|선자|아재|아진적|아능|아도시|나사년|종편|포부|니문|수책|오월령|'
        r'적장부|적신도|단목후|파경후|천월|생활계|속성점|적아|불시|옹유|요도|전민|전직|자소도주|일품용화|'
        r'표고양|금욕불자|앵앵괴|소조종|화오|국술|대종사|도과|항도|항종|권유|괴렵|위새리사|삼두룡|통고금|'
        r'초시|포화호선|출룡|희신|희랍대악인|허니만장|금점층|호림원|호림|초가전|령원구|학신전|회당|'
        r'극도무성|용상반약공|횡추|화의금화|첩영|명령여징복|연대문|여배|각성후|쾌천)'
    )

    # 4-3. 일본어 한자음 문법 어소
    JP_PHONETIC_GRAMMAR_REGEX = re.compile(
        r'(?:지인|적거인|전생|방랑담|수기녹|귀멸|진격|은혼|주술회전)'
    )

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
        "훈련가": "중국식 포켓몬 트레이너(训练家)",
        "영천": "영약 샘물(영천/空间灵泉)",
        "흘육": "고기 먹기(흘육/吃肉)",
        "개시": "시작/개시(종양식대호개시 등)",
        "래료": "도착/왔다(래료/来了)",
        "년초": "연초/초기(칠십년대초 등)",
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
        # 직역투 및 시스템/치트
        "적맹왕": "중국어 조사 '~적(的)' 직역",
        "~세계적": "중국어 조사 '~적(的)' 직역",
        "적인생": "중국어 조사 '~적인생(~的人生)' 직역",
        "아적": "중국어 1인칭 소유격 '아적(我的)'",
        "아시": "중국어 서술어 '아시(我是)'",
        "대착": "중국어 동사 '대착(带着)'",
        "재래": "중국어 '재래(才来/再来/又来)'",
        "재유": "중국어 '재유(才有)'",
        "개국": "초반 전개(개국/开局)",
        "开局": "초반 전개(开局)",
        "계통": "시스템(계통/系统)",
        "系统": "시스템(系统)",
        "系統": "시스템(系統)",
        "모의기": "인생 시뮬레이터(모의기/模拟器)",
        "模拟器": "시뮬레이터(模拟器)",
        # 추가 음독/빙의/소설 클리셰
        "아취시": "중국어 '아취시(我就是)'",
        "천성": "빙의 직역 '천성(穿成)'",
        "천서": "책빙의 직역 '천서(穿书)'",
        "천서후": "책빙의 후 직역 '천서후(穿书后)'",
        "포회": "엑스트라 직역 '포회(炮灰)'",
        "대도황": "피난/도황 직역 '대도황(大逃荒)'",
        "도황": "피난 직역 '도황(逃荒)'",
        "별야": "중국어 '별야(别惹)'",
        "불안투로": "중국어 '불안투로(不按套路)'",
        "척패": "중국어 '척패(出牌)'",
        "가급": "시집가다 직역 '가급(嫁给)'",
        "가유": "집에 ~가 있다 '가유(家有)'",
        "개착": "켜고 직역 '개착(开着)'",
        "외괘": "치트 직역 '외괘(外挂)'",
        "흘육": "고기를 먹다 직역 '흘육(吃肉)'",
        "대이자": "처형 직역 '대이자(大姨子)'",
        "미혼처": "약혼녀 직역 '미혼처(未婚妻)'",
        "목엽": "나뭇잎마을 직역 '목엽(木叶)'",
        "화영": "나루토 직역 '화영(火影)'",
        "소해도": "작은 섬 직역 '소해도(小海岛)'",
        "표한": "사납다 직역 '표한(彪悍)'",
        "심첨총": "애지중지 총애 '심첨총(心尖宠)'",
        "소농녀": "어린 시골처녀 '소농녀(小农女)'",
        "강성선신": "선신 강림(강성선신)",
        "자손구아": "자손들이 내게 청하다(자손구아)",
        "인생시뮬": "인생 시뮬레이터",
        "출석체크": "시스템 싸인(签到)",
        "签到": "시스템 싸인(签到)",
        "사인": "시스템 싸인/출석(사인/签到)",
        "역습계통": "역습 시스템(逆袭系统)",
        "逆袭系统": "역습 시스템(逆袭系统)",
        "골드핑거": "치트(골드핑거/金手指)",
        "金手指": "치트(金手指)",
        "대승기": "선협 경지(대승기/大乘期)",
        "大乘期": "선협 경지(大乘期)",
        "두라": "투라대륙 패러디(두라/斗罗)",
        "斗罗": "투라대륙 패러디(斗罗)",
        "두라지": "투라대륙 패러디(斗罗之)",
        "려포": "여포 음독(려포/吕布)",
        "이석": "중국어 지시대명사 '이석/저개(这个)' 음독",
        "이신몰상": "중국어 클리셰 '아진몰상(我真没想)' 음독",
        "아진몰상": "중국어 클리셰 '아진몰상(我真没想)' 직역",
        "이적": "중국어 1인칭 소유격 '아적(我的)' 음독",
        "이취시": "중국어 '이취시(这就是)' 음독",
        "아태상": "중국어 '아태상(我太想)' 음독",
        "아피박": "중국어 '아피박(我被迫)' 음독",
        "아합법": "중국어 '아합법(我合法)' 음독",
        "악자": "중국어 '처자/아내(妻子)' 음독",
        "말세": "중국 아포칼립스 장르 '말세(末世)'",
        "생존유희": "중국 서바이벌 장르 '생존유희(生存游戏)'",
        "구도": "중국 선협 존버/은둔 '구도(苟到)'",
        "세모": "중국 판타지 악마 '세모(恶魔)' 음독",
        "난세서": "중국 선협/무협 명작 소설 '난세서(乱世书)'",
        "장공주": "황실 장공주(长公主)",
        "모반": "모반을 꾀하다(造反)",
        "조반": "조반(造反)",
        "황숙": "황숙(皇叔)",
        "교낭": "미인 교낭(娇娘)",
        "미색무쌍": "절세미색(美色无双)",
        "복녀": "복덩이 딸(福女)",
        "총후": "총애받는 황후(宠后)",
        "서녀": "서녀(庶女)",
        "적녀": "적녀(嫡女)",
        "서적녀": "서적녀(庶嫡女)",
        "침춘환": "침춘환(沈春欢)",
        "쾌천": "무한 전이(쾌천/快穿)",
        "후궁직장": "후궁 직장물(后宫职场)",
        "승직기": "승진기(升职记)",
        "성료": "~이 되었다(成了)",
        "함어료": "드러누웠다(咸鱼了)",
        "별태리보": "너무 터무니없다(别太离谱)",
        "국사대인": "국사 어른(国师大人)",
        "보위": "지키다(保卫)",
        "망절": "망절(忘节)",
        "곽격옥자": "호그와트(곽격옥자/霍格沃茨)",
        "적자연마법": "자연마법(~的自然魔法)",
        "기묘모험": "기묘한 모험(奇妙冒险)",
        "선자": "선자(仙子)",
        "아재": "내가 ~에서(我在)",
        "아진적": "나는 정말(我真的)",
        "아능": "나는 할 수 있다(我能)",
        "아도시": "나는 모두(我都是)",
        "나사년": "그 시절(那些年)",
        "종편": "~에서부터(从...)",
        "포부": "폭부(暴富, 벼락부자)",
        "니문": "너희들(你们)",
        "수책": "수첩/지침(手册)",
        "오월령": "오월령(五月令/五零)",
        "적장부": "나의 남편(~的丈夫)",
        "적신도": "나의 신도(~的信徒)",
        "비로": "비로소설(飞卢)",
        "단목후": "단막을 본 후(弹幕后)",
        "파경후": "거울이 깨진 후(破镜后)",
        "공간물자": "공간 아이템 직역 '공간물자(空间物资)'",
        "공간 물자": "공간 아이템 직역 '공간물자(空间物资)'",
        "천월": "차원이동/빙의 직역 '천월(穿越)'",
        "70년대": "중국 시대극 70년대(七零年代)",
        "80년대": "중국 시대극 80년대(八零年代)",
        "칠령": "중국 70년대(七零)",
        "팔령": "중국 80년대(八零)",
        "육령": "중국 60년대(六零)",
        "구령": "중국 90년대(九零)",
        "인재동경": "도쿄에 있는 나(人在东京)",
        "인재탄서": "삼체/탄서에 있는 나(人在吞噬)",
        "인재": "중국 웹소설 클리셰 '인재~(人在~)'",
        "생활계": "생활계 직역(生活系)",
        "일근육": "하나의 근육(一肌肉)",
        "속성점": "속성 포인트(属性点)",
        "적아": "나의 ~ 직역(的我)",
        "불시": "~가 아니다 직역(不是)",
        "옹유": "가지다 직역(拥有)",
        "요마": "요마(妖魔)",
        "장생요도": "장생요도(长生妖道)",
        "요도": "요괴 도사 직역(妖道)",
        "전민령주": "전민 영주물(全民领主)",
        "전민진화": "전민 진화물(全民进化)",
        "전민": "전민/전 인류(全民)",
        "전직법사": "전직법사(全职法师)",
        "자소도주": "자소도주(紫霄道主)",
        "도주": "도주(道主)",
        "일품용화": "일품용화(一品荣华)",
        "용화": "부귀영화 직역(荣华)",
        "장안호": "장안의 호걸(长安豪)",
        "장안": "장안(长安)",
        "만명": "명나라 말기(晚明)",
        "저정류": "톱스타(顶流)",
        "종예": "예능(综艺)",
        "제일교": "중국 언정(第一娇/第一侯)",
        "주명승도": "중국 선협(铸明升道)",
        "시가사": "중국어 구어체 음독 '시가사(是个啥)'",
        "초능력시가사": "중국어 번역투 '초능력시가사(超能力是个啥)'",
        # 어미 및 조사 음독
        "리적": "중국어 '~리적(里的: ~안의)' 음독",
        "후적": "중국어 '~후적(后的: ~후의)' 음독",
        "지력": "중국어 '~지력(之力: ~의 힘)' 음독",
        "료마": "중국어 의문조사 '~료마(了吗)' 음독",
        "시수": "중국어 '~시수(是谁: 누구인가)' 음독",
        "불사우": "중국어 '~불사우(不死于: ~로 죽지 않는다)' 음독",
        "관선료": "중국어 '관선료(官宣了: 공식 발표했다)' 음독",
        "풍료": "중국어 '풍료(疯了: 미쳤다)' 음독",
        "붕료": "중국어 '붕료(崩了: 붕괴했다)' 음독",
        "매방료": "중국어 '매방료(买房了: 집을 샀다)' 음독",
        "흔난": "중국어 '흔난(很难: 매우 어렵다)' 음독",
        "타적": "중국어 3인칭 소유격 '타적(他的: 그의)' 음독",
        "나저": "중국어 '나저(那这: 그렇다면 이것은)' 음독",
        "회리적": "중국어 '회리적(怀里的: 품 속의)' 음독",
        "니설": "중국어 '니설(你说: 네가 말하기를)' 음독",
        "저시": "중국어 '저시(这是: 이것이)' 음독",
        "척능": "중국어 '척능(只能: 오직 ~할 수밖에)' 음독",
        # 중국 고유 클리셰 및 어휘 음독
        "표고양": "중국 고대 언정 외사촌 아가씨(表姑娘)",
        "금욕불자": "중국 로맨스 언정 금욕불자(禁欲佛子)",
        "앵앵괴": "중국 인터넷 유행어 애교쟁이(嘤嘤怪)",
        "소조종": "중국 언정 상전/조상님(小祖宗)",
        "화오": "중국 연예계(华娱) 또는 피겨(花滑)",
        "국술": "중국 전통 권술(国术)",
        "대종사": "대종사(大宗师)",
        "도과": "선협 도의 결실(道果)",
        "항도": "홍콩 섬(港岛)",
        "항종": "홍콩 영화 종합 유니버스(港综)",
        "권유": "왕좌의 게임 중국어 약칭(权游)",
        "괴렵": "몬스터 헌터 중국어 약칭(怪猎)",
        "위새리사": "비세리스 음독(韦赛里斯)",
        "삼두룡": "타르가르옌 삼두룡(三头龙)",
        "통고금": "고금을 통하다(通古今)",
        "초시": "슈퍼마켓(超市)",
        "포화호선": "포화호선(炮火弧线)",
        "출룡": "대체역사 출룡(黜龙)",
        "구일음락가": "크툴루 옛지배자 음악가(旧日音乐家)",
        "구호반": "축구 9.5번 공격수(九号半)",
        "영능자": "사이커/초능력자(灵能者)",
        "희신": "경극의 신(戏神)",
        "희랍대악인": "그리스 신화 대악인(希腊带恶人)",
        "허니만장": "허니만장광망호(许你万丈光芒好)",
        "금점층": "골든 셰이디드 고양이(金渐层)",
        "호림원": "산림 레인저(护林员)",
        "호림": "산림 보호(护林)",
        "초가전": "가챠 뽑기 전(抽卡前)",
        "령원구": "털이/약탈(零元购)",
        "학신전": "학문의 신의 전당(学神殿)",
        "회당": "되돌아가다(回档)",
        "극도무성": "극도 무성(极道武圣)",
        "용상반약공": "김용 무협 용상반약공(龙象般若功)",
        "횡추": "거침없이 밀어붙이다(横推)",
        "화의금화": "남북조 역사극 화의금화(华衣锦华)",
        "첩영": "스파이/첩보(谍影)",
        "명령여징복": "커맨드 앤 컨커(命令与征服)",
    }

    # 6. 일본 소설 고유 클리셰 및 어휘 패턴
    JP_TRAIT_KEYWORDS: Dict[str, str] = {
        "악역영애": "여성향 악역영애(悪役令嬢)",
        "悪役令嬢": "여성향 악역영애(悪役令嬢)",
        "약혼파기": "약혼 파기(婚約破棄)",
        "婚約破棄": "약혼 파기(婚約破棄)",
        "단죄": "단죄 이벤트(断罪)",
        "断죄": "단죄 이벤트(断罪)",
        "익애": "무조건적 사랑(익애/溺愛)",
        "溺愛": "무조건적 사랑(溺愛)",
        "추방물": "파티 추방물(追放)",
        "追放": "파티 추방물(追放)",
        "슬로우라이프": "이세계 슬로우라이프",
        "슬로우 라이프": "이세계 슬로우라이프",
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
        "오토메": "여성향 게임(오토메/乙女)",
        "을녀": "여성향 게임(을녀/乙女)",
        "코노스바": "코노스바 패러디",
        "대마녀": "일본 라이트노벨 대마녀",
        "마법연구": "일본 라이트노벨 마법연구",
        "마법사 왕으로": "일본 웹소설 문장형 제목 (~から~へ)",
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
        "발롱도르": "한국 스포츠물(발롱도르)",
        "스트라이커": "한국 스포츠물(스트라이커)",
        "프로축구": "한국 스포츠물(프로축구)",
        "대치동": "한국 학원/전문직(대치동)",
        "항마신장": "한국 무협(항마신장)",
        "소호객잔": "한국 무협(소호객잔)",
        "대한민국": "한국 배경",
        "서울": "한국 수도 배경",
        "조선": "한국 역사 배경",
        "고려": "한국 역사 배경",
        "신무협": "한국 창작 신무협",
        "판도충": "한국 대체역사 밈/용어",
        "만반도": "한국 대체역사 밈/용어",
        "타입문": "서브컬처 타입문(TYPE-MOON)",
        "커쉐": "명탐정 코난 커쉐(柯学)",
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
            reasons.append("중국 플랫폼/고유 장르 태그 감지 (언정/선협/사합원/치뎬 등)")

        if cls.JP_SOURCE_TAGS.search(full_text):
            jp_score += 100
            reasons.append("일본 플랫폼/출처 태그 감지 (나로우/카쿠요무/하멜른/라노벨 등)")

        if cls.KR_SOURCE_TAGS.search(full_text):
            kr_score += 100
            reasons.append("한국 플랫폼/출처 태그 감지 (리디/문피아/시리즈/노벨피아 등)")

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
            elif cls.JAPANESE_SHINJITAI_REGEX.search(cjk_source):
                jp_score += 75
                reasons.append(f"원문 제목에 일본어 신자체(新字体) 한자 포함: '{cjk_source}'")
            elif cls.CHINESE_CHAR_REGEX.search(cjk_source):
                # 한국 소설의 한자 표기 병기 검사:
                # 번역 태그/중국 전각 기호가 없고, 외래 클리셰가 없으며,
                # 한글 제목 글자 수와 괄호 한자 글자 수가 동일한 경우 (예: 비뢰도 == 飛雷刀, 군림천하 == 君臨天下, 묵향 == 墨香)
                clean_korean = re.sub(r'[^가-힣]', '', title or raw_name)
                clean_cjk = re.sub(r'[^\u4e00-\u9fff]', '', cjk_source)
                has_cn_punct = bool(cls.CHINESE_PUNCTUATION_REGEX.search(full_text))
                has_trans_tag = bool(cls.TRANSLATION_TAGS.search(full_text))
                is_foreign_trope = any(kw in clean_korean for kw in ['악역영애', '사합원', '선협', '언정', '지청', '수선', '이세계', '전생', '오토메', '포회', '천월', '중생'])

                if not has_trans_tag and not has_cn_punct and not is_foreign_trope and clean_korean and clean_cjk and len(clean_korean) == len(clean_cjk):
                    kr_score += 65
                    reasons.append(f"한국 소설의 한자 표기 병기 감지 ({clean_korean} == {clean_cjk})")
                elif any(kw in full_text for kw in ['전생', '이세계', '오토메', '라노벨', '영애']):
                    jp_score += 75
                    reasons.append(f"원문 한자 표기 및 일본 소설 클리셰 동반: '{cjk_source}'")
                else:
                    cn_score += 70
                    reasons.append(f"원문 제목에 한자(CJK) 표기 포함: '{cjk_source}'")

        # -------------------------------------------------------------
        # 2-1. 중국어 고유 전각 문장부호 감지 (전각 쉼표: '，', 전각 콜론: '：', 모점: '、')
        # -------------------------------------------------------------
        if cls.CHINESE_PUNCTUATION_REGEX.search(full_text):
            cn_score += 50
            reasons.append("중국어 고유 전각 문장부호(，, ：, 、) 감지")

        # -------------------------------------------------------------
        # 2-2. 일본식 라노벨/웹소설 서식 (물결표 부제, 문장형 제목) 감지
        # -------------------------------------------------------------
        has_jp_tilde = bool(re.search(r'~[^~]+~', full_text))
        has_jp_sentence = bool(re.search(r'[가-힣]+에서\s+[가-힣]+(으)?로', full_text) or re.search(r'[가-힣]+(했|였)더니', full_text))
        # 한국어 소설의 일상적 문장과 구분하기 위해 번역 태그나 라노벨 단서가 있을 때 가산
        if (has_jp_tilde or has_jp_sentence) and (cls.TRANSLATION_TAGS.search(full_text) or jp_score > 0):
            jp_score += 45
            reasons.append("일본식 라노벨/웹소설 서식(물결표 부제/문장형 제목) 감지")

        # -------------------------------------------------------------
        # 2-3. 띄어쓰기 여부 분석 (원문 한자 독음 직역 vs 번역 제목 / 국내작)
        # -------------------------------------------------------------
        # 괄호, 특수기호, 숫자를 제거한 순수 한글 제목 추출
        clean_title_no_bracket = re.sub(r'[\(\[\{（【〔［《〈｛].*?[\)\]\}）】〕］》〉｝]', '', title or raw_name).strip()
        clean_title_words = re.sub(r'[\d\-~+~_,\.!?，：]+', ' ', clean_title_no_bracket).strip()
        words = [w for w in clean_title_words.split() if w]
        is_spaced = len(words) >= 2
        korean_only = re.sub(r'[^가-힣]', '', clean_title_words)
        korean_len = len(korean_only)

        if not is_spaced:
            # [Case A: 띄어쓰기가 없는 무공백 한자 독음 제목]
            # 중국/일본 원문은 띄어쓰기가 없으므로, 번역 없이 한국식 한자 독음으로 옮겨 적은 경우
            if korean_len >= 7:
                if cls.CN_PHONETIC_GRAMMAR_REGEX.search(korean_only):
                    cn_score += 70
                    reasons.append(f"띄어쓰기 없는 장문({korean_len}자) 중국 한자 독음 직역 제목 감지: '{korean_only}'")
                elif cls.JP_PHONETIC_GRAMMAR_REGEX.search(korean_only):
                    jp_score += 70
                    reasons.append(f"띄어쓰기 없는 장문({korean_len}자) 일본 한자 독음 직역 제목 감지: '{korean_only}'")
                else:
                    cn_score += 45
                    reasons.append(f"띄어쓰기 없는 장문({korean_len}자) 한자 독음형 제목 감지")
            elif korean_len >= 3:
                # 3~6자의 무공백 제목: 중국/일본 특유의 음독 어휘가 있을 때만 가산 (한국 무협/판타지 오탐 방지)
                if cls.CN_PHONETIC_GRAMMAR_REGEX.search(korean_only):
                    cn_score += 60
                    reasons.append(f"띄어쓰기 없는 중국 고유 한자 독음 어휘 일치: '{korean_only}'")
                elif cls.JP_PHONETIC_GRAMMAR_REGEX.search(korean_only):
                    jp_score += 60
                    reasons.append(f"띄어쓰기 없는 일본 고유 한자 독음 어휘 일치: '{korean_only}'")
        else:
            # [Case B: 정상 띄어쓰기가 된 제목 (번역 제목 또는 국내 창작물)]
            # 번역된 제목의 경우에는 띄어쓰기가 되어 있으므로 무공백 음독 점수는 부여하지 않고,
            # 번역 태그나 외래 플랫폼/클리셰가 없을 경우 국내 창작물 가산
            reasons.append(f"정상 띄어쓰기 어절 구조({len(words)}개 어절) 감지 (무공백 한자 독음 제외)")
            if not cls.TRANSLATION_TAGS.search(full_text) and cn_score == 0 and jp_score == 0:
                kr_score += 30
                reasons.append("번역 마커 없는 정상 한국어 띄어쓰기 문장 (국내 창작물 가산)")

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

        # -------------------------------------------------------------
        # 3-1. 중국어 음독/클리셰 분석 엔진(ChinesePhoneticAnalyzer) 통합
        # -------------------------------------------------------------
        try:
            from core.utils.chinese_phonetic_analyzer import ChinesePhoneticAnalyzer
            phonetic_res = ChinesePhoneticAnalyzer.analyze(full_text, title)
            if phonetic_res.is_detected:
                # 한국 소설에도 흔한 일반적 게임/스포츠/공포/현대/전통무협 키워드 단독 출현 시 CN 오감지 방지
                is_generic_trope = any(
                    generic in (phonetic_res.reason or "")
                    for generic in ["게임판타지/생존게임 클리셰", "스포츠", "공포/괴담", "전문직/연예계", "전통 무협/강호 클리셰"]
                ) and not any(
                    cjk_kw in (phonetic_res.matched_pattern or "")
                    for cjk_kw in ["생존유희", "生存游戏", "유희", "游戏", "속성반", "공로구생", "도생", "계통", "系统", "골드핑거", "모의기", "고룡", "국술", "대종사", "횡추", "극도무성", "용상반약공"]
                )
                if not is_generic_trope:
                    cn_score += 80
                    reasons.append(f"중국어 음독/클리셰 분석 일치: {phonetic_res.reason} (패턴: {phonetic_res.matched_pattern})")
        except Exception:
            pass

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
                cn_clues = [
                    '천월', '중생', '적녀', '서녀', '장공주', '모반', '조반', '국사', '후궁', '황숙',
                    '수책', '교낭', '총후', '복녀', '미색', '망절', '보위', '성료', '쾌천', '침춘환',
                    '곽격', '자연마법', '선자', '아재', '아진적', '아능', '아도시', '나사년', '종편',
                    '포부', '니문', '별태리보', '오월령', '적장부', '적신도', '대기련기', '련기'
                ]
                if any(c in full_text for c in cn_clues):
                    cn_score += 50
                    reasons.append("번역 소설 내 중국 고유 음독/어휘 단서 감지")
                elif has_jp_tilde or has_jp_sentence:
                    jp_score += 50
                    reasons.append("번역 소설 내 일본 라노벨 서식 단서 감지")
                else:
                    cn_score += 20
                    jp_score += 20

        # -------------------------------------------------------------
        # 4. 장르 기반 판별 가산점
        # -------------------------------------------------------------
        genre_clean = genre.strip(" []()")
        if "선협" in genre_clean or any(k in full_text for k in ['[선협]', '선협,', ', 선협']):
            cn_score += 70
            reasons.append("고유 장르 '선협' (중국 오리지널 99%)")
        elif "언정" in genre_clean or any(k in full_text for k in ['[언정]', '언정,', ', 언정']):
            cn_score += 70
            reasons.append("고유 장르 '언정' (중국 여성향 100%)")
        elif any(k in full_text for k in ['[사합원]', '사합원,', ', 사합원']):
            cn_score += 70
            reasons.append("고유 소재 '사합원' (베이징 전통가옥 100%)")

        # -------------------------------------------------------------
        # 5. 고유 어휘 및 클리셰 패턴 검사
        # -------------------------------------------------------------
        combined_text = f"{full_text} {cjk_source}".strip()

        # (A) 중국 고유 어휘 검사 (최대 2개 누적 가산)
        cn_trait_count = 0
        for kw, desc in cls.CN_TRAIT_KEYWORDS.items():
            if kw in combined_text:
                score_to_add = 40 if cn_trait_count == 0 else 25
                cn_score += score_to_add
                reasons.append(f"중국 고유 클리셰 어휘: {kw} ({desc})")
                cn_trait_count += 1
                if cn_trait_count >= 2:
                    break

        # (B) 일본 고유 어휘 검사
        for kw, desc in cls.JP_TRAIT_KEYWORDS.items():
            if kw in combined_text:
                # 마왕, 용사, 이세계, 슬로우라이프 등은 한국 판타지에도 자주 쓰이므로 번역 태그나 해외 단서가 있을 때만 가산
                if kw in ['마왕', '용사', '이세계', '슬로우라이프', '슬로우 라이프'] and not has_translation_tag and jp_score == 0:
                    continue
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
