#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명 정규화 도구 - 핵심 로직 모듈

한국 웹소설/라이트노벨 파일명을 표준화된 형식으로 변환하는 정규화 로직을 제공합니다.

주요 기능:
    - 장르 카테고리 정규화 (예: 퓨전판타지 → 퓨판)
    - 완결 표시 통일 (完, 완, Complete → (완))
    - 범위 정보 추출 및 정리 (1-536화 → 1-536)
    - 외전/후기 정보 처리 (番外 → 외전)
    - 저자명 제거 (@닉네임, ⓒ닉네임)
    - 노이즈 제거 (번역 정보, 불필요한 키워드)
    - 부 정보 위치 조정 (범위 앞으로 이동)

표준 파일명 형식:
    [카테고리] 제목 부정보 범위 (완) + 외전정보.확장자
    예: [판타지] 마법사의 모험 1-2부 1-100 (완) + 외전 1-5.txt

버전: 1.0.1
작성일: 2025-02-10
"""

import re
import csv
from pathlib import Path
from typing import Tuple, Optional, List, Dict

# ============================================================================
# 설정 및 상수
# ============================================================================

# 파일 경로 (독립 실행 시 사용)
INPUT_FILE = Path('list.txt')
OUTPUT_LIST = Path('normalized_list.txt')
OUTPUT_CSV = Path('mapping.csv')

# 허용된 장르 목록 (화이트리스트)
# 이 목록에 없는 장르는 카테고리에서 제외됨
GENRE_WHITELIST = {
    '소설',      # 일반 소설
    '판타지',    # 판타지
    '현대',      # 현대물
    '현판',      # 현대판타지
    '무협',      # 무협
    '선협',      # 선협
    '스포츠',    # 스포츠
    '퓨판',      # 퓨전판타지 (퓨전 통합)
    '역사',      # 역사물
    '로판',      # 로맨스판타지 (로맨스, BL 통합)
    'SF',        # SF
    '겜판',      # 게임판타지 (게임 통합)
    '언정',      # 언어정령
    '공포',      # 공포
    '패러디',    # 패러디
}

# 장르 매핑 (추론 결과 → 표준 장르명)
GENRE_MAPPING = {
    '퓨전': '퓨판',      # 퓨전 → 퓨판으로 통일
    '게임': '겜판',      # 게임 → 겜판으로 통일
    '로맨스': '로판',    # 로맨스 → 로판으로 통일
    'BL': '로판',        # BL → 로판으로 통일
}

# 장르 추론을 위한 키워드 매핑
GENRE_KEYWORDS = {
    '판타지': [
        '마법', '마왕', '용', '드래곤', '엘프', '던전', '모험', '마검', '마도',
        '정령', '마나', '스킬', '레벨', '각성', '전생', '환생', '회귀', '빙의',
        '차원', '이세계', '소환', '영웅', '마탑', '길드', '몬스터', '보스',
        '마법사', '대마법사', '네크로맨서', '마검사', '소환사', '용사', '마왕',
        '대공', '공작', '후작', '백작', '자작', '남작', '공왕', '시스템',
        '마법학교', '소드마스터', '데몬', '마녀', '연금술사', '인형술사',
        '골렘', '나이트', '기사', '영주', '영지', '크라켄', '환수'
    ],
    '무협': [
        '검', '협', '무림', '강호', '문파', '장로', '제자', '사부', '무공',
        '내공', '기공', '검법', '장법', '권법', '절학', '비급', '고수', '대협',
        '협객', '검객', '검사', '검성', '검제', '검황', '무당', '소림', '화산',
        '개방', '사파', '정파', '마교', '혈교', '천마', '마두', '검마',
        '무협', '강호', '협객', '검성', '검황', '천마', '혈마',
        '곤륜', '점창', '무당파', '남궁세가', '제갈세가', '팽가', '아미파',
        '무제', '무신', '무왕', '무성', '무사', '호위무사', '객잔', '숙수', '객점', '신마',
        '당문', '사천당가', '백씨세가', '서문', '반점', '낙향문사', '삼류무가',
        '천하제일인', '소교주', '대사형', '침술', '괴존', '신검', '신귀', '마도명가',
        '마도제일검', '마신', '사신', '산서제일가', '석대세가', '설혼', '악역무쌍',
        '일세지존', '대창수', '농로', '권황', '공자', '참요록'
    ],
    '현판': [
        '헌터', '각성자', '능력자', '이능', '초능력', '게이트', '던전', '몬스터',
        '현대', '학원', '학생', '회사', '직장', '재벌', '회장', '사장',
        '각성', 'a급', 'b급', 's급', 'ss급', 'sss급', 'ssss급', 'sssss급', 'ex급',
        '등급', '랭킹', '레벨업', '성장', '무한', '탑', '공략', '생존', '법칙',
        '2024', '2025', '2030', '대한민국', '한국', '독립전쟁',
        '비트코인', '걸그룹', '국세청', '국가실세', '매니저', '검사', '감전', '엔지니어',
        '영화감독', '프로듀서', '엔터테인먼트', '어촌', '귀향', '1980', '1982', '1990',
        '회사원', '신입사원', '제대', '이등병', '병장', '소대장',
        # 방송/미디어
        '스트리밍', '유튜브', '유튜버', '방송', '방송국', '피디', 'pd',
        # AI/기술
        'ai', 'AI', '인공지능', '해킹', '해커', '핵무기',
        # 경제/비즈니스
        '투자', '주식', 'CEO', '부동산', '투자의 신', '퇴사', '입사', '경영', '경매',
        '세일즈맨', '대표님', '비자금', '로또', '코인', '돈', '고아',
        # 교육
        '대학', '대학생', '삼류대', '명문대', '복학생', '로스쿨',
        # 엔터테인먼트
        'manager', 'entertainer', '스타', '연예인', '가수', '배우', '연기자', '싱어',
        '톱스타', '탑스타', '아이돌', '연예계', '팬', '연출', '조연출', '작가', '작곡',
        '데뷔', '아역', '뮤지컬', '음악', '보컬', '천재배우', '연기천재', '작곡가',
        '드라마', '영화', '애니메이션', '소설가', '레트로',
        # 직장/회사
        '회장님', '과장', '부장', '상무', '이사', '전무', '회사', '파티셰', '사원',
        # 법조
        '판사', '변호사', '승소', '패소', '고졸변호사',
        # 의료
        '의사', '명의', '닥터', '수의사', '외과의사', '깡촌의사', '침술명의',
        # 가족
        '이혼', '재혼', '딸', '삼촌',
        # 회귀/환생
        '트럭', '회귀자', '귀환자', '과로사',
        # 기타 현대 키워드
        '국정원', '특전사', '군인', '순직', '귀농', '귀촌', '식당', '마트', '편의점',
        '동물병원', '차트', '스마트폰', '퀘스트', '버킷리스트', '언더커버',
        '아포칼립스', '종말', '멸망', '생존', '통제관', '킹', '힐러',
        '드루이드', '공간', '창고', '인벤토리', '스트리머', '과금', '방구석',
        '옥탑방', '야산', '깜빵', '벼락', '예지', '미래', '귀신', '영단',
        '라그나로크', '슈퍼솔져', '에이스', '히어로', '빌런', '악역',
        '이발병', '요리사', '알바생', '조향사', '고고학자', '경비병',
        '유학생', '만능', '융복합', '은퇴', '전설', '최강', '사냥꾼',
        '보안관', '변호', '작두', '손', '옷', '기록', '시한부', '연기',
        '엑스트라', '설정', '껌딱지', '최애', '소문', '순두부상',
        '두메산골', '작가', '그레이트써전', '써전', '대표', '덕질',
        '향기로운', '세일즈', '셀럽', '레이디', '온에어', '완벽한',
        '실눈', '우리', '원래', '강한데', '위대한', '항해', '은퇴한',
        '조용히', '은하계', '음악동아리', '나라', '없앨', '음탕한',
        '겜친', '동생', '건들면', '새끼', '안에', '왕국', '현실',
        '주식계좌', '떡상', '캐릭', '플레이어', '사납다', '멸망시킨',
        '부족', '내일', '향해', '쏴라', '너드남', '흑화', '너의',
        '너희들', '변호됐다', '노랑머리', '수군통제사', '눈떠보니',
        '니네', '파티', '쩔더라', '달빛', '당신들', '소원대로',
        '퇴장', '대표님', '대한민국엔', '덕질하던', '도파민', '폭발',
        '게임방송', '독마', '약손', '두번', '타격', '메이커',
        '환수', '살아가는법', '디펜스', '챌린지', '딸이랑', '냥이랑',
        '시골', '똑딱이', '라이벌', '그만두겠습니다', '라이프', '겜블',
        '랜덤스킬', '인생역전', '레벨업', '만이', '살길', '로맨스가',
        '가능해', '알바생', '하프엘프', '키우는법', '야산', '묻혀버렸더니',
        '약초밭', '어게인', '마이', '라이프', '어느날', '어두운',
        '바다', '등불', '어둠은', '시각', '집어삼킨다', '얼굴천재',
        '엔딩', '안내서', '여배우', '여섯', '영혼', '노래', '여우',
        '기다리는', '연예계', '퇴물', '등교', '영광', '해일로',
        '영단', '먹고', '예지', '옆집', '예고', '옥탑방', '세계수',
        '야스킹', '완벽한', '요리사', '레벨업', '숨김', '우리딸들',
        '융복합', '다재다능', '음악동아리', '이가문', '미친놈',
        '이능', '계승', '특성', '이동요새', '이런환생', '원치않아',
        '이발병', '머리', '잘자름', '이번생', '이세계', '방랑자',
        '사람들', '보은', '외과의사', '존버킹', '생존좌', '흙수저',
        '선원', '찍었더니', '천만감독', '데려왔습니다', '능력',
        '흡수', '이혼예정', '남편', '하룻밤', '유예', '귀농했더니',
        '손만대면', '터짐', '미래가', '보이기', '작두', '탔습니다',
        '축구', '쉬워짐', '파혼', '낫더라', '가족', '버렸다',
        '인생', '리메이크', '살육', '미친', '상수리나무', '아래',
        '서리명가', '검술천재', '서부', '검은머리', '용병', '세계수',
        '하숙집', '어서오세요', '소드마스터', '소문', '커플',
        '순두부상', '순직', '슈퍼솔져', '스마트폰', '든', '세종',
        '스타피디', '사는법', '시작부터', '월드클래스', '신세계',
        '신화급', '귀속아이템', '손에넣었다', '창고', '얻었다',
        '아늑하게', '살고있습니다', '안그만두겠습니다', '기회',
        '얻었다', '속', '만렙', '포인트', '진화', '무한진화',
        '마트합니다', '통제관', '악인', '흡수', '지구최강',
        '알고보니', '일대일', '하프엘프', '암살', '신', '최강힐러',
        '약파는', '황태자', '약초밭', '깡촌명의', '어게인마이라이프',
        '퀘스트', '보이기시작했다', '회귀자', '버킷리스트', '등불',
        '되어', '시각', '얼굴천재', '연기천재', '회귀', '에이스히어로',
        '엔딩', '위한', '안내서', '여배우', '회귀피디', '좋아해',
        '여섯영혼', '노래', '그리고', '가수', '여우', '기다리는',
        '연예계퇴물', '등교', '다시시작', '영광', '해일로', '영단',
        '먹고', '예지', '얻다', '옆집', '대표님', '이사왔다',
        '예고', '음악천재', '옥탑방세계수', '야스킹', '온에어',
        '완벽한실눈', '악역', '연기', '요리사', '레벨업', '숨김',
        '우리딸들', '돈', '잘번다', '융복합다재다능', '은퇴한전설',
        '조용히', '살고싶다', '은하계', '각성', '음악동아리',
        '회귀자', '있다', '이가문', '미친놈', '나야', '이나라',
        '없앨', '예정', '이능계승', '특성', '있다', '이동요새',
        '아포칼립스', '살아남기', '이런환생', '원치않아', '이발병',
        '머리', '너무잘자름', '이번생', '아역부터', '이세계방랑자',
        '생존하는법', '사람들', '자꾸만', '보은', '외과의사',
        '존버킹생존좌', '흙수저선원', '찍었더니천만감독',
        '데려왔습니다', '능력', '흡수', '이혼예정', '남편',
        '하룻밤', '보냈다', '이혼유예', '귀농했더니', '손만대면',
        '터짐', '미래가보이기시작', '작두탔습니다', '축구',
        '너무쉬워짐', '이혼보다파혼', '낫더라', '가족버렸다',
        '인생리메이크', '천재애니메이션감독', '살육미친스트리머'
    ],
    '겜판': [
        '게임', 'VR', '가상', '현실', '접속', '로그인', '로그아웃', '플레이어',
        '유저', 'NPC', 'npc', '퀘스트', '아이템', '인벤토리', '스탯', '스킬', '레벨업',
        '경험치', '길드', '파티', '레이드', '보스', '공략', 'RPG', 'MMORPG',
        '갓겜', '게임속', '게임 속', '온라인', '시스템', '게이머', '게임난이도',
        '미쳤다', '고인물', '리셋', '싫다', '손', '잡지않는다', '화려하다', '망겜', '갇힌',
        '중심', '듀얼', '외치다', '지휘관', '복사', '라이벌', '그만두겠습니다',
        '라이프겜블', '러브코미디', '망가뜨리는', '방법', '디펜스게임',
        '폭군', '되었다', '챌린지', '이단심문관', '찐따', '멸망한세계',
        '농부', '요리사', '요한', '유일한상속자', '모래위', '연금술사',
        '꽃만키우는데', '너무강함', '식사하고가세요', '마법면역',
        '클리어', '멸망이후', '세계', '멸망한세계'
    ],
    '퓨판': [
        '편의점', '헌터', '각성', '던전', '탑', '레벨', '스킬', '능력',
        '이세계', '차원', '귀환', '회귀', '환생', '전생', '빙의',
        '시스템', '퀘스트', '스탯', '랭커', '먼치킨', '계산주의자',
        '겟어라이프', 'get a life', 'get', 'life', '격란', '자연과학원', '경력직',
        '다크니스', '로드', '다크니스로드',
        '멸망', '싫다', '경매', '맞짱뜨다', '귀촌', '첫날', '차원문',
        '생겼다', '귀환전', '미혼', '귀환후', '편의점', '귀환자',
        '압살', '귀환한먼치킨', '귀환한삼촌', '재앙급', '투신',
        '금쪽같은', '소환수', '기간트', '미친', '천재공학자',
        '기억상실', '마녀', '주워버렸다', '나혼자', '스마트폰',
        '고인물', '신화급', '군단소환', '정품유저', '차원지식',
        '독점', '총알무한', '탑에서농사', '마법면역', '클리어',
        '홀로', '최강포식자', '플레이어', '군주', '스켈레톤',
        '키운다', '회귀자', '아닙니다', '나만탑있어', '내마음대로',
        '내머릿속', '소드마스터', '내반사기', '무적', '내소환수',
        '무한', '내캐릭', '내플레이어들', '사납다', '멸망시킨',
        '부족', '후예', '내일', '향해', '쏴라', '다만드는',
        '제작천재', '다크니스로드', '독마', '손', '약손', '독보적',
        '스킬', '화려', '랜덤스킬', '인생역전', '레벨업만이',
        '살길', '알고보니', '일대일', '천재', '암살', '신',
        '최강힐러', '되다', '암흑명가', '망나니', '되었다',
        '귀촌첫날', '차원문', '귀환전', '미혼', '귀환후', '던전편의점',
        '귀환자', '각성', '압살', '귀환한먼치킨', '계산주의자',
        '귀환한삼촌', '재앙급투신', '금쪽같은소환수', '기간트',
        '미친천재공학자', '기억상실', '마녀', '주워버렸다',
        '나혼자스마트폰고인물', '신화급군단소환', '정품유저',
        '차원지식독점', '총알무한', '탑에서농사', '마법면역',
        '클리어', '홀로이세계최강포식자', '이세계플레이어',
        '군주', '스켈레톤키운다', '회귀자아닙니다', '나만탑있어',
        '내마음대로', '내머릿속소드마스터', '내반사기무적',
        '내소환수무한', '내캐릭무한', '내플레이어들사납다',
        '멸망시킨부족후예', '내일향해쏴라', '다만드는제작천재',
        '다크니스로드', '독마손약손', '독보적스킬화려',
        '랜덤스킬인생역전', '레벨업만이살길', '알고보니일대일천재',
        '암살신최강힐러', '암흑명가천재망나니', '마을소녀',
        '던전마스터', '마존', '현세강림기', '만렙찍고레벨업',
        '망겜', '갇힌고인물', '지휘관', '스킬복사', '멸망급',
        '데스나이트', '회귀', '멸망한세계', '농부', '요한',
        '유일한상속자', '물량', '나혼자독식', '무적', '무한정',
        '지속', '물량나혼자독식', '무적무한정지속', '빙의한악역',
        '너무강함', '서리명가검술천재', '설정찍는엑스트라',
        '스킬복제', '방랑자', '악인능력', '흡수', '지구최강',
        '알고보니일대일', '아포칼립스포인트진화', '무한진화',
        '아포칼립스', '나혼자생존게임', '악은삶', '바란다',
        '악인능력만흡수', '어느회귀자', '버킷리스트', '영웅모으는',
        '고고학자', '영주다시태어나다', '영주님', '전설',
        '용병단장', '영주다자다복', '신령한가족', '이능계승',
        '특성', '이동요새', '아포칼립스살아남기', '이세계검은머리',
        '외국인', '이세계방랑자', '생존하는법', '이세계사람들',
        '자꾸만보은', '이세계외과의사', '이세계존버킹생존좌',
        '이세계흙수저선원', '이세계능력', '흡수', '이세계드루이드',
        '이세계마신', '왕의힘', '회귀', '대심해', '크라켄',
        '대출산시대', '생존', '디펜스챌린지', '마도시대흑기사',
        '마을소녀던전마스터', '만렙찍고', '망겜갇힌',
        '망겜지휘관스킬복사', '멸망급데스나이트회귀',
        '멸망한세계농부', '멸망한세계요한', '멸망한세계유일한상속자',
        '물량나혼자독식', '무적무한정지속', '빙의한악역너무강함',
        '서리명가검술천재회귀', '설정찍는', '스킬복제방랑자',
        '악인능력흡수지구최강', '아포칼립스포인트진화무한진화',
        '아포칼립스나혼자생존게임', '악은삶바란다',
        '어느회귀자버킷리스트', '영웅모으는고고학자',
        '영주다시태어나다', '영주님전설용병단장',
        '영주다자다복신령한가족', '이능계승특성',
        '이동요새아포칼립스살아남기', '이세계검은머리외국인',
        '이세계방랑자생존하는법', '이세계사람들자꾸만보은',
        '이세계외과의사', '이세계존버킹생존좌',
        '이세계흙수저선원', '이세계능력흡수', '이세계드루이드',
        '이세계마신', '왕의힘회귀', '난세', '환생', '치트급랭커',
        '남겨진남자', '노예하렘', '삼촌', '돌아왔다', '공간',
        '지배', '공방', '인형술사', '공청석유', '엘릭서',
        '생겼더니', '변방', '의느님'
    ],

    '로판': [
        # 로맨스 키워드
        '사랑', '연애', '결혼', '신부', '신랑', '남편', '아내', '약혼', '청혼',
        '데이트', '키스', '고백', '짝사랑', '첫사랑', '운명', '인연', '로맨스',
        '집착한다', '집착', '최애', '고대로돌아간수의사',
        '권모', '내아내', '비서입니다', '러스트', '리와인드필름',
        'rewind film', '막장인소', '살아남는방법', '옥무향',
        '온에어', '유해한친구', '이혼예정남편하룻밤보냈다',
        '이혼유예', '소문그커플', '고대수의사', '비서', '인소',
        '유해한', '친구',
        # 로판 키워드
        '공작', '공녀', '황제', '황후', '황녀', '왕자', '공주', '귀족', '백작',
        '후작', '남작', '기사', '시녀', '집사', '메이드', '영애', '영지', '성',
        '궁전', '무도회', '사교계', '혼약', '파혼', '악녀', '빙의', '환생',
        '대공', '공왕', '자작', '여주', '여주인공', '계약직아내',
        '이만떠나렵니다', '남주들', '첫날밤', '수집', '내동생',
        '건들면', '죽은목숨', '너드남', '흑화', '막아보겠습니다',
        '던전호텔', '오신것', '환영', '로스트차일드', '로조종저시진적광',
        '로판', '살아남기', '사랑스러운', '그대', '만나기위해',
        '상수리나무아래', '서브남주', '파업', '생기는일',
        '세계수하숙집', '어서오세요', '셀럽레이디', '멸망엔딩',
        '최애', '구하는방법', '여름', '언어', '신데렐라',
        '역대급빌런', '구해버린', '무명히어로', '영웅', '경비병',
        '사랑해버렸다', '이단심문관', '되었습니다', '계약직아내',
        '이만떠나렵니다', '남주들첫날밤수집', '내동생건들면',
        '죽은목숨', '너드남흑화막아보겠습니다', '던전호텔',
        '오신것환영', '로스트차일드', '로조종저시진적광',
        '로판살아남기', '사랑스러운그대만나기위해',
        '상수리나무아래', '서브남주파업생기는일',
        '세계수하숙집어서오세요', '셀럽레이디', '멸망엔딩최애',
        '구하는방법', '여름언어신데렐라', '역대급빌런구해버린',
        '무명히어로', '영웅경비병사랑해버렸다', '이단심문관되었습니다'
    ],
    '역사': [
        '조선', '고려', '삼국', '신라', '백제', '고구려', '구한말', '대한제국',
        '왕', '왕비', '세자', '대군', '공주', '궁', '한양', '양반', '사대부', '선비', '무사', '장군',
        '임진왜란', '병자호란', '역사', '시대', '전쟁', '삼국지', '춘추전국',
        '열도', '침몰', '작전명', '독립', '런던', '파리', '로마', '빅토리아',
        '19세기', '20세기', '1941', '1945', '대전', '세계대전',
        '바이킹', '중세', '탐관오리', '고종시대', '회귀', '특전사',
        '정치', '너무잘함', '광해', '대륙정벌', '대명문괴',
        '더퍼거토리', '노랑머리', '수군통제사', '나폴레옹',
        '천재아들', '서부', '검은머리용병', '스마트폰', '든세종',
        '슬기로운', '대궐생활', '위대한항해', '이독일',
        '총통', '필요해요', '고종시대회귀특전사정치너무잘함',
        '광해대륙정벌', '대명문괴', '더퍼거토리',
        '노랑머리수군통제사', '나폴레옹천재아들',
        '서부검은머리용병', '스마트폰든세종', '슬기로운대궐생활',
        '위대한항해', '이독일총통필요해요'
    ],
    '선협': [
        '선', '선인', '선녀', '도', '도사', '수련', '득도', '비선', '승천',
        '천계', '선계', '영약', '영초', '영물', '법보', '법술', '도법', '진법',
        '선문', '도문', '종문', '장문', '진인', '상선', '대선',
        '선협', '신선', '수선', '법술', '장생', '수행', '나는두세계봉인',
        '가지고있다', '매달치트키', '갱신', '수있다', '마천기',
        '비천', '사상최강', '스승님', '시작부터당무린', '혈맥',
        '뽑아냈다', '전구고무', '나는두세계봉인가지고있다',
        '매달치트키갱신수있다', '사상최강스승님',
        '시작부터당무린혈맥뽑아냈다', '전구고무'
    ],
    'SF': [
        'SF', '우주', '외계', '로봇', '안드로이드', '사이보그', '메카', '함선',
        '우주선', '행성', '은하', '제국', '연방', '미래', '타임', '시간여행',
        '차원', '평행세계', '과학', '기술', '테크놀로지', '사상최강보안관'
    ],
    '스포츠': [
        '야구', '축구', '농구', '배구', '테니스', '골프', '수영', '육상',
        '선수', '감독', '코치', '경기', '시합', '대회', '우승', '챔피언',
        '올림픽', '월드컵', '리그', '팀', '구단', '훈련', '연습',
        'MLB', 'NBA', '라리가', '프리미어리그', '분데스리그', '매니저', 'manager', '레슬링',
        '라운더', '라운드', '마운드', '코트', '링', '경기장',
        '축구화', '발롱도르',
        # 야구 포지션
        '투수', '포수', '유격수', '1루수', '2루수', '3루수', '외야수', '중견수', '타자', '홈런',
        # 축구 포지션
        '공격수', '스트라이커', '수비수', '미들필더', '미드필더', '슈팅', '필드', '월클',
        # 격투기
        '복서', '복싱', '킥복싱', '유도', '태권도',
        # 스포츠 용어
        '판정승', '승부', '체육', '고독한', '에이스', '구속', '빼고', '다가짐',
        '똑딱이', '내눈', '스카우트', '라이즈리얼', '두번', '사는', '타격', '천재',
        '에이스히어로', '시작부터', '월드클래스', '이혼후', '축구', '너무', '쉬워짐'
    ],
    '공포': [
        '귀신', '유령', '좀비', '괴물', '악마', '저주', '원한', '공포', '호러',
        '살인', '미스터리', '추리', '범죄', '사건', '사고', '죽음', '시체',
        '피', '무서운', '오싹', '섬뜩'
    ],
    '언정': [
        # 중국 웹소설 특징적 키워드 (한글 변환된 중국어)
        # 특징: 의미 없는 한글 조합, 4글자 이상 연속
        '고가후상화리', '고대과거양와일상', '고대렵호적양가일상',
        '고대종전분투사', '공간농녀종전망', '공간소농녀', '공간물자',
        '과거문계모양와일상', '교술', '교주영옥', '국자감요리사',
        '낭자금리운', '낭자진부시사요', '년대랄식유공간',
        '대저삼보거종전', '년대소복처대착공간가초한', '농가복보유공간',
        '농진주', '유학생활', '단총맹보일세반', '대숙리혼청방수',
        '독보경화', '독부부종량', '미인아내', '탐정', '사공월아',
        '서서득정', '서자', '역습', '안락전', '제황서', '유생활계통후아폭부료',
        '대백억물자', '재70년대풍생수기',
        # 분해된 키워드
        '고가', '후상', '화리', '과거', '양와', '일상', '렵호적', '양가',
        '종전', '분투사', '농녀', '종전망', '소농녀', '문계모',
        '교주', '영옥', '국자감', '낭자', '금리운', '진부', '시사요',
        '년대', '랄식', '유공간', '대저', '삼보', '거종전', '소복처',
        '대착', '가초한', '복보', '농진주', '단총', '맹보', '일세반',
        '대숙', '리혼', '청방수', '독보', '경화', '독부', '부종량',
        '사공월아', '서서', '득정', '안락전', '제황서', '생활계통',
        '후아', '폭부료', '대백억', '재70년대', '풍생수기'
    ],
    'BL': [
        '그분이오신다', '매직온더데드', 'magic on the dead',
        '메인빌런', '껌딱지', '되어버렸다', '이소설', '서브공',
        '이상하다', '그분', '오신다', '빌런껌딱지'
    ],
    '패러디': [
        '나루토', '세계', '여자들', '다따먹음', '양아치', '간다',
        '호카게', '닌자', '통일', '츠치카게', '되었다',
        '오오츠츠키', '가문', '혈통', '시작', '아카츠키',
        '부터', '흑막', '여덟살', '내가', '우치하',
        '일족', '태어나', '여장', '이타치', '속임',
        '근육신', '이우치하', '너무조심스럽다',
        '나루토세계', '호카게닌자세계통일', '츠치카게되었다',
        '오오츠츠키가문혈통', '아카츠키부터시작흑막',
        '여덟살호카게', '우치하일족여장이타치속임',
        '우치하근육신', '이우치하너무조심스럽다'
    ]
}


# ============================================================================
# 유틸리티 함수
# ============================================================================

def normalize_unicode_spaces(text: str) -> str:
    """
    유니코드 공백 문자를 일반 공백으로 통일하고 연속된 공백을 하나로 압축
    
    Args:
        text: 정규화할 텍스트
        
    Returns:
        공백이 정규화된 텍스트
    """
    return re.sub(r'\s+', ' ', text.strip())


def extract_extension(name: str) -> Tuple[str, str]:
    """
    파일명에서 확장자를 분리
    
    지원 확장자: .txt, .epub, .zip, .zipx, .7z, .rar
    확장자 앞 공백도 제거합니다.
    
    Args:
        name: 파일명 (확장자 포함)
        
    Returns:
        (파일명, 확장자) 튜플
        예: ("파일명", ".txt")
    """
    m = re.search(r'\s*\.(txt|epub|zip|zipx|7z|rar)$', name, re.IGNORECASE)
    if not m:
        return name, ''
    # 확장자 앞 공백 제거
    return name[:m.start()].rstrip(), '.' + m.group(1)


# ============================================================================
# 카테고리 처리
# ============================================================================

def infer_genre_from_filename(filename: str, return_confidence: bool = False) -> Optional[str | Tuple[str, str]]:
    """
    파일명에서 키워드를 분석하여 장르 추론
    
    4단계 추론 시스템:
        0. 중국어-한글 변환 패턴 체크
        1. 복합 패턴 체크 (게임+현실, 주식+퇴사, 천마+방송 등)
           - 컨텍스트 기반 패턴이 단순 키워드보다 우선함
           - 예: "천마님 방송하신다" → 현판 (무협 아님)
        2. 고신뢰도 키워드 체크 (검황, 천마, 대마법사 등)
        3. 우선순위 키워드 체크 (헌터→퓨판 80%, S급→퓨판 70% 등)
        4. 일반 키워드 점수 계산
    
    신뢰도 레벨:
        - 'high': 90%+ 확정 (녹색)
        - 'medium': 50-90% 추정 (노란색, 사용자 확인 필요)
        - 'low': 추론 실패 (빨간색)
    
    새로 추가된 컨텍스트 패턴 (v1.1.0):
        주요 패턴:
        - "주식" + "퇴사" → 현판
        - "천마" + 현대 컨텍스트 (방송, 요리사) → 현판
        - "배우"/"아이돌" + 엔터테인먼트 → 현판
        - "공학자" + "영지" → 퓨판
        - "마공학자" → 퓨판
        - "용병" + "방송" → 현판
        - "파티셰" → 현판
        
        복합 키워드 패턴 (단일 키워드 보강):
        - "아이돌" + 일반 컨텍스트 (그룹, 이야기, 데뷔) → 현판
        - "판사"/"변호사" + 법조 컨텍스트 (일상, 사건) → 현판
        - "편의점" + 일반 컨텍스트 (알바, 점원) → 퓨판
        - "톱스타"/"탑스타" 단독 → 현판 (고신뢰도)
        - "회사" + 직장 컨텍스트 (직장, 입사, 퇴사) → 현판
    
    Args:
        filename: 분석할 파일명
        return_confidence: True면 (장르, 신뢰도) 튜플 반환
        
    Returns:
        장르 또는 (장르, 신뢰도) 튜플 또는 None
    """
    filename_lower = filename.lower()
    confidence = 'low'  # 기본값: 추론 실패
    genre = None
    
    # Helper: 장르 매핑 적용 후 반환
    def apply_mapping_and_return(g, c):
        mapped_genre = GENRE_MAPPING.get(g, g) if g else g
        return (mapped_genre, c) if return_confidence else mapped_genre
    
    # ========== 0단계: 중국어 한글 변환 패턴 체크 ==========
    # 예: "가급일개노황제", "가급장군후적종전일상" 등
    # 특징: 한글만 있고, 의미 없는 조합, 선협 키워드 없으면 미정
    if re.match(r'^[가-힣]+$', filename_lower):
        # 선협 키워드 있으면 선협
        if any(kw in filename_lower for kw in ['선협', '신선', '수선', '선인', '선계', '득도']):
            genre, confidence = '선협', 'high'
            return (genre, confidence) if return_confidence else genre
        # 그 외는 추론 안 함 (중국어 변환 가능성)
        if len(filename_lower) > 6:  # 긴 한글 조합은 의심
            return (None, 'low') if return_confidence else None
    
    # ========== 1단계: 복합 패턴 우선 체크 (high confidence) ==========
    
    # "갓겜" → 겜판 (확정, 다른 키워드보다 우선)
    if '갓겜' in filename_lower:
        genre, confidence = '겜판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "게임 속" → 겜판 (확정)
    if '게임 속' in filename_lower or '게임속' in filename_lower:
        genre, confidence = '겜판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "게임" + "현실" → 겜판
    if '게임' in filename_lower and '현실' in filename_lower:
        genre, confidence = '겜판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "게임 개발" + "제국" → 퓨판
    if ('게임 개발' in filename_lower or '게임개발' in filename_lower) and '제국' in filename_lower:
        genre, confidence = '퓨판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "게임 마인드" + "중세" → 역사
    if ('게임 마인드' in filename_lower or '게임마인드' in filename_lower) and '중세' in filename_lower:
        genre, confidence = '역사', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "게임PD" + "마법" → 퓨판
    if 'pd' in filename_lower and '마법' in filename_lower:
        genre, confidence = '퓨판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "재벌" + "검사"(법조인) → 현판
    if '재벌' in filename_lower and '검사' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 1980년대 이후 + 현대 키워드 → 현판
    if re.search(r'(19[89][0-9]|20[0-9]{2})', filename_lower):
        modern_keywords = ['대한민국', '한국', '독립', '전쟁', '대전', '어촌', '돌아가다', '귀향']
        if any(kw in filename_lower for kw in modern_keywords):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # "조선" (단, "유조선" 제외) → 역사
    if '조선' in filename_lower and '유조선' not in filename_lower:
        genre, confidence = '역사', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "대한제국" → 역사 (황제보다 우선)
    if '대한제국' in filename_lower:
        genre, confidence = '역사', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "구한말" → 역사
    if '구한말' in filename_lower:
        genre, confidence = '역사', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "온라인" → 겜판 우선 (게임 > 퓨판 > 현판)
    if '온라인' in filename_lower:
        genre, confidence = '겜판', 'medium'
        return (genre, confidence) if return_confidence else genre
    
    # "혈" + 현대 키워드 → 현판 (혈마보다 우선)
    if '혈' in filename_lower:
        modern_indicators = ['21세기', '20세기', '19세기', '2024', '2025', '2030', '현대']
        if any(kw in filename_lower for kw in modern_indicators):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # "천마의 유산" (천마 단독 아님) → 퓨판
    if '천마' in filename_lower and ('유산' in filename_lower or '계승' in filename_lower):
        genre, confidence = '퓨판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "감전" + "엔지니어" → 현판
    if '감전' in filename_lower and '엔지니어' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # ========== 새로운 컨텍스트 기반 패턴 (우선순위 순서) ==========
    
    # 1. "주식" + "퇴사" → 현판 (무협 아님)
    # 예시: "주식천재는 오늘도 퇴사각!"
    if '주식' in filename_lower and '퇴사' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 2. "천마" + 현대 컨텍스트 → 현판 (무협 아님)
    # 예시: "천마님 방송하신다", "천마님은 중화요리사"
    # 이 패턴은 2단계의 '천마' → 무협 분류를 덮어씀
    if '천마' in filename_lower:
        modern_context = ['방송', '중화요리사', '요리사']
        if any(kw in filename_lower for kw in modern_context):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # 3. "배우" 또는 "아이돌" + 엔터테인먼트 → 현판
    # 예시: "천만 안티 팬 배우님", "천재 배우가 작곡 능력을 숨김",
    #       "천재 아이돌의 연예계 공략법", "천재 아이돌이 회사를 탈주함"
    entertainment_keywords = ['팬', '연예계', '회사', '작곡']
    if ('배우' in filename_lower or '아이돌' in filename_lower):
        if any(kw in filename_lower for kw in entertainment_keywords):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # 4. "공학자" + "영지" → 퓨판/판타지 (로판 아님)
    # 예시: "천재 공학자의 역대급 영지 설계"
    if '공학자' in filename_lower and '영지' in filename_lower:
        genre, confidence = '퓨판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 5. "마공학자" → 퓨판/판타지 (제목에 "역사"가 있어도 덮어씀)
    # 예시: "천재 마공학자 역사를 다시 쓰다"
    if '마공학자' in filename_lower:
        genre, confidence = '퓨판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 6. "용병" + "방송" → 현판 (판타지 아님)
    # 예시: "천재 용병 방송으로 살아남기"
    if '용병' in filename_lower and '방송' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 7. "파티셰" → 현판
    # 예시: "천재 파티셰가 되었다"
    if '파티셰' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # ========== 추가 복합 패턴 (단일 키워드 보강) ==========
    
    # "아이돌" + 일반 키워드 → 현판
    # 예시: "아이돌 그룹 이야기"
    if '아이돌' in filename_lower:
        general_context = ['그룹', '이야기', '생활', '일상', '데뷔', '활동']
        if any(kw in filename_lower for kw in general_context):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # "판사" + 법조 관련 → 현판
    # 예시: "판사의 일상"
    if '판사' in filename_lower or '변호사' in filename_lower:
        legal_context = ['일상', '생활', '법정', '재판', '사건', '의뢰인']
        if any(kw in filename_lower for kw in legal_context):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # "편의점" + 일반 키워드 → 퓨판
    # 예시: "편의점 알바생"
    if '편의점' in filename_lower:
        convenience_context = ['알바', '아르바이트', '점원', '생활', '이야기', '일상']
        if any(kw in filename_lower for kw in convenience_context):
            genre, confidence = '퓨판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # "톱스타"/"탑스타" 단독 → 현판 (고신뢰도)
    if '톱스타' in filename_lower or '탑스타' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "회사" + 직장 관련 → 현판
    if '회사' in filename_lower:
        office_context = ['직장', '사원', '부장', '과장', '상사', '동료', '입사', '퇴사', '탈주']
        if any(kw in filename_lower for kw in office_context):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
    
    # ========== 2단계: 고신뢰도 키워드 체크 (high confidence) ==========
    
    high_confidence_keywords = {
        '판타지': ['대마법사', '네크로맨서', '드래곤', '마왕', '정령'],
        '무협': ['검황', '천마', '무림', '강호', '검성', '검제', '검마', '곤륜', '점창', '무당파', '소림', '남궁세가', '제갈세가', '팽가', '아미파', '무제', '무신', '호위무사'],
        '퓨판': ['검술명가', 'z 시대', '아카데미'],
        '겜판': ['갓겜', 'mmorpg', 'rpg'],
        '로판': ['공작', '황제', '악녀', '공녀', '황녀', '집착한다'],
        'SF': ['sf', '우주선', '안드로이드', '사이보그'],
        '선협': ['선인', '득도', '선계', '법술', '신선', '수선', '선협'],
        '스포츠': ['mlb', 'nba', '라리가', '프리미어리그', '분데스리그', '레슬링', '라운더', '마운드', '발롱도르', '축구화'],
        '공포': ['좀비', '호러'],
        '역사': ['열도', '침몰', '작전명', '임진왜란', '병자호란', '바이킹', '1941', '1945', '구한말', '대한제국'],
        '현판': ['비트코인', '걸그룹', '국세청', '국가실세', '게이트', '각성자', '엔지니어', '영화감독', '프로듀서', '엔터테인먼트', '회사원', '신입사원', '유튜브', '유튜버', '스트리밍', '인공지능', '트럭', '해킹', '해커', '핵무기', 'ceo', '대학생', '복학생']
    }
    
    for g, keywords in high_confidence_keywords.items():
        for keyword in keywords:
            if keyword in filename_lower:
                genre, confidence = g, 'high'
                return (genre, confidence) if return_confidence else genre
    
    # ========== 3단계: 우선순위 키워드 체크 ==========
    
    # S급/SS급/SSS급 → 문맥에 따라
    # "운빨", "확률" 등 게임 키워드 있으면 겜판(high), 아니면 퓨판(medium)
    if re.search(r'\b(s+급|ex급)', filename_lower):
        game_context_keywords = ['운빠', '운빨', '확률', '가챠', '뽑기', '랜덤']
        if any(kw in filename_lower for kw in game_context_keywords):
            genre, confidence = '겜판', 'high'
            return (genre, confidence) if return_confidence else genre
        genre, confidence = '퓨판', 'medium'  # 70% 확률
        return (genre, confidence) if return_confidence else genre
    
    # "헌터" → 퓨판(medium, 80%)
    if '헌터' in filename_lower:
        genre, confidence = '퓨판', 'medium'
        return (genre, confidence) if return_confidence else genre
    
    # "혈마" → 무협(high)
    if '혈마' in filename_lower:
        genre, confidence = '무협', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # "감독" → 문맥에 따라
    if '감독' in filename_lower:
        sports_keywords = ['야구', '축구', '농구', '배구', '선수', '팀', '리그', '골프', '수영', '육상', '레슬링', '라운더', '라운드', '마운드', '코트']
        if any(kw in filename_lower for kw in sports_keywords):
            genre, confidence = '스포츠', 'high'
            return (genre, confidence) if return_confidence else genre
        # 영화감독 등 엔터테인먼트
        entertainment_keywords = ['영화', '프로듀서', '엔터테인먼트', '배우', '연기', '촬영']
        if any(kw in filename_lower for kw in entertainment_keywords):
            genre, confidence = '현판', 'high'
            return (genre, confidence) if return_confidence else genre
        # 스포츠/엔터 키워드 없으면 미정
        genre, confidence = None, 'low'
        return (genre, confidence) if return_confidence else genre
    
    # 스포츠 관련 키워드 (라운더, 마운드, 코트 등)
    sports_field_keywords = ['라운더', '라운드', '마운드', '코트', '링', '경기장']
    if any(kw in filename_lower for kw in sports_field_keywords):
        genre, confidence = '스포츠', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 스포츠 포지션 및 핵심 키워드 (우선순위 높음)
    sports_position_keywords = ['투수', '포수', '유격수', '1루수', '2루수', '3루수', '외야수', '중견수', '타자', '홈런',
                                '공격수', '스트라이커', '수비수', '미들필더', '미드필더', '슈팅', '월클',
                                '복서', '복싱', '킥복싱', '유도', '태권도']
    if any(kw in filename_lower for kw in sports_position_keywords):
        genre, confidence = '스포츠', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 엔터테인먼트 키워드
    if any(kw in filename_lower for kw in ['영화감독', '프로듀서', '엔터테인먼트']):
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 회사원 키워드
    if any(kw in filename_lower for kw in ['회사원', '신입사원']):
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 군대 키워드 (제대, 이등병, 병장, 소대장)
    military_keywords = ['제대', '이등병', '병장', '소대장', '군대', '입대']
    if any(kw in filename_lower for kw in military_keywords):
        # 판타지/무협 키워드 있으면 퓨판, 없으면 현판
        fantasy_keywords = ['마법', '던전', '검', '무림', '강호']
        if any(kw in filename_lower for kw in fantasy_keywords):
            genre, confidence = '퓨판', 'medium'
            return (genre, confidence) if return_confidence else genre
        else:
            genre, confidence = '현판', 'medium'
            return (genre, confidence) if return_confidence else genre
    
    # "매니저" → 문맥에 따라
    if '매니저' in filename_lower:
        sports_keywords = ['야구', '축구', '농구', '배구', '선수', '감독', '팀', '리그', '골프', '수영', '육상', '레슬링']
        if any(kw in filename_lower for kw in sports_keywords):
            genre, confidence = '스포츠', 'high'
            return (genre, confidence) if return_confidence else genre
        else:
            genre, confidence = '현판', 'medium'
            return (genre, confidence) if return_confidence else genre
    
    # "재벌" → 현판(high)
    if '재벌' in filename_lower:
        genre, confidence = '현판', 'high'
        return (genre, confidence) if return_confidence else genre
    
    # 귀족 칭호 → 판타지(medium, 60%) 우선
    noble_titles = ['백작', '자작', '남작', '공작', '후작', '공녀', '황녀']
    if any(title in filename_lower for title in noble_titles):
        genre, confidence = '판타지', 'medium'
        return (genre, confidence) if return_confidence else genre
    
    # ========== 4단계: 일반 키워드 점수 계산 ==========
    
    genre_scores = {}
    
    for g, keywords in GENRE_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in filename_lower:
                score += 1
        if score > 0:
            genre_scores[g] = score
    
    # 점수가 가장 높은 장르 반환
    if genre_scores:
        best_genre = max(genre_scores, key=genre_scores.get)
        
        # 최소 2개 이상의 키워드가 매칭되어야 신뢰도 있음
        if genre_scores[best_genre] >= 2:
            genre, confidence = best_genre, 'high'
            return (genre, confidence) if return_confidence else genre
        
        # 1개만 매칭되어도 특정 장르는 신뢰도 높음
        elif best_genre in ['무협', '선협', '로판', 'SF', '스포츠', '공포', '역사'] and genre_scores[best_genre] >= 1:
            genre, confidence = best_genre, 'medium'
            # 장르 매핑 적용
            genre = GENRE_MAPPING.get(genre, genre)
            return (genre, confidence) if return_confidence else genre
    
    # 추론 실패
    return (None, 'low') if return_confidence else None


def detect_category(head: str) -> Tuple[Optional[str], str]:
    """
    파일명 시작 부분에서 장르 카테고리를 추출하고 정규화
    
    처리 패턴:
        - [판타지] → [판타지]
        - (무협) → [무협]
        - [퓨전판타지] → [퓨판]
        - [신무협] → [무협]
        - [판타지.무협] → [판타지.무협]
        - [골든아공간] → 제거 (화이트리스트에 없음)
        - [로맨스] → [로판] (매핑 적용)
        - [BL] → [로판] (매핑 적용)
        - [게임] → [겜판] (매핑 적용)
        - [퓨전] → [퓨판] (매핑 적용)
    
    Args:
        head: 파일명 (확장자 제외)
        
    Returns:
        (카테고리 또는 None, 나머지 텍스트) 튜플
        예: ("[판타지]", "제목 1-100 완")
    """
    # 시작 대괄호/소괄호로 카테고리 추출
    # 소괄호는 대괄호로 변환하여 반환
    m = re.match(r'^[\[\(]\s*(.*?)\s*[\]\)]\s*', head)
    if m:
        raw = normalize_unicode_spaces(m.group(1))
        tokens = re.split(r'[.,·]', raw)
        valid_tokens: List[str] = []
        for token in tokens:
            token = token.strip()
            # 동의어 정규화
            if token in ('신무협','퓨전무협','퓨전 무협'):
                token = '무협'
            elif token in ('퓨전판타지','퓨전 판타지'):
                token = '퓨판'
            elif token in ('현대판타지','현대 판타지'):
                token = '현판'
            elif token in ('대체역사','대체 역사'):
                token = '역사'
            
            # 장르 매핑 적용 (로맨스→로판, BL→로판, 게임→겜판, 퓨전→퓨판)
            token = GENRE_MAPPING.get(token, token)
            
            if token in GENRE_WHITELIST:
                valid_tokens.append(token)
        if valid_tokens:
            combined = '.'.join(valid_tokens)
            # 항상 대괄호로 반환 (소괄호도 대괄호로 변환)
            cat = f'[{combined}]'
            rest = head[m.end():].lstrip()
            return cat, rest
        else:
            rest = head[m.end():].lstrip()
            return None, rest
    return None, head


# ============================================================================
# 전처리 함수
# ============================================================================

def preprocess_symbols(text: str) -> str:
    """
    파일명의 특수 기호를 표준 형식으로 변환
    
    변환 규칙:
        숫자_숫자 → 숫자-숫자 (범위 표시, 먼저 처리)
        + → 공백 (완+外는 이후 패턴으로 처리)
        _ → 공백
        ~text~ → - text (물결표 사이 텍스트는 하이픈으로, 공백 보존)
        범위 공백 제거: 1 - 787 → 1-787
        잘못된 범위 수정: 1-.355 → 1-355
    
    Args:
        text: 변환할 텍스트
        
    Returns:
        기호가 변환된 텍스트
    """
    # "N-ABCD,M부" 패턴을 임시로 보호 (예: 1-6841,2부 → 1-6841§§COMMA§§2부)
    # 이 패턴은 나중에 extract_range_and_extras에서 처리됨
    text = re.sub(r'(\d+-\d+),(\d+부)', r'\1§§COMMA§§\2', text)
    
    # 숫자부_숫자부 패턴을 먼저 숫자-숫자부로 변환 (예: 1부_2부 → 1-2부)
    text = re.sub(r'(\d+)부_(\d+부)', r'\1-\2', text)
    
    # 숫자_숫자부 패턴을 먼저 숫자-숫자부로 변환 (예: 1_2부 → 1-2부)
    text = re.sub(r'(\d+)_(\d+부)', r'\1-\2', text)
    
    # 숫자_숫자 패턴을 먼저 숫자-숫자로 변환 (예: 001_304 → 001-304)
    # 이렇게 하면 나중에 _를 공백으로 변환해도 범위가 보존됨
    text = re.sub(r'(\d+)_(\d+)', r'\1-\2', text)
    
    # 001회~111회 → 001회-111회 (물결표를 하이픈으로)
    text = re.sub(r'(\d+)(회|화|편|권)~(\d+)(회|화|편|권)', r'\1\2-\3\4', text)
    
    # 괄호 안의 공백 제거 (예: ( 001회-111회) → (001회-111회))
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    
    # (숫자알파벳) 패턴 보호 (예: (19N), (18+) 등)
    # 이 패턴은 범위가 아니므로 _를 공백으로 변환하지 않음
    protected_patterns = []
    def protect_pattern(m):
        protected_patterns.append(m.group(0))
        return f'§§PROTECTED{len(protected_patterns)-1}§§'
    
    # (숫자+알파벳) 패턴 보호
    text = re.sub(r'\(\d+[A-Z+]+\)', protect_pattern, text)
    
    text = text.replace('+', ' ')
    text = text.replace('_', ' ')
    
    # 보호한 패턴 복원
    for i, pattern in enumerate(protected_patterns):
        text = text.replace(f'§§PROTECTED{i}§§', pattern)
    
    # (~숫자) 패턴을 1-숫자로 변환 (예: (~144) → 1-144, 괄호 제거)
    text = re.sub(r'\(~(\d+)\)', r'1-\1', text)
    
    # ~text~ 패턴을 - text로 변환 (예: ~난세서~ → - 난세서)
    text = re.sub(r'~([^~]+)~', r'- \1', text)
    # 남은 ~ 제거
    text = text.replace('~', '-')
    
    # 잘못된 범위 패턴 수정 (예: 1-.355 → 1-355)
    text = re.sub(r'(\d+)-\.(\d+)', r'\1-\2', text)
    
    # "N,M,P부" 패턴을 "N-P부"로 변환 (예: 1,2,3부 → 1-3부)
    # 먼저 3개 이상의 숫자가 있는 경우 처리
    # 패턴: 첫 숫자, (중간 숫자들,)* 마지막 숫자부
    text = re.sub(r'(\d+)(?:\s*,\s*\d+)+\s*,\s*(\d+)\s*부', r'\1-\2부', text)
    
    # "N, M부" 패턴을 "N-M부"로 변환 (예: 1, 2부 → 1-2부)
    # 주의: "N-ABCD,M부" 패턴은 보호 (예: 1-6841,2부)
    # 조건: 쉼표 앞에 하이픈이 없는 경우만 변환
    text = re.sub(r'(?<!-\d)(?<!-\d\d)(?<!-\d\d\d)(?<!-\d\d\d\d)(\d+)\s*,\s*(\d+부)', r'\1-\2', text)
    
    # "N- M부" 패턴을 "N-M부"로 변환 (예: 1- 2부 → 1-2부)
    # 부 범위 표시의 공백 제거
    text = re.sub(r'(\d+)\s*-\s+(\d+부)', r'\1-\2', text)
    
    # 범위 표시의 공백 제거 (1 - 787 → 1-787)
    text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1-\2', text)
    
    # 제목과 숫자부 사이에 공백 추가 (예: 아이들1부 → 아이들 1부)
    text = re.sub(r'([가-힣a-zA-Z])(\d+부)', r'\1 \2', text)
    
    # 제목과 범위 사이에 공백 추가 (예: 산하1-192 → 산하 1-192)
    text = re.sub(r'([가-힣a-zA-Z])(\d+\s*-\s*\d+)', r'\1 \2', text)
    
    # 범위와 (완) 사이에 공백 추가 (예: 1-318(완) → 1-318 (완))
    text = re.sub(r'(\d+)\(완\)', r'\1 (완)', text, flags=re.IGNORECASE)
    
    # 제목과 (완) 사이에 공백 추가 (예: 메이지(완) → 메이지 (완))
    text = re.sub(r'([가-힣a-zA-Z])\(완\)', r'\1 (완)', text, flags=re.IGNORECASE)
    
    # 外를 외전으로 변환 (예: 外 5 → 외전 5, 1-100 外 → 1-100 외전)
    text = re.sub(r'\b外\b', '외전', text)
    
    return normalize_unicode_spaces(text)


def remove_basic_noise(text: str) -> str:
    """
    파일명에서 불필요한 노이즈 제거
    
    제거 대상:
        - @EE (특정 업로더 표시)
        - (AI번역), (기계번역), (손번역), (번역)
        - (txt), (epub) 등 파일 형식 표시
        - 본편, 및, 포함 등 불필요한 키워드
        - 연재중 키워드
        - (미결), (미완) 키워드
    
    변환 대상:
        - 외포 → 외전
        - 번외 → 외전
        - 왼전 → 외전 (오타 수정)
        - 작가의 말 → 후기
    
    Args:
        text: 정리할 텍스트
        
    Returns:
        노이즈가 제거된 텍스트
    """
    # [외전 포함] 패턴을 "외전포함"으로 변환 (나중에 처리)
    text = re.sub(r'\[외전\s*포함\]', '외전포함', text, flags=re.IGNORECASE)
    
    # [외전 후일담 포함] 패턴을 "외전 후일담"으로 변환
    text = re.sub(r'\[외전\s+후일담\s+포함\]', '외전 후일담', text, flags=re.IGNORECASE)
    
    # 에필포함 패턴을 "에필"로 변환하고 나머지 제거
    # 예: "에필포함수정" → "에필"
    text = re.sub(r'에필포함[가-힣]*', '에필', text, flags=re.IGNORECASE)
    
    # 특정 업로더 표시 제거
    text = re.sub(r'\s*@\s*EE\b', '', text, flags=re.IGNORECASE)
    
    # 번역 정보 제거
    text = re.sub(r'\s*\((AI번역|기계번역|번역|손번역)\)\s*', '', text, flags=re.IGNORECASE)
    
    # 파일 형식 표시 제거
    text = re.sub(r'\s*\(\s*(txt|epub)\s*\)', '', text, flags=re.IGNORECASE)
    
    # "연재중" 키워드 제거 (완결과 함께 있을 때)
    text = re.sub(r',?\s*연재\s*중\s*,?', '', text, flags=re.IGNORECASE)
    
    # (미결), (미완), [미완] 키워드 제거
    text = re.sub(r'\s*[\(\[]\s*(미결|미완)\s*[\)\]]\s*', '', text, flags=re.IGNORECASE)
    # 단독 "미완" 키워드도 제거
    text = re.sub(r'\b미완\b', '', text, flags=re.IGNORECASE)
    
    # (진짜완결) → 완결
    text = re.sub(r'\(\s*진짜\s*(완결|완|Complete)\s*\)', r'\1', text, flags=re.IGNORECASE)
    
    # 작가의 말 → 후기
    text = re.sub(r'작가의\s*말', '후기', text, flags=re.IGNORECASE)
    
    # 불필요한 키워드 제거
    # 주의: "본편 N-M 完 외전 N" 패턴은 보호 (extract_complete_and_extras에서 처리)
    # "본편 1-872 完 외전 120" 같은 패턴이 있으면 "본편"을 제거하지 않음
    # 주의: "외전포함", "번외포함"은 보호
    if not re.search(r'본편\s+\d{1,4}\s*-\s*\d{1,4}\s*(完|완|Complete)\s+(외전|外)\s+\d{1,4}', text, re.IGNORECASE):
        text = re.sub(r'\b본편\b', '', text)
        # "외전포함", "번외포함"이 아닌 경우만 "포함" 제거
        text = re.sub(r'(?<!외전)(?<!번외)(본편|및|포함)', '', text)
        text = re.sub(r'(?<!외전)(?<!번외)(본편|및|포함)\s*(\d{1,4})', r'\2', text)
        text = re.sub(r'(\d{1,4})\s*(?<!외전)(?<!번외)(본편|및|포함)', r'\1', text)
        text = re.sub(r'본편(?=\d)', '', text)
    
    # "및" 키워드는 항상 제거
    text = re.sub(r'\b및\b', '', text)
    
    # "번외포함N시즌" 패턴 처리 (예: "번외포함1시즌" → "시즌1 번외")
    # 이 패턴을 먼저 처리해야 시즌과 번외가 올바르게 분리됨
    # 주의: 외전 표기 통일보다 먼저 처리해야 함
    m = re.search(r'번외포함(\d{1,2})시즌', text)
    if m:
        season_num = m.group(1)
        # "시즌N 번외"로 변환
        text = text[:m.start()] + f'시즌{season_num} 번외' + text[m.end():]
    
    # 외전 표기 통일 (오타 포함)
    # 번외편 → 번외 (먼저 처리)
    text = re.sub(r'\b번외편\b', '번외', text)
    # 외포, 왼전 → 외전 (번외는 그대로 유지)
    text = re.sub(r'\b(외포|왼전)\b', '외전', text)
    # 후기포 → 후기
    text = re.sub(r'\b후기포\b', '후기', text)
    
    # "특별" 키워드 제거 (외전이 있으면 중복)
    text = re.sub(r'\b특별\s*(?=외전)', '', text)
    text = re.sub(r'(?<=외전)\s*특별\b', '', text)
    
    return normalize_unicode_spaces(text)


def remove_author_info(text: str) -> str:
    """
    저자명 및 업로더 정보 제거
    
    제거 대상:
        - @닉네임 (예: @아말하, @koi, @김갈비뼈)
        - ⓒ닉네임
        - 특정 키워드 (K, 국뽕, 시계열 등)
        - 저자명 패턴 (고유성, 김수지 등)
        - 중복 대괄호 내용
        - 날짜 패턴 (25.4.29, 2024.01.01 등)
        - 업로더 표시 (E역전, E번역 등)
    
    Args:
        text: 정리할 텍스트
        
    Returns:
        저자 정보가 제거된 텍스트
    """
    # 업로더 표시 제거 (E역전, E번역, E수정 등)
    # 패턴: 공백 + E + 한글 (예: " E역전", " E번역")
    text = re.sub(r'\s+E[가-힣]+', '', text)
    
    # @닉네임, ⓒ닉네임 완전 제거 (닉네임 자체도 제거)
    # @작가 이름 패턴도 처리 (예: @작가 시준 → 제거)
    text = re.sub(r'@작가\s+[가-힣]+', '', text)
    text = re.sub(r'@[^\s@]+', '', text)
    # ⓒ 닉네임 제거 (공백 있거나 없거나 모두 처리)
    # 예: "ⓒ주도민", "ⓒ 주도민"
    text = re.sub(r'ⓒ\s*[^\s]+', '', text)
    
    # 빈 대괄호 + 닉네임 패턴 제거 (예: "[]모루우", "[] 모루우")
    # 빈 대괄호 뒤에 공백 있거나 없거나 모두 처리
    text = re.sub(r'\[\]\s*[가-힣a-zA-Z0-9]+', '', text)
    
    # 完/완 뒤에 붙은 단일 알파벳 제거 (예: "完K", "완K") - 먼저 처리
    text = re.sub(r'(完|완|완결|Complete)\s*([A-Z])\b', r'\1', text, flags=re.IGNORECASE)
    
    # 흔히 남는 단일 키워드 제거
    # 택본/텍본: 텍스트 파일을 의미하는 업로더 표시
    text = re.sub(r'\s*\b(K|국뽕|시계열|선우선사|한중월야|보리네집사|택본|텍본)\b\s*', ' ', text, flags=re.IGNORECASE)
    
    # 날짜 패턴 제거 (예: 25.4.29, 2024.01.01, 24-12-31, .121120)
    text = re.sub(r'\b\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2}\b', '', text)
    text = re.sub(r'\.\d{6}\b', '', text)  # .121120 형태
    
    # 한글 이름 패턴 제거 (2-3글자 한글, 완결 표시 뒤에 오는 경우)
    # 예: "完고유성", "完 김수지", "128完고유성"
    # 주의: "완벽한", "완미세계", "완전무결한" 같은 제목의 일부는 보호해야 함
    
    # 패턴 1: 숫자 + 完/완 + 한글 이름 (예: "128完고유성")
    # 주의: "후일담", "외전", "번외", "후기", "에필" 같은 키워드는 보호
    protected_keywords = r'(?!특외|외전|후기|에필|특별|후일담|추가외전|인랑전|귀환후일담|번외)'
    text = re.sub(rf'(\d{{1,4}})(完|완|완결|Complete)\s*{protected_keywords}([가-힣]{{2,3}})\b', r'\1\2', text, flags=re.IGNORECASE)
    
    # 패턴 2: 괄호 안 숫자 + 完/완 + 괄호 닫기 + 한글 이름 (예: "(271 완) 참도미", "(216 완) 오늘도요")
    # 주의: "후일담", "외전" 같은 키워드는 보호
    protected_keywords = r'(?!특외|외전|후기|에필|특별|후일담|추가외전|인랑전|귀환후일담|번외)'
    text = re.sub(rf'(完|완|완결|Complete)\s*\)\s*{protected_keywords}([가-힣]{{2,4}})\b', r'\1)', text, flags=re.IGNORECASE)
    
    # 패턴 3: 공백/특수문자 + 完/완결/Complete + 한글 이름
    # "완벽한", "완미세계" 같은 단어는 보호 (문장 시작이나 단어 시작은 제외)
    # 예: " 完 김수지" (O), "완벽한" (X - 문장 시작)
    # 주의: "특외", "외전" 같은 키워드는 보호
    # 주의: "- 한글이름" 형태는 저자명으로 제거 (예: "- 와룡생", "- 나한")
    # 보호할 키워드: 특외, 외전, 후기, 에필, 특별, 후일담, 추가외전, 인랑전, 귀환후일담
    protected_keywords = r'(?!특외|외전|후기|에필|특별|후일담|추가외전|인랑전|귀환후일담)'
    # 하이픈이 아닌 경우만 제거
    text = re.sub(rf'(?<!-\s)[\s\W](完|완결|Complete)\s*{protected_keywords}([가-힣]{{2,3}})\b', r' \1', text, flags=re.IGNORECASE)
    
    # 패턴 4: "- 한글이름" 형태의 저자명 제거 (완결 표시 뒤에 오는 경우)
    # 예: "(완) - 와룡생", "(완) - 나한"
    # 주의: 부제목이 아닌 저자명만 제거 (완결 표시 뒤에 오는 경우)
    text = re.sub(r'\(완\)\s*-\s*[가-힣]{2,4}\b', '(완)', text, flags=re.IGNORECASE)
    text = re.sub(r'(完|완결|Complete)\s*-\s*[가-힣]{2,4}\b', r'\1', text, flags=re.IGNORECASE)
    
    # 대괄호 내용 제리 (단, 개정판/완전판/수정판 등은 보존)
    # 장르 태그는 detect_category에서 이미 추출되었으므로 나머지는 제거
    # 보존할 패턴: [개정판], [완전판], [수정판], [개정], [완전], [수정]
    # 변환할 패턴: [완결] → 완결 (나중에 처리)
    # 제거할 패턴: [txt], [epub] 등
    # 주의: [외전 포함]은 이미 remove_basic_noise에서 "외전포함"으로 변환됨
    
    # [완결]을 " 완결 "로 변환 (나중에 extract_complete_and_extras에서 처리)
    # 공백을 추가하여 단어 경계 확보
    text = re.sub(r'\[완결\]', ' 완결 ', text, flags=re.IGNORECASE)
    
    # [완+외전] 패턴을 "완 외전"으로 변환 (대괄호 제거 전에 처리)
    text = re.sub(r'\[(완|完)\s*\+\s*(외전|外)\]', r'\1 \2', text, flags=re.IGNORECASE)
    
    # 먼저 보존할 패턴을 임시로 치환
    preserved = []
    def preserve_match(m):
        preserved.append(m.group(0))
        return f'__PRESERVED_{len(preserved)-1}__'
    
    # [완 외전] 패턴도 보존 (대괄호 포함)
    text = re.sub(r'\[(완|完)\s+(외전|外)\]', preserve_match, text, flags=re.IGNORECASE)
    text = re.sub(r'\[(개정판|완전판|수정판|개정|완전|수정)\]', preserve_match, text, flags=re.IGNORECASE)
    
    # 외전/에필/후기 관련 대괄호도 보존
    text = re.sub(r'\[(에필로그후기|외전후기|에필로그|에필|외전|후기)\]', preserve_match, text, flags=re.IGNORECASE)
    
    # 외전 범위 패턴도 보존 (예: [외전1-5화미완])
    text = re.sub(r'\[외전\d{1,4}-\d{1,4}화?미완?\]', preserve_match, text, flags=re.IGNORECASE)
    
    # 나머지 대괄호 제거 (저자명 포함)
    # 예: [카이첼], [류화수], [퓨전] 등
    text = re.sub(r'\[[^\]]*\]', ' ', text)
    
    # 보존한 패턴 복원
    for i, pattern in enumerate(preserved):
        # 개정판/완전판/수정판은 대괄호 포함하여 복원
        if re.match(r'\[(개정판|완전판|수정판|개정|완전|수정)\]', pattern, re.IGNORECASE):
            # 대괄호 포함하여 복원
            text = text.replace(f'__PRESERVED_{i}__', pattern)
        else:
            # 나머지는 대괄호 제거하고 내용만 복원
            content = pattern.strip('[]')
            text = text.replace(f'__PRESERVED_{i}__', content)
    
    return re.sub(r'\s+', ' ', text).strip()


def has_incomplete_flag(text: str) -> bool:
    """
    미완/연재중 플래그 감지
    
    이 플래그가 있으면 (완) 표시를 추가하지 않음
    
    주의: "본편 完, 외전 연재중" 같은 경우는 본편은 완결이므로 False 반환
    
    Args:
        text: 확인할 텍스트
        
    Returns:
        미완/연재중 플래그 존재 여부
    """
    # "외전 연재중", "외전 미완" 패턴은 무시 (본편은 완결)
    if re.search(r'(외전|外)\s*(연재\s*중|미완)', text, re.IGNORECASE):
        return False
    
    # "[외전N-M화미완]" 패턴도 무시 (본편은 완결)
    if re.search(r'\[외전\d+-\d+화?미완\]', text, re.IGNORECASE):
        return False
    
    return bool(re.search(r'(미완|연재중)', text, re.IGNORECASE))


# ============================================================================
# 완결 및 외전 정보 추출
# ============================================================================

def extract_complete_and_extras(text: str) -> Tuple[str, bool, Optional[str], List[str]]:
    """
    텍스트에서 완결 표시와 외전 정보를 추출
    
    완결 표시 인식 규칙 (v1.2.0):
        명확한 완결 표시만 인식:
        1. 공백으로 분리된 "완": " 완 ", " 완$", "^완 "
        2. 괄호/대괄호: "(완)", "[완]", "(완결)", "[완결]"
        3. 명시적 완결어: "완결", "完", "Complete"
        4. 범위 + 완: "1-100 완", "100 완"
        5. 접미사: "완텍", "완_1", "완@"
        
        보호 (완결 표시로 인식하지 않음):
        - 한글에 붙은 "완": "완벽", "완전", "완공", "완료", "구완공", "작업완료"
        - 하이픈 뒤 한글: "-완벽한"
    
    처리 패턴:
        완결 표시:
            - 完, 완, Complete → (완)
            - (50 완) → 1-50 (완)
            - 1-536화 [완] → 1-536 (완)
            - 종족초월1-345完 → 종족초월 1-345 (완)
            - 完@닉네임 → (완), 닉네임 제거
        
        외전 정보:
            - 完+外 → (완) + 외전
            - 完+外 1-3 → (완) + 외전 1-3
            - 完 17 外전 → (완) + 외전 17
            - 1432 외전 完 → 1-1432 (완) + 외전 (v1.1.0 수정)
            - 1-473 외전1-86 完 → 1-473 (완) + 외전 1-86
        
        부 정보:
            - (1, 2부 完) → 1-2부 (완)
        
        에필로그 정보:
            - 1-209 完+ 에필로그 1-3完 → 1-209 (완) + 에필 1-3
    
    버그 수정 (v1.1.0):
        "숫자 외전 完" 패턴에서 숫자를 본편 범위로 올바르게 추출
        예: "전구고무1432 외전 完" → "전구고무 1-1432 (완) + 외전"
    
    Args:
        text: 처리할 텍스트
        
    Returns:
        (남은 텍스트, 완결 여부, 범위 정보, 외전 목록) 튜플
        예: ("제목", True, "1-100", ["외전 1-5"])
    """
    has_complete = False
    range_info: Optional[str] = None
    extras: List[str] = []
    
    # ========== 전처리: 제목의 일부인 "완" 보호 ==========
    # "완벽", "완전", "완공", "완료", "구완공", "작업완료", "-완벽한" 등의 "완"은 보호
    # 방법: 한글에 붙어있는 "완"을 임시로 치환
    
    # 패턴 1: 한글-완-한글 (예: 구완공, 작업완료)
    text = re.sub(r'([가-힣])완([가-힣])', r'\1__WAN_PROTECTED__\2', text)
    
    # 패턴 2: 하이픈-완-한글 (예: -완벽한)
    text = re.sub(r'(-)완([가-힣])', r'\1__WAN_PROTECTED__\2', text)
    
    # (N 완) 패턴 처리는 나중에 (우선순위 0에서 처리하거나 별도 로직에서 처리)
    # 여기서 괄호를 제거하면 범위 추출 로직이 작동하지 않음
    
    # [외전 포함] 패턴 처리 (이미 "외전포함"으로 변환됨)
    if re.search(r'외전포함', text, re.IGNORECASE):
        if not any('외전' in e for e in extras):
            extras.append('외전')
        text = re.sub(r'외전포함', '', text, flags=re.IGNORECASE)

    patterns = {
        'has_complete_paren': '(완)' in text,
        'has_existing_range': bool(re.search(r'\b\d{1,4}\s*-\s*\d{1,4}(?!\s*부)(?!-\d)\b', text)),
        'has_bu_pattern': bool(re.search(r'\d{1,4}(?:-\d{1,4})?\s*부', text)),
        'has_season_pattern': bool(re.search(r'시즌\s*\d{1,4}(?:-\d{1,4})?', text))
    }

    # ========== 우선순위 -1: 특수 괄호 패턴 (최우선) ==========
    
    # 패턴 1: (N부 미완) → N부 유지, 미완 플래그는 has_incomplete_flag에서 처리
    # 예: "절대 마법사(2부 미완) 532-562" → "절대 마법사 2부 532-562"
    m = re.search(r'\(\s*(\d{1,4})\s*부\s*미완\s*\)', text, re.IGNORECASE)
    if m:
        bu_info = f'{m.group(1)}부'
        # 괄호와 미완을 제거하고 부 정보만 남김
        text = text[:m.start()] + ' ' + bu_info + ' ' + text[m.end():]
    
    # 패턴 2: (N부 완결, 외전연재) → N부 (완) + 외전
    # 예: "척준경이 달라졌어요 001-205 (1부 완결, 외전연재)" → "척준경이 달라졌어요 1부 1-205 (완) + 외전"
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*\(\s*(\d{1,4})\s*부\s*(완결|완|Complete)\s*,\s*외전\s*연재\s*\)', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        bu_info = f'{m.group(3)}부'
        if not any('외전' in e for e in extras):
            extras.append('외전')
        # 범위와 괄호 제거, 부 정보만 남김
        text = text[:m.start()] + ' ' + bu_info + ' ' + text[m.end():]

    # ========== 우선순위 0: (완) 앞의 범위 추출 (최우선) ==========
    # 이미 (완) 괄호가 있으면 우선 유지
    # 앞에 범위가 있으면 추출 (예: 001-427 (완), 1-201 1부 (완), 001-199 에필로그 (완), 1-339 (완) 外)
    # 주의: has_existing_range 조건과 무관하게 처리 (우선순위 높음)
    if patterns['has_complete_paren'] and not range_info:
        has_complete = True
        # (완) 앞에 범위 + 부 정보가 있는지 확인 (예: 1-201 1부 (완))
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(\d{1,4}부)\s*\(완\)', text, re.IGNORECASE)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            bu_info = m.group(3)
            # 범위와 (완)을 제거하고 부 정보만 남김
            text = text[:m.start()] + ' ' + bu_info + ' ' + text[m.end():]
        else:
            # (완) 앞에 범위 + 에필로그/외전이 있는지 확인 (예: 001-199 에필로그 (완))
            m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(에필로그|에필|외전|外)\s*\(완\)', text, re.IGNORECASE)
            if m:
                range_info = f'{int(m.group(1))}-{int(m.group(2))}'
                extra_label = '에필' if m.group(3) in ['에필로그', '에필'] else '외전'
                if extra_label not in extras:
                    extras.append(extra_label)
                # 범위와 에필로그/외전과 (완)을 모두 제거
                text = text[:m.start()] + text[m.end():]
            else:
                # (완) 뒤에 외전/에필 범위가 있는지 확인 (예: 1-365 (완) 에필로그 1-2)
                m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*\(완\)\s+(外|외전|에필로그|에필)\s+(\d{1,4})\s*-\s*(\d{1,4})', text, re.IGNORECASE)
                if m:
                    range_info = f'{int(m.group(1))}-{int(m.group(2))}'
                    extra_label = '에필' if m.group(3) in ['에필로그', '에필'] else '외전'
                    extra_range = f'{int(m.group(4))}-{int(m.group(5))}'
                    extras.append(f'{extra_label} {extra_range}')
                    # 범위와 (완)과 외전/에필 범위를 모두 제거
                    text = text[:m.start()] + text[m.end():]
                else:
                    # (완) 뒤에 외전/에필이 있는지 확인 (예: 1-339 (완) 外, 1-339 (완) 외전)
                    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*\(완\)\s+(外|외전|에필로그|에필)\b', text, re.IGNORECASE)
                    if m:
                        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
                        extra_label = '에필' if m.group(3) in ['에필로그', '에필'] else '외전'
                        if extra_label not in extras:
                            extras.append(extra_label)
                        # 범위와 (완)과 외전/에필을 모두 제거
                        text = text[:m.start()] + text[m.end():]
                    else:
                        # (완) 앞에 단일 숫자가 있는지 확인 (예: 00136 (완), 500 (완))
                        # 주의: 앞에 0이 있어도 (완) 앞의 숫자는 범위로 간주
                        # 주의: 외전/에필 범위가 아닌지 확인 (예: "完 외전 1-3 (완)"에서 "1-3"은 외전 범위)
                        # 주의: 범위 패턴 (N-M)의 일부가 아닌지 확인
                        # 주의: 제목 시작 부분의 연도는 제외 (예: "1874 대혁명 (완)" - 숫자 뒤에 한글)
                        # 주의: 천 단위 구분 쉼표가 있는 숫자는 제외 (예: "163,417,413번째 (완)")
                        m = re.search(r'(\d{1,6})\s*\(완\)', text, re.IGNORECASE)
                        if m:
                            # 숫자 앞에 하이픈이 있는지 확인 (범위의 일부인지)
                            before_num = text[:m.start()]
                            # 하이픈이 바로 앞에 있으면 범위의 일부이므로 제외
                            if re.search(r'-\s*$', before_num):
                                pass  # 범위의 일부이므로 처리하지 않음
                            # 외전/에필 키워드가 바로 앞에 있으면 이것은 외전 범위임
                            elif re.search(r'(외전|外|에필로그|에필|完|완|Complete)\s*$', before_num, re.IGNORECASE):
                                pass  # 외전 범위이므로 처리하지 않음
                            # 제목 시작 부분의 연도인지 확인 (앞에 한글이 없으면 제목의 일부)
                            elif not re.search(r'[가-힣a-zA-Z]', before_num):
                                pass  # 제목 시작 부분의 연도이므로 처리하지 않음
                            # 천 단위 구분 쉼표가 있는지 확인 (예: "163,417,413번째")
                            elif re.search(r',\d+$', before_num):
                                pass  # 천 단위 구분 숫자의 일부이므로 처리하지 않음
                            # 숫자와 (완) 사이에 한글이 있는지 확인 (예: "1874 대혁명 (완)" - 연도)
                            else:
                                # 전체 텍스트에서 숫자 끝부터 괄호 시작까지 추출
                                num_part = m.group(1)     # 예: "1874"
                                num_end_pos = m.start() + len(num_part)
                                paren_start_pos = text.find('(', num_end_pos, m.end())
                                if paren_start_pos > num_end_pos:
                                    between_text = text[num_end_pos:paren_start_pos]
                                    if re.search(r'[가-힣]', between_text):
                                        pass  # 숫자와 (완) 사이에 한글이 있으면 연도이므로 처리하지 않음
                                    else:
                                        # 정상적인 단일 숫자 (앞의 0 제거하여 범위로 변환)
                                        range_info = f'1-{int(m.group(1))}'
                                        text = text[:m.start()] + text[m.end():]
                                else:
                                    # 정상적인 단일 숫자 (앞의 0 제거하여 범위로 변환)
                                    range_info = f'1-{int(m.group(1))}'
                                    text = text[:m.start()] + text[m.end():]
                        else:
                            # (완) 앞에 범위만 있는지 확인 (예: 001-427 (완), 001-265 (완))
                            # 주의: 외전/에필 범위가 아닌지 확인 (예: "完 외전 1-3 (완)"에서 "1-3"은 외전 범위)
                            m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*\(완\)', text, re.IGNORECASE)
                            if m:
                                # 범위 앞에 "외전", "外", "에필", "에필로그", "完", "완" 등이 있는지 확인
                                before_range = text[:m.start()]
                                # 외전/에필 키워드가 바로 앞에 있으면 이것은 외전 범위임
                                if re.search(r'(외전|外|에필로그|에필|完|완|Complete)\s*$', before_range, re.IGNORECASE):
                                    # 외전 범위이므로 메인 범위로 추출하지 않음
                                    # 대신 외전 정보로 추가
                                    extra_range = f'{int(m.group(1))}-{int(m.group(2))}'
                                    # 외전인지 에필인지 확인
                                    extra_keyword_match = re.search(r'(외전|外|에필로그|에필)\s*$', before_range, re.IGNORECASE)
                                    if extra_keyword_match:
                                        extra_label = '에필' if extra_keyword_match.group(1) in ['에필로그', '에필'] else '외전'
                                        extras.append(f'{extra_label} {extra_range}')
                                    else:
                                        # 完/완만 있으면 외전으로 간주
                                        extras.append(f'외전 {extra_range}')
                                    # 외전 키워드부터 (완)까지 제거
                                    text = re.sub(r'(외전|外|에필로그|에필|完|완|Complete)\s*\d{1,4}\s*-\s*\d{1,4}\s*\(완\)', '', text, count=1, flags=re.IGNORECASE)
                                else:
                                    # 정상적인 메인 범위
                                    range_info = f'{int(m.group(1))}-{int(m.group(2))}'
                                    text = text[:m.start()] + text[m.end():]

    # ========== 우선순위 1: 범위가 2개 있는 복합 패턴 (본편 + 외전/에필) ==========
    
    # 패턴 -3: "N 완 외전 M 완" (예: "500 완 외전 100 완", "194 완, 외전 6 완")
    # 첫 번째가 본편, 두 번째가 외전
    # 쉼표가 있을 수도 있음
    m = re.search(r'(\d{1,4})\s+(완|完|완결|Complete)\s*,?\s+(외전|外)\s+(\d{1,4})\s+(완|完|완결|Complete)', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'1-{int(m.group(1))}'
        extras.append(f'외전 {int(m.group(4))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 -3: "시즌N N-M 完 시즌M N-M 完" (예: "시즌1 1-100 完 시즌2 1-50 完")
    # 양쪽 모두 완결, (완) 중복 허용
    m = re.search(r'시즌(\d{1,4})\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+시즌(\d{1,4})\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(2))}-{int(m.group(3))}'
        season1_info = f'시즌{m.group(1)}'
        season2_range = f'{int(m.group(6))}-{int(m.group(7))}'
        extras.append(f'시즌{m.group(5)} {season2_range} (완)')
        # 제목에 시즌1 정보 추가
        text = text[:m.start()] + f' {season1_info} ' + text[m.end():]
    
    # 패턴 -2.5: "시즌N N-M 完 시즌M N-M" (예: "시즌1 1-100 完 시즌2 1-50")
    # 시즌1 완결, 시즌2 연재중
    m = re.search(r'시즌(\d{1,4})\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+시즌(\d{1,4})\s+(\d{1,4})\s*-\s*(\d{1,4})(?!\s*(完|완|Complete))', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(2))}-{int(m.group(3))}'
        season1_info = f'시즌{m.group(1)}'
        season2_range = f'{int(m.group(6))}-{int(m.group(7))}'
        extras.append(f'시즌{m.group(5)} {season2_range}')
        # 제목에 시즌1 정보 추가
        text = text[:m.start()] + f' {season1_info} ' + text[m.end():]
    
    # 패턴 -2.3: "N-M 完 N부 N-M 完" (예: "1-203 完 2부 1-5 完")
    # 1부 생략, 양쪽 모두 완결, (완) 중복 허용
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(\d{1,4})부\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        part1_info = '1부'
        part2_range = f'{int(m.group(5))}-{int(m.group(6))}'
        extras.append(f'{m.group(4)}부 {part2_range} (완)')
        # 제목에 1부 정보 추가
        text = text[:m.start()] + f' {part1_info} ' + text[m.end():]
    
    # 패턴 -2.2: "N-M 完 N부 N-M" (예: "1-203 完 2부 1-5")
    # 1부 생략, 1부 완결, 2부 연재중
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(\d{1,4})부\s+(\d{1,4})\s*-\s*(\d{1,4})(?!\s*(完|완|Complete))', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        part1_info = '1부'
        part2_range = f'{int(m.group(5))}-{int(m.group(6))}'
        extras.append(f'{m.group(4)}부 {part2_range}')
        # 제목에 1부 정보 추가
        text = text[:m.start()] + f' {part1_info} ' + text[m.end():]
    
    # 패턴 -2: "N-M N부 完 N-M N부" (예: "1-259 1부 完 1-68 2부")
    # 첫 번째 부는 완결, 두 번째 부는 extras로 처리
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(\d{1,4})부\s*(完|완|Complete)\s+(\d{1,4})\s*-\s*(\d{1,4})\s+(\d{1,4})부', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        part_info = f'{m.group(3)}부'
        extras.append(f'{m.group(7)}부 {int(m.group(5))}-{int(m.group(6))}')
        # 제목에 부 정보 추가
        text = text[:m.start()] + f' {part_info} ' + text[m.end():]
    
    # 패턴 -1: "본편 N-M 完 외전 N" (예: "본편 1-872 完 외전 120")
    # 가장 먼저 처리해야 다른 패턴에 의해 분리되지 않음
    m = re.search(r'본편\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(외전|外)\s+(\d{1,4})\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extras.append(f'외전 {m.group(5)}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 0: N-M 完 외전N-M 完 (예: 1-838 完 외전1-45 完)
    # 두 개의 完이 있는 경우, 첫 번째가 본편, 두 번째가 외전
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(외전|外|에필로그|에필)(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extra_label = '에필' if m.group(4) in ['에필로그', '에필'] else '외전'
        extras.append(f'{extra_label} {int(m.group(5))}-{int(m.group(6))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 0: N-M 외전 N-M 完 (예: 1-771 외전 1-2 完)
    # 공백이 있는 경우 - 첫 번째 범위가 본편, 두 번째 범위가 외전
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(외전|外|에필로그|에필)\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extra_label = '에필' if m.group(3) in ['에필로그', '에필'] else '외전'
        extras.append(f'{extra_label} {int(m.group(4))}-{int(m.group(5))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 1: N-M 외전N-M 完 (예: 1-473 외전1-86 完)
    # 공백이 없는 경우 - 첫 번째 범위가 본편, 두 번째 범위가 외전
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(외전|外|에필로그|에필)(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extra_label = '에필' if m.group(3) in ['에필로그', '에필'] else '외전'
        extras.append(f'{extra_label} {int(m.group(4))}-{int(m.group(5))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 2: N-M 完+ 에필로그 N-M完 (예: 1-209 完+ 에필로그 1-3完)
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s*\+?\s*(에필로그|에필|외전|外)\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)?\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extra_label = '에필' if m.group(4) in ['에필로그', '에필'] else '외전'
        extras.append(f'{extra_label} {int(m.group(5))}-{int(m.group(6))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 3: N-M 完 外 N-M (예: 1-555 完 에필로그 1-3)
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(에필로그|에필|외전|外)\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)?\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extra_label = '에필' if m.group(4) in ['에필로그', '에필'] else '외전'
        extras.append(f'{extra_label} {int(m.group(5))}-{int(m.group(6))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 4: N-M 화 外 完 (예: 1-154화 外 完)
    # 外/외전이 완결 표시 앞에 있는 경우
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(화|편|회|권)?\s+(外|외전|에필로그|에필)\s+(完|완|Complete)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extra_label = '에필' if m.group(4) in ['에필로그', '에필'] else '외전'
        if extra_label not in extras:
            extras.append(extra_label)
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 5: "N부 (M 완) N부 (M 완) ..." (예: "1부 (3 완) 2부 (4 완)", "1부 (10 완) 2부 (20 완) 3부 (30 완)")
    # 각 부의 범위가 괄호 안에 있는 경우
    # 모든 부를 찾아서 처리
    bu_pattern = r'(\d{1,4})부\s*\(\s*(\d{1,4})\s+(완|完|완결|Complete)\s*\)'
    bu_matches = list(re.finditer(bu_pattern, text, re.IGNORECASE))
    
    if len(bu_matches) >= 2:
        # 2개 이상의 부가 있는 경우
        has_complete = True
        bu_parts = []
        
        for i, m in enumerate(bu_matches):
            bu_num = m.group(1)
            range_num = f'1-{int(m.group(2))}'
            bu_parts.append((bu_num, range_num, m.start(), m.end()))
        
        # 첫 번째 부를 메인 범위로 설정
        range_info = bu_parts[0][1]
        
        # 나머지 부들을 extras에 추가
        for i in range(1, len(bu_parts)):
            bu_num, range_num, _, _ = bu_parts[i]
            extras.append(f'{bu_num}부 {range_num} (완)')
        
        # 텍스트에서 모든 부 패턴 제거하고 첫 번째 부만 남김
        # 역순으로 제거 (인덱스 변경 방지)
        for i in range(len(bu_parts) - 1, -1, -1):
            _, _, start, end = bu_parts[i]
            if i == 0:
                # 첫 번째 부는 "N부"만 남김
                text = text[:start] + f' {bu_parts[0][0]}부 ' + text[end:]
            else:
                # 나머지 부는 제거
                text = text[:start] + ' ' + text[end:]
    
    # 패턴 6: "N-M N부 完 N-M N부 연재중" (예: "1-259 1부 完 1-68 2부 연재중")
    # 첫 번째 범위가 1부, 두 번째 범위가 2부
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(\d{1,4})부\s+(完|완|Complete)\s+(\d{1,4})\s*-\s*(\d{1,4})\s+(\d{1,4})부\s+연재\s*중', text, re.IGNORECASE)
    if m:
        # 1부는 완결, 2부는 연재중
        bu1 = f'{m.group(3)}부'
        range1 = f'{int(m.group(1))}-{int(m.group(2))}'
        bu2 = f'{m.group(7)}부'
        range2 = f'{int(m.group(5))}-{int(m.group(6))}'
        
        has_complete = True
        range_info = range1
        extras.append(f'{bu2} {range2}')
        text = text[:m.start()] + f' {bu1} ' + text[m.end():]
        # "연재중" 플래그 제거 (이미 처리됨)
        text = re.sub(r'\s*연재\s*중\s*', '', text, flags=re.IGNORECASE)
    
    # 새 패턴: N 외전 完 (N은 본편 범위, 외전 아님)
    # 예시: "전구고무1432 외전 完" → range=1-1432, extras=[외전], complete=True
    # 제목과 숫자 사이에 공백이 없는 경우도 처리
    m = re.search(r'(\d{1,5})\s+(외전|外)\s+(完|완|Complete)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'1-{int(m.group(1))}'
        if '외전' not in [e for e in extras if '외전' in e]:
            extras.append('외전')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 完+外 N-M 패턴 (예: 完+外 1-3, (완)+外 1-5)
    m = re.search(r'(\(완\)|完|완|Complete)\s*\+?\s*(外|외전|외포|외)\s+(\d{1,4})\s*-\s*(\d{1,4})', text, re.IGNORECASE)
    if m:
        has_complete = True
        extras.append(f'외전 {int(m.group(3))}-{int(m.group(4))}')
        text = text[:m.start()] + ' ' + text[m.end():]

    # 完+外, 完 외전, 完 外, 完외포, (완)+外 등의 조합
    # 괄호 안의 완결 표시도 처리
    # 주의: 뒤에 숫자가 있는 경우는 제외 (예: "完 외전 3"은 아래 패턴에서 처리)
    if re.search(r'(\(완\)|完|완|Complete)\s*\+?\s*(外|외전|외포|외)\b(?!\s*\d)', text, re.IGNORECASE):
        has_complete = True
        if not any('외전' in e for e in extras):
            extras.append('외전')
        text = re.sub(r'(\(완\)|完|완|Complete)\s*\+?\s*(外|외전|외포|외)\b(?!\s*\d)', '', text, flags=re.IGNORECASE)

    # N 完 N-N 외전 패턴 (예: 1213 完 1-93 외전)
    # 첫 번째 N이 범위 끝, N-N이 외전 범위
    m = re.search(r'(\d{1,4})\s+(完|완|Complete)\s+(\d{1,4})\s*-\s*(\d{1,4})\s*(外|외전)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'1-{int(m.group(1))}'
        extras.append(f'외전 {m.group(3)}-{m.group(4)}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 完 N 外전 같은 패턴 (예: 完 120 외전)
    # 주의: N은 외전 범위이지 본편 범위가 아님
    m = re.search(r'(完|완|Complete)\s+(\d{1,4})\s*(外|외전)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        extras.append(f'외전 {m.group(2)}')
        text = re.sub(r'(完|완|Complete)\s+\d{1,4}\s*(外|외전)\b', '', text, flags=re.IGNORECASE)
    

    # N-M 完 외전 N-M (완) 패턴 (예: 1-305 完 외전 1-25 (완))
    # 첫 번째 범위가 본편, 두 번째 범위가 외전
    # 외전의 (완)은 제거
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(외전|外)\s+(\d{1,4})\s*-\s*(\d{1,4})\s*\(완\)', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extras.append(f'외전 {int(m.group(5))}-{int(m.group(6))}')
        text = text[:m.start()] + ' ' + text[m.end():]
    else:
        # N-M 完 외전 N-M 패턴 (예: 1-272 完 외전 1-3)
        # 첫 번째 범위가 본편, 두 번째 범위가 외전
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(외전|外)\s+(\d{1,4})\s*-\s*(\d{1,4})\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            extras.append(f'외전 {int(m.group(5))}-{int(m.group(6))}')
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # N-M 完 외전 N 패턴 (예: 1-872 完 외전 120)
    # 첫 번째 범위가 본편, 두 번째 숫자가 외전
    # 이 패턴을 먼저 처리해야 "외전 120"이 제목에 붙지 않음
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|Complete)\s+(외전|外)\s+(\d{1,4})\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extras.append(f'외전 {m.group(5)}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # N-M화 외전 N 完 패턴 (예: 1-940화 외전 15 完)
    # 첫 번째 범위가 본편, 두 번째 숫자가 외전
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(화|편|회|권)?\s+(외전|外)\s+(\d{1,4})\s*(完|완|Complete)\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        extras.append(f'외전 {m.group(5)}')
        text = text[:m.start()] + ' ' + text[m.end():]

    # -N(M부 완...) 패턴 (예: -94(1부 완.121120)) - 먼저 처리
    # -N을 1-N으로 변환하고 M부를 추출
    # 괄호 안의 모든 내용을 제거 (날짜 등 포함)
    m = re.search(r'-(\d{1,4})\s*\(\s*(\d{1,4})\s*부\s*(완결?|Complete|완|完)[^)]*\)', text, re.IGNORECASE)
    if m:
        has_complete = True
        range_info = f'1-{int(m.group(1))}'
        bu_text = f'{m.group(2)}부'
        # 매칭된 전체를 부 정보로 교체
        text = text[:m.start()] + ' ' + bu_text + ' ' + text[m.end():]
    
    # 괄호 안의 부 + 완 + 외전 패턴 (예: (1-2부 완, 외전))
    m = re.search(r'\(\s*(\d{1,4})\s*-\s*(\d{1,4})\s*부\s*(완결?|Complete|완|完)\s*,\s*(외전|外)\s*\)', text, re.IGNORECASE)
    if m:
        has_complete = True
        bu_text = f'{m.group(1)}-{m.group(2)}부'
        if '외전' not in extras:
            extras.append('외전')
        text = text[:m.start()] + ' ' + bu_text + ' ' + text[m.end():]
    
    # 괄호 안의 단일 부 + 완 패턴 (예: (1부완), (2부 완))
    # 공백 있거나 없거나 모두 처리
    m = re.search(r'\(\s*(\d{1,4})\s*부\s*(완결?|Complete|완|完)\s*\)', text, re.IGNORECASE)
    if m:
        has_complete = True
        bu_text = f'{m.group(1)}부'
        # 괄호 제거하고 부 정보만 남김 (공백 추가)
        text = text[:m.start()] + ' ' + bu_text + ' ' + text[m.end():]
    
    # 괄호 안의 부 범위 + 완 패턴 (예: (1, 2부 完), (1-2부 完))
    m = re.search(r'\(\s*(\d{1,4})\s*[,~-]\s*(\d{1,4})\s*부\s*(완결?|Complete|완|完)\s*\)', text, re.IGNORECASE)
    if m:
        has_complete = True
        # "1, 2부" 또는 "1-2부" 형태를 제목 뒤에 남김
        bu_text = f'{m.group(1)}-{m.group(2)}부'
        text = text[:m.start()] + ' ' + bu_text + ' ' + text[m.end():]
    
    # N-M부 + 完 패턴 (예: "1-2부 완") - 먼저 처리
    # 부 범위가 있는 경우
    m = re.search(r'(\d{1,4}-\d{1,4}부)\s*(完|완|완결|Complete)(\s*\(([^)]*)\))?\b', text, re.IGNORECASE)
    if m:
        has_complete = True
        bu_text = m.group(1)
        # 부 정보는 제목에 남기고 完과 괄호 제거
        text = text[:m.start()] + ' ' + bu_text + ' ' + text[m.end():]
    else:
        # 단독 부 + 完 패턴 (예: "2부 完", "3부完(연재중)")
        # 연재중이어도 해당 부는 완결로 처리 (3부 완결, 4부 연재중 같은 경우)
        # 주의: N-M부 형태는 위에서 처리했으므로 여기서는 단일 숫자만
        m = re.search(r'(?<!-\d)(?<!-\d\d)(?<!-\d\d\d)(?<!-\d\d\d\d)(\d{1,4}부)\s*(完|완|완결|Complete)(\s*\(([^)]*)\))?\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            bu_text = m.group(1)
            # 부 정보는 제목에 남기고 完과 괄호 제거
            text = text[:m.start()] + ' ' + bu_text + ' ' + text[m.end():]

    # (N 완) 패턴 -> 범위 추출 (기존 범위가 없을 때)
    # 주의: 제목 시작 부분의 연도는 제외 (예: "1874 대혁명 (완)" - 숫자 뒤에 한글)
    # 주의: 천 단위 구분 쉼표가 있는 숫자는 제외 (예: "163,417,413번째 (완)")
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'\(\s*(\d{1,4})\s*(완결?|Complete|완|完)\s*\)', text, re.IGNORECASE)
        if m:
            # 숫자 앞의 텍스트 확인
            before_num = text[:m.start()]
            
            # 제목 시작 부분의 연도인지 확인 (앞에 한글이 없으면 제목의 일부)
            has_title_before = bool(re.search(r'[가-힣a-zA-Z]', before_num))
            
            # 천 단위 구분 쉼표가 있는지 확인 (예: "163,417,413번째")
            has_comma_before = bool(re.search(r',\d+$', before_num))
            
            # 괄호 앞 숫자 뒤에 한글이 있는지 확인 (예: "1874 대혁명 (완)")
            # 패턴: 숫자 + 공백 + 한글
            has_korean_after_num = bool(re.search(r'^\d+\s+[가-힣]', text[m.start():]))
            
            # 제목이 앞에 있고, 천 단위 구분 쉼표가 없고, 숫자 뒤에 한글이 없으면 범위로 간주
            if has_title_before and not has_comma_before and not has_korean_after_num:
                has_complete = True
                range_info = f'1-{int(m.group(1))}'
                text = text[:m.start()] + ' ' + text[m.end():]

    # 숫자-숫자 完K 패턴 (예: 1-192 完K) - 범위가 있어도 처리
    # 이 패턴은 범위 뒤에 完K가 붙은 경우이므로 우선 처리
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(完|완|완결|Complete)\s*([A-Z])\b', text, re.IGNORECASE)
    if m and not range_info:
        has_complete = True
        range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 숫자-숫자화 完 N 패턴 (예: 1-318화 완결 2) - 가장 먼저 처리
    # 주의: preprocess_symbols에서 _가 공백으로 변환되므로 "완결_2" → "완결 2"
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(화|편|회|권)\s*(完|완|완결|Complete)(?:\s+\d+|텍)?\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 숫자-숫자화 完 패턴 (예: 1-225화 完, 1-250화 완_1)
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(화|편|회|권)\s*(完|완|완결|Complete)(?:텍|_\d+)?\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            text = text[:m.start()] + ' ' + text[m.end():]

    # 숫자-숫자화 [완] 패턴 (예: 1-536화 [완])
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(화|편|회|권)?\s*\[완\]', text)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            text = text[:m.start()] + ' ' + text[m.end():]

    # 숫자 [완] 패턴
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,4})\s*(화|편|회|권)?\s*\[완\]', text)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            text = text[:m.start()] + ' ' + text[m.end():]

    # 숫자-숫자-완외전 패턴 (예: 1-271-완외전) - 먼저 처리
    # 하이픈이 2개 있고 외전이 붙어있는 경우
    if not range_info:
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*-\s*(완결?|Complete|완|完)(외전|外)', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            if '외전' not in extras:
                extras.append('외전')
            # 매칭된 전체를 제거
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 숫자-숫자-완결 패턴 (예: 001-241-완결) - 먼저 처리
    # 하이픈이 2개 있는 경우 (has_existing_range 조건 제거)
    if not range_info:
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*-\s*(완결?|Complete|완|完)', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            # 매칭된 전체를 제거
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 숫자-숫자 完 패턴 (예: 1-345完, 1-200 完, 001-178완결, 1-392 완 pioren) - 제목끝숫자 패턴보다 먼저 처리
    # 주의: has_existing_range 조건과 무관하게 처리 (완 표시가 있으면 범위 추출)
    if not range_info:
        # 완결 뒤에 괄호나 공백이 올 수 있음 (예: 001-178완결(외전포함), 1-392 완 pioren)
        m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(완결?|Complete|완|完)', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            # 매칭된 전체를 제거
            text = text[:m.start()] + text[m.end():]

    # -N 完 패턴
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'-(\d{1,4})\s*(완결?|Complete|완|完)\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            text = text[:m.start()] + ' ' + text[m.end():]

    # 제목끝숫자-숫자 完 패턴 (예: 천재가됨1-536완, 칸푸1023完)
    # 최대 6자리 숫자 지원
    if not range_info:
        title_range_pattern = r'([가-힣A-Za-z]+)(\d{1,6})\s*-\s*(\d{1,6})\s*(화|편|회|권)?\s*(완결?|Complete|완|完)\b'
        m = re.search(title_range_pattern, text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'{m.group(2)}-{m.group(3)}'
            text = text[:m.start()] + m.group(1) + ' ' + text[m.end():]
    
    # 제목끝숫자 完 패턴 (예: 칸푸1023完)
    # 숫자만 있고 범위가 없는 경우
    # 주의: "시즌N", "부N" 같은 패턴은 제외
    if not range_info:
        title_num_pattern = r'([가-힣A-Za-z]+)(\d{1,6})\s*(완결?|Complete|완|完)\b'
        m = re.search(title_num_pattern, text, re.IGNORECASE)
        if m:
            # "시즌", "부" 같은 키워드는 제외
            if m.group(1) not in ['시즌', '부']:
                has_complete = True
                range_info = f'1-{int(m.group(2))}'
                text = text[:m.start()] + m.group(1) + ' ' + text[m.end():]
    
    # N화 완결_N 패턴 (예: 318화 완결_2) - 뒤의 숫자 포함 제거
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,5})\s*(권|화|편|회)\s*(완결?|Complete|완|完)(?:텍|_텍|_\d+)', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # N권 完 패턴 (예: 10권 完)
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'\b(\d{1,4})\s*(권|화|편|회)\s*(완결?|Complete|완|完)\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # N (완결) 패턴 (예: 198 (완결))
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'\b(\d{1,4})\s*\(완결\)', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 단독 完 패턴 (범위 뒤에 오는 경우: "1-200 完", "131 完, 후기", "1-225화 完", "1-318화 완결 2")
    # 이미 범위가 있으면 完만 제거하고 has_complete 설정
    # ⚠️ 이 패턴은 접미사 패턴보다 먼저 실행되어야 함!
    # 주의: preprocess_symbols에서 _가 공백으로 변환되므로 "완결_2" → "완결 2"
    if patterns['has_existing_range'] and not has_complete:
        # (화|편|회|권)? + 공백? + 完/완결 + (공백+숫자)? - 뒤의 숫자도 함께 제거
        m = re.search(r'(?:화|편|회|권)?\s*(完|완결?|Complete)(?:\s+\d+|텍)?', text, re.IGNORECASE)
        if m:
            has_complete = True
            # 完과 뒤의 숫자 전체 제거
            text = text[:m.start()] + text[m.end():]
    
    # 숫자 + 完 + @닉네임 패턴 (예: "00198 完 @K", "120 完@아말하")
    # 이 패턴을 먼저 처리해야 "完 @"가 단독으로 제거되지 않음
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(0?\d{2,6})\s*(완결?|Complete|완|完)\s*@[^\s@]+', text, re.IGNORECASE)
        if m:
            has_complete = True
            num_str = m.group(1)
            range_info = f'1-{int(num_str)}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 완+후기/외전+@닉네임 패턴 (예: 完@아말하, 完@koi, 完후기@김갈비뼈)
    # 이 패턴을 먼저 처리해야 "完후기@"가 저자명으로 잘못 인식되지 않음
    m = re.search(r'(완결?|Complete|완|完)(후기|외전|에필로그|에필)?\s*@[^\s@]+', text, re.IGNORECASE)
    if m:
        has_complete = True
        # 후기/외전/에필로그가 있으면 extras에 추가
        if m.group(2):
            extra_label = '에필' if m.group(2) in ['에필로그', '에필'] else m.group(2)
            if extra_label not in extras:
                extras.append(extra_label)
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 단일 숫자 + 完 + 에필/후기 패턴 (예: "165 完 에필")
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,5})\s+(완결?|Complete|완|完)\s+(에필로그|에필|후기|외전)\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            extra_label = '에필' if m.group(3) in ['에필로그', '에필'] else m.group(3)
            if extra_label not in extras:
                extras.append(extra_label)
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 단일 숫자 + 完 + 저자명 패턴 (예: "128完고유성")
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(\d{1,6})(완결?|Complete|완|完)([가-힣]{2,3})\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(1))}'
            # 완결 표시와 저자명 모두 제거
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 完 + 숫자 패턴 (완결 표시가 숫자 앞에 오는 경우)
    # 예: "完 120" → range=1-120, complete=True
    if not patterns['has_existing_range'] and not range_info:
        m = re.search(r'(완결?|Complete|완|完)\s+(\d{1,6})\b', text, re.IGNORECASE)
        if m:
            has_complete = True
            range_info = f'1-{int(m.group(2))}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 단일 숫자 + 完 패턴 (최대 6자리까지 지원, 앞에 0이 있어도 처리)
    # 예: 00198, 001200, 1023 등
    # 주의: 5자리 숫자 (00198)도 범위로 변환
    # 주의: 제목 시작 부분의 연도는 제외 (예: "1874 대혁명", "1904 대한민국")
    # 주의: 천 단위 구분 쉼표가 있는 숫자는 제외 (예: "163,417,413번째")
    # 이 패턴은 다른 패턴들보다 나중에 실행되어야 함 (우선순위 낮음)
    if not patterns['has_existing_range'] and not range_info:
        # 5-6자리 숫자 패턴 (00198, 001200 등) - 앞에 0이 있는 경우
        # 먼저 0으로 시작하는 5-6자리 숫자를 찾음
        m = re.search(r'\s(0\d{4,5})\s*(완결?|Complete|완|完)', text, re.IGNORECASE)
        if m:
            has_complete = True
            num_str = m.group(1)
            # 앞의 0 제거하여 정수로 변환
            range_info = f'1-{int(num_str)}'
            # 매칭된 부분 제거 (공백 하나는 유지)
            text = text[:m.start()] + ' ' + text[m.end():]
        else:
            # 일반 숫자 패턴 (1-4자리만 매칭, 5자리 이상은 위에서 처리)
            # 주의: "시즌N", "부N" 같은 패턴은 제외
            # 주의: 제목 시작 부분의 연도는 제외 (예: "1874 대혁명", "1904 대한민국")
            # 주의: 천 단위 구분 쉼표가 있는 숫자는 제외 (예: "163,417,413번째")
            m = re.search(r'\s(\d{1,4})\s*(완결?|Complete|완|完)\s*(?:,\s*)?', text, re.IGNORECASE)
            if m:
                # 숫자 바로 앞에 "시즌"이나 "부"가 있는지 확인
                before_num = text[:m.start()]
                # 숫자 바로 앞 문자열 확인 (공백 제거 전)
                if not re.search(r'(시즌|부)$', before_num):
                    # 제목 시작 부분의 연도인지 확인 (앞에 한글이 없으면 제목의 일부)
                    # 예: "1874 대혁명" (제목), "제목 1874" (범위)
                    has_title_before = bool(re.search(r'[가-힣a-zA-Z]', before_num))
                    
                    # 천 단위 구분 쉼표가 있는지 확인 (예: "163,417,413번째")
                    # 숫자 바로 앞에 쉼표+숫자가 있으면 천 단위 구분 숫자의 일부
                    has_comma_before = bool(re.search(r',\d+$', before_num))
                    
                    # 제목이 앞에 있고, 천 단위 구분 쉼표가 없으면 범위로 간주
                    if has_title_before and not has_comma_before:
                        has_complete = True
                        num_str = m.group(1)
                        range_info = f'1-{int(num_str)}'
                        text = text[:m.start()] + ' ' + text[m.end():]

    # 접미사형 완표시 제거 (단, 제목 시작 부분과 한글 단어 일부는 제외)
    # 예: "完텍", "완_1", "완@", "完 (텍)_1", "完 (텍) 1" 등은 제거하지만 "완미세계", "완벽한" 같은 제목은 보호
    # 조건: 공백이나 숫자 뒤에 오는 "완" + 특수문자/텍스트만 제거
    # 주의: "완결 - 한글이름" 형태는 부제목으로 보존 (예: "완결 - 청빙 최영진")
    # 주의: "숫자-완결" 형태는 위에서 처리하므로 여기서는 제외
    complete_suffix_patterns = [
        r'(完|완)\s*\(텍\)\s*[_\s]*\d+',  # 完 (텍)_1, 完 (텍) 1 패턴 (preprocess 전후 모두 처리)
        r'(完|완)(?:텍|_텍|_\d+)',  # 完텍, 완_1 등 (뒤의 숫자 포함)
        r'(완결|Complete)(?:텍|_?텍|_\d+)',  # 완결_2, Complete_1 등 (뒤의 숫자 포함)
        r'[\s\d]+(완결?|Complete|완|完)(?:텍|_?텍)?\s*[_@Q]+\s*\d*',  # 공백/숫자 + 완 + 특수문자 (하이픈 제외)
        r'(?<!-)\s+(완결|Complete)(?:텍|_?텍)?\s*[_@Q]*\s*\d*'  # 공백 + "완결", "Complete" (하이픈 뒤 제외)
    ]
    for pattern in complete_suffix_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            has_complete = True
            # 첫 세 패턴(完 (텍)_1, 完텍, 완_1, 완결_2)은 전체 제거
            if pattern in [complete_suffix_patterns[0], complete_suffix_patterns[1], complete_suffix_patterns[2]]:
                text = text[:m.start()] + text[m.end():]
            else:
                # 나머지는 앞의 공백/숫자 1개는 유지
                text = text[:m.start()+1] + text[m.end():]

    # 完 뒤에 바로 한글이 오는 패턴 처리 (예: "完후일담", "完번외")
    # 이 패턴을 먼저 처리해야 후일담/번외가 extras에 추가됨
    m = re.search(r'(完|완|완결|Complete)(후일담|번외|외전|에필로그|에필|후기)', text, re.IGNORECASE)
    if m:
        has_complete = True
        extra_label = m.group(2)
        # 에필로그는 에필로 통일
        if extra_label in ['에필로그', '에필']:
            extra_label = '에필'
        if extra_label not in extras:
            extras.append(extra_label)
        # 完과 키워드 모두 제거
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 기타 간단한 표기들
    # 주의: "완벽한", "완미세계" 같은 제목의 "완"은 보호해야 함
    # 주의: "숫자-숫자-완" 형태는 위에서 처리하므로 여기서는 제외
    simple_complete_patterns = [
        r'-완-',  # "-완-" 패턴
        r'(?<!\d)-완(?![가-힣])',  # "-완" 패턴 (단, 뒤에 한글이 없는 경우만)
        r'\[완\]', r'\[완결\]', r'완\[\d*\]',
        r'\(완결\)',  # (완결) 패턴
        r',\s*완\b',  # ", 완" 패턴
        r'(完|완),',  # "完," 또는 "완," 패턴
        r'\s+(完)[A-Z]?\s*$',  # 끝에 오는 " 完" 또는 " 完K" 패턴
        r'\s+(完)[A-Z]?\.'  # 확장자 앞 " 完." 또는 " 完K." 패턴
    ]
    for pattern in simple_complete_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            has_complete = True
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    
    # ========== "완" 단독 패턴 (명확한 완결 표시만) ==========
    # 규칙: 공백으로 분리되어 있고, 앞뒤에 한글이 붙어있지 않은 경우만
    
    # 패턴 1: 공백 + 완 + 문자열 끝 (예: "제목 완")
    # 조건: 앞에 한글이 바로 붙어있지 않음 (완벽, 완전, 완공, 완료 등 제외)
    m = re.search(r'(?<![가-힣])\s+완\s*$', text, re.IGNORECASE)
    if m:
        has_complete = True
        text = text[:m.start()] + text[m.end():]
    
    # 패턴 2: 공백 + 완 + 공백 (예: "제목 완 부제목")
    # 조건: 앞뒤에 한글이 바로 붙어있지 않음
    m = re.search(r'(?<![가-힣])\s+완\s+(?![가-힣])', text, re.IGNORECASE)
    if m:
        has_complete = True
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 3: 공백 + 완. (확장자 앞)
    m = re.search(r'(?<![가-힣])\s+완\.', text, re.IGNORECASE)
    if m:
        has_complete = True
        text = text[:m.start()] + text[m.end():]

    text = re.sub(r'\(\s*\)\s*', '', text)
    text = re.sub(r'\s*\(완\)\s*', ' ', text, flags=re.IGNORECASE)

    # ========== 후처리: 보호된 "완" 복원 ==========
    text = text.replace('__WAN_PROTECTED__', '완')
    
    # print(f"출력: text='{text}', has_complete={has_complete}, range_info={range_info}")
    # print(f"=== extract_complete_and_extras 종료 ===\n")

    return normalize_unicode_spaces(text), has_complete, range_info, extras


def extract_range_and_extras(text: str, extras_from_complete: Optional[List[str]] = None, range_from_complete: Optional[str] = None) -> Tuple[str, Optional[str], List[str]]:
    # extras_from_complete는 extract_complete_and_extras에서 넘어온 외전/후기 정보
    extras: List[str] = extras_from_complete[:] if extras_from_complete else []
    range_info: Optional[str] = range_from_complete
    
    # "§§COMMA§§"를 쉼표로 복원
    text = text.replace('§§COMMA§§', ',')
    
    # 대괄호 안의 외전/에필/후기 패턴 처리 (예: [에필로그후기], [외전], [외전후기])
    # 패턴 1: [에필로그후기] → 에필, 후기
    if re.search(r'\[에필로그후기\]', text, re.IGNORECASE):
        if '에필' not in extras:
            extras.append('에필')
        if '후기' not in extras:
            extras.append('후기')
        text = re.sub(r'\[에필로그후기\]', '', text, flags=re.IGNORECASE)
    
    # 패턴 2: [외전후기] → 외전, 후기
    if re.search(r'\[외전후기\]', text, re.IGNORECASE):
        if not any('외전' in e for e in extras):
            extras.append('외전')
        if '후기' not in extras:
            extras.append('후기')
        text = re.sub(r'\[외전후기\]', '', text, flags=re.IGNORECASE)
    
    # 패턴 3: [외전N-M화미완] → 외전 N-M (예: [외전1-5화미완])
    # 미완 플래그는 무시하고 범위만 추출
    m = re.search(r'\[외전(\d{1,4})-(\d{1,4})화?미완?\]', text, re.IGNORECASE)
    if m:
        extra_range = f'{int(m.group(1))}-{int(m.group(2))}'
        extras.append(f'외전 {extra_range}')
        text = text[:m.start()] + ' ' + text[m.end():]
    
    # 패턴 4: [외전] → 외전
    if re.search(r'\[외전\]', text, re.IGNORECASE):
        if not any('외전' in e for e in extras):
            extras.append('외전')
        text = re.sub(r'\[외전\]', '', text, flags=re.IGNORECASE)
    
    # 패턴 4: [에필로그] 또는 [에필] → 에필
    if re.search(r'\[(에필로그|에필)\]', text, re.IGNORECASE):
        if '에필' not in extras:
            extras.append('에필')
        text = re.sub(r'\[(에필로그|에필)\]', '', text, flags=re.IGNORECASE)
    
    # 패턴 5: [후기] → 후기
    if re.search(r'\[후기\]', text, re.IGNORECASE):
        if '후기' not in extras:
            extras.append('후기')
        text = re.sub(r'\[후기\]', '', text, flags=re.IGNORECASE)
    
    # 에필후기/에필로그후기 패턴 처리 (대괄호 없는 경우)
    # 예: 에필후기 → 에필, 후기 / 에필로그후기 → 에필, 후기
    if re.search(r'\b(에필로그후기|에필후기)\b', text):
        if '에필' not in extras:
            extras.append('에필')
        if '후기' not in extras:
            extras.append('후기')
        text = re.sub(r'\b(에필로그후기|에필후기)\b', '', text)
    
    # 외전후기 패턴 처리 (대괄호 없는 경우)
    # 예: 외전후기 → 외전, 후기
    if re.search(r'\b외전후기\b', text):
        if not any('외전' in e for e in extras):
            extras.append('외전')
        if '후기' not in extras:
            extras.append('후기')
        text = re.sub(r'\b외전후기\b', '', text)
    
    # 에필로그/외전 범위를 먼저 추출 (범위 추출보다 우선)
    # 예: "에필로그 1-5" → extras에 "에필 1-5" 추가
    epilogue_with_range = re.search(r'(에필로그|에필)\s*(\d{1,4}(?:-\d{1,4})?)', text)
    if epilogue_with_range:
        nums = epilogue_with_range.group(2)
        ext_entry = f'에필 {nums}'
        if ext_entry not in extras:
            extras.append(ext_entry)
        text = text[:epilogue_with_range.start()] + ' ' + text[epilogue_with_range.end():]

    # "1-6841,2부" 패턴 처리 (예: "1-6841,2부" → "1-684"와 "1-2부")
    # 쉼표 앞 마지막 숫자가 부 번호인 경우
    # 패턴: N-ABCD,E부 또는 N-ABCD, E부 (공백 허용)
    # 예: 1-6841,2부 → 1-684 (range), 1-2부 (bu)
    # 예: 1-4501,2부 → 1-450 (range), 1-2부 (bu)
    m = re.search(r'(\d{1,4})-(\d{2,})(\d)\s*,\s*(\d)부', text)
    if m:
        # 마지막 숫자를 제외한 나머지가 범위
        range_end = m.group(2)  # 예: "684" 또는 "450"
        bu_start = m.group(3)   # 예: "1"
        bu_end = m.group(4)     # 예: "2"
        
        if not range_info:
            range_info = f'{m.group(1)}-{range_end}'
        bu_info = f'{bu_start}-{bu_end}부'
        text = text[:m.start()] + ' ' + bu_info + ' ' + text[m.end():]
    
    # '부' 패턴 특별 처리
    # 패턴: "N화 N부" (예: "1-430화 1부") → 부 정보를 제목 앞으로 이동
    bu_match = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s*(화|권|편|회)\s+(\d{1,4}부)', text)
    if bu_match:
        # 범위와 부 정보 추출
        if not range_info:
            range_info = f'{int(bu_match.group(1))}-{int(bu_match.group(2))}'
        bu_info = bu_match.group(4)
        # 텍스트에서 제거하고 나중에 build_standard_name에서 재배치
        text = text[:bu_match.start()] + ' ' + bu_info + ' ' + text[bu_match.end():]
    
    # "1부 2부" 패턴 처리 (예: 1부 2부 → 1-2부)
    # 주의: 연속된 부 정보를 범위로 변환
    m = re.search(r'(\d{1,4})부\s+(\d{1,4})부', text)
    if m:
        bu_info = f'{m.group(1)}-{m.group(2)}부'
        text = text[:m.start()] + bu_info + text[m.end():]
    
    # "1-406 1-2부" 패턴 처리 (범위와 부 정보가 분리된 경우)
    # 주의: 부 정보를 제목 앞으로 이동하되 그대로 유지
    # "1- 2부" 같이 공백이 있는 경우도 처리
    m = re.search(r'(\d{1,4})\s*-\s*(\d{1,4})\s+(\d{1,4})\s*-\s*(\d{1,4})부', text)
    if m:
        if not range_info:
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
        bu_info = f'{m.group(3)}-{m.group(4)}부'
        # 부 정보를 그대로 유지 (제목 앞에 배치)
        text = text[:m.start()] + ' ' + bu_info + ' ' + text[m.end():]
    
    # '부' 패턴 보호 (예: 1-3부 등은 범위로 변환 X)
    has_bu_pattern = re.search(r'\d{1,4}(?:-\d{1,4})?\s*부\b', text)
    if has_bu_pattern:
        # N-M 범위 추출 (부 패턴이 있어도 처리)
        # 예: "2부 532-562" → "2부" + range_info="532-562"
        if not range_info:
            # 부 패턴이 아닌 N-M 범위 찾기
            for m in re.finditer(r'(\d{1,4})\s*-\s*(\d{1,4})(?!\s*부)', text):
                # 시즌 패턴이 아닌지 확인
                before_match = text[:m.start()]
                if not re.search(r'시즌\s*$', before_match):
                    range_info = f'{int(m.group(1))}-{int(m.group(2))}'
                    text = text[:m.start()] + ' ' + text[m.end():]
                    # 범위 추출 후 남은 단위 제거
                    text = re.sub(r'\b(화|권|편|회)\b', '', text)
                    break
        
        # "-N" 패턴 처리 (부 정보 뒤에 있는 경우도 처리)
        # 예: "2부 -203" → "2부 1-203"
        if not range_info:
            m = re.search(r'-(\d{1,4})\b', text)
            if m:
                range_info = f'1-{int(m.group(1))}'
                text = text[:m.start()] + ' ' + text[m.end():]
        
        # 단일 숫자를 범위로 변환 (부 패턴이 있어도 처리)
        # 예: "1-3부 814" → "1-3부" + range_info="1-814"
        if not range_info:
            # 부 패턴을 제외한 단일 숫자만 찾기
            # "1-3부"의 일부가 아닌 독립적인 숫자만 추출
            for m in re.finditer(r'\b(\d{1,4})(?:\s*(화|권|편|회))?\b', text):
                num = m.group(1)
                # 앞에 0이 있는 3자리 이하 숫자는 제목의 일부로 간주
                if num.startswith('0') and len(num) <= 3:
                    continue
                
                start, end = m.start(), m.end()
                before_text = text[:start]
                after_text = text[end:] if end < len(text) else ''
                
                # 부 패턴의 일부인지 확인
                # 1) 바로 뒤에 "부"가 있으면 제외 (예: "1부", "3부")
                if re.match(r'\s*부\b', after_text):
                    continue
                
                # 2) 바로 앞이 "-"이고 뒤에 "부"가 있으면 제외 (예: "1-3부"의 "3")
                if re.search(r'-\s*$', before_text):
                    # 뒤에 "부"가 있는지 확인
                    remaining = text[start:]
                    if re.match(r'\d+\s*부\b', remaining):
                        continue
                
                # 3) 바로 뒤가 "-"이고 그 뒤에 숫자+"부"가 있으면 제외 (예: "1-3부"의 "1")
                if re.match(r'\s*-\s*\d+\s*부\b', after_text):
                    continue
                
                # 유효한 단일 숫자 발견
                if (start == 0 or re.match(r'\W', text[start-1])) and (end == len(text) or re.match(r'\W', text[end])):
                    text = text[:m.start()] + text[m.end():]
                    range_info = f'1-{int(num)}'
                    # 범위 추출 후 남은 단위 제거
                    text = re.sub(r'\b(화|권|편|회)\b', '', text)
                    break
        
        # 외전/후기/에필 등만 추출
        # 주의: 부 정보 (예: "1-3부")는 외전 범위가 아님
        # "외전 N-M부"는 제외하고 "외전 N-M"만 추출
        ext_patterns = [
            r'(?:^|[^가-힣])외전\s*(\d{1,4}(?:-\d{1,4})?)(?!\s*부)',  # 외전 1-3 (단, "외전 1-3부"는 제외)
            r'(\d{1,4}(?:-\d{1,4})?)\s*외전(?:[^가-힣]|$)'  # 1-3 외전
        ]
        for pattern in ext_patterns:
            while True:
                m = re.search(pattern, text)
                if not m:
                    break
                nums = m.group(1)
                ext_entry = f'외전 {nums}'
                if ext_entry not in extras:
                    extras.append(ext_entry)
                text = text[:m.start()] + ' ' + text[m.end():]
        if '외전포함' in text:
            if not any('외전' in e for e in extras):
                extras.append('외전')
            text = text.replace('외전포함', '')
        if re.search(r'\b외전\b', text):
            if not any('외전' in e for e in extras):
                extras.append('외전')
            text = re.sub(r'\b외전\b', '', text)
        for label in ['후기', '에필로그', '에필']:
            if re.search(rf'\b{label}\b', text):
                normalized_label = '에필' if label in ['에필로그', '에필'] else label
                if normalized_label not in extras:
                    extras.append(normalized_label)
                text = re.sub(rf'\b{label}\b', '', text)
        
        # "특외", "특별편" 처리 (부 패턴 보호 블록 내에서)
        if re.search(r'\b특외\b', text):
            if '특외' not in extras:
                extras.append('특외')
            text = re.sub(r'\b특외\b', '', text)
        
        if re.search(r'\b특별편\b', text):
            if '특별편' not in extras:
                extras.append('특별편')
            text = re.sub(r'\b특별편\b', '', text)
        
        return normalize_unicode_spaces(text), range_info, extras

    # 대괄호 범위 [1-111]
    if not range_info:
        m = re.search(r'\[(\d{1,4})\s*-\s*(\d{1,4})\]', text)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            text = text[:m.start()] + text[m.end():]
            return normalize_unicode_spaces(text), range_info, extras
    
    # 괄호 안의 범위 (001회-111회) → 1-111, (1-36) → 1-36
    if not range_info:
        # 패턴 1: (N회-M회) 형태
        m = re.search(r'\((\d{1,4})(회|화|편|권)-(\d{1,4})(회|화|편|권)\)', text)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(3))}'
            text = text[:m.start()] + text[m.end():]
            return normalize_unicode_spaces(text), range_info, extras
        
        # 패턴 2: (N-M) 형태 (단위 없음)
        m = re.search(r'\((\d{1,4})-(\d{1,4})\)', text)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            text = text[:m.start()] + text[m.end():]
            return normalize_unicode_spaces(text), range_info, extras

    # "N-외전" 패턴 특별 처리 (예: "1-외전" → 범위 없이 외전만 추출)
    # "1-외전"은 의미 없는 범위이므로 외전만 추출
    m = re.search(r'\d{1,4}\s*-\s*외전\b', text)
    if m:
        if '외전' not in extras:
            extras.append('외전')
        text = text[:m.start()] + ' ' + text[m.end():]
        # range_info는 설정하지 않음 (의미 없는 범위)
    
    # "N권-M권" 패턴 처리 (예: "01권-04권" → "1-4")
    if not range_info:
        m = re.search(r'(\d{1,4})권\s*-\s*(\d{1,4})권', text)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # "-N" 패턴 처리 (예: -203 → 1-203, 2부 -203 → 2부 1-203)
    # 완결 표시가 없어도 처리
    # 부 정보 뒤에 오는 경우도 처리
    # 주의 1: N-M 패턴의 일부가 아닌지 확인 (예: 001-078에서 -078은 제외)
    # 주의 2: 제목의 일부인 경우 제외 (예: "-99레벨 대마법사"에서 -99는 제목)
    # 조건 1: 공백 뒤에 오는 "-N" 패턴만 범위로 간주
    # 조건 2: 제목 시작 부분(앞에 한글/영문이 없는 경우)은 제외
    # 조건 3: 숫자 뒤에 "레벨", "살", "세", "년", "대" 등이 오면 제목의 일부로 간주
    if not range_info:
        m = re.search(r'\s+-(\d{1,4})\b', text)
        if m:
            # 하이픈 앞의 텍스트 확인
            before_hyphen = text[:m.start()].strip()
            # 앞에 한글/영문이 있는지 확인 (제목이 있으면 범위로 간주)
            has_title_before = bool(re.search(r'[가-힣a-zA-Z]', before_hyphen))
            
            # 숫자 뒤의 텍스트 확인
            after_num = text[m.end():m.end()+10]  # 뒤 10글자 확인
            # 제목의 일부인지 확인 (레벨, 살, 세, 년, 대, 층, 급 등)
            is_title_part = bool(re.match(r'(레벨|살|세|년|대|층|급|단|차|기)', after_num))
            
            # 제목이 앞에 있고, 뒤가 제목의 일부가 아니면 범위로 간주
            if has_title_before and not is_title_part:
                range_info = f'1-{int(m.group(1))}'
                text = text[:m.start()] + ' ' + text[m.end():]
    
    # 일반 범위 추출 (시즌 패턴 제외)
    if not range_info:
        # 패턴 1: N회-M회 형태 (각 숫자 뒤에 단위)
        # 예: 001회-111회, 1화-100화
        m = re.search(r'(\d{1,4})(회|화|편|권)\s*-\s*(\d{1,4})(회|화|편|권)', text)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(3))}'
            text = text[:m.start()] + text[m.end():]
    
    # 패턴 2: N-M 형태 (단위 없거나 뒤에만)
    if not range_info:
        # 시즌 패턴이 아닌 범위만 추출
        # 주의: 001-178 같은 패턴도 1-178로 변환
        # 주의: "1-201 1부" 같은 패턴에서 부 정보는 제목에 남김
        for m in re.finditer(r'(\d{1,4})\s*-\s*(\d{1,4})(?:\s*(화|권|편|회))?', text):
            # 시즌 앞의 범위인지 확인
            before_match = text[:m.start()]
            if not re.search(r'시즌\s*$', before_match):
                left, right = m.group(1), m.group(2)
                
                # "N부-한글" 패턴은 범위가 아님 (예: "1부-광무황제")
                # 범위 뒤에 한글이 바로 오는지 확인
                after_match = text[m.end():]
                if re.match(r'[가-힣]', after_match):
                    # "N부-한글" 패턴이므로 범위가 아님
                    continue
                
                # 범위 뒤에 부 정보가 있는지 확인
                bu_match = re.match(r'\s*(\d{1,4}부)', after_match)
                if bu_match:
                    # 부 정보가 있으면 제목에 남기고 범위만 제거
                    # m.start()부터 m.end() + bu_match.end()까지를 bu_match.group(1)로 교체
                    text = text[:m.start()] + bu_match.group(1) + text[m.end() + bu_match.end():]
                else:
                    text = text[:m.start()] + ' ' + text[m.end():]
                range_info = f'{int(left)}-{int(right)}'
                # 범위 추출 후 남은 단위 제거
                text = re.sub(r'\b(화|권|편|회)\b', '', text)
                break
        else:
            # 단일 숫자 추출 (단위 포함 가능)
            # 주의: 001, 007 같은 앞에 0이 있는 숫자는 범위로 변환하지 않음
            # 주의: "1115 시즌4" 같은 패턴에서 시즌 앞의 숫자는 범위로 변환
            # 주의: 제목 시작 부분의 연도는 제외 (예: "1874 대혁명")
            # 주의: 천 단위 구분 쉼표가 있는 숫자는 제외 (예: "163,417,413번째")
            m = re.search(r'\b(\d{1,4})(?:\s*(화|권|편|회))?\b', text)
            if m:
                num = m.group(1)
                # 앞에 0이 있는 3자리 이하 숫자는 제목의 일부로 간주 (예: 007, 001)
                if num.startswith('0') and len(num) <= 3:
                    # 타이틀 일부일 가능성: 무시
                    range_info = None
                else:
                    start, end = m.start(), m.end()
                    
                    # 숫자 앞의 텍스트 확인
                    before_num = text[:start]
                    
                    # 천 단위 구분 쉼표가 있는지 확인 (예: "163,417,413번째")
                    # 숫자 앞이나 뒤에 쉼표가 있으면 천 단위 구분 숫자
                    has_comma_before = bool(re.search(r',\d+$', before_num))
                    
                    # 숫자 뒤의 텍스트 확인
                    after_match = text[end:]
                    
                    # 숫자 뒤에 쉼표가 있는지 확인 (예: "163,417,413번째")
                    has_comma_after = bool(re.match(r',\d+', after_match))
                    
                    # 숫자 뒤에 시즌 패턴이 있는지 확인
                    has_season_after = bool(re.match(r'\s*시즌\d+', after_match))
                    
                    # 숫자 뒤에 한글이 있는지 확인 (예: "1874 대혁명" - 연도)
                    has_korean_after = bool(re.match(r'\s+[가-힣]', after_match))
                    
                    # 제목 시작 부분의 연도인지 확인 (앞에 한글이 없고 뒤에 한글이 있으면 연도)
                    is_year_at_start = (not re.search(r'[가-힣a-zA-Z]', before_num) and has_korean_after)
                    
                    # 4자리 연도 (1800-2099)는 제목의 일부로 간주
                    is_year_number = (len(num) == 4 and 1800 <= int(num) <= 2099)
                    
                    if (start == 0 or re.match(r'\W', text[start-1])) and (end == len(text) or re.match(r'\W', text[end])):
                        # 천 단위 구분 쉼표가 있거나, 제목 시작 부분의 연도이거나, 4자리 연도이면 무시
                        if has_comma_before or has_comma_after or is_year_at_start or is_year_number:
                            range_info = None
                        else:
                            # 시즌 패턴이 뒤에 있으면 범위로 변환하고 시즌 정보는 유지
                            text = text[:m.start()] + text[m.end():]
                            range_info = f'1-{int(num)}'
                            # 범위 추출 후 남은 단위 제거
                            text = re.sub(r'\b(화|권|편|회)\b', '', text)
                    else:
                        # 타이틀 일부일 가능성: 무시
                        range_info = None
    
    # 범위 추출 후 남은 단위 제거 (추가 정리)
    text = re.sub(r'\s+(화|권|편|회)\s+', ' ', text)
    
    # 미완 키워드 제거 (외전 범위 추출 후 남은 경우)
    text = re.sub(r'\b미완\b', '', text, flags=re.IGNORECASE)

    # 외전/후기/에필/특외/후일담 추출
    # 외전 N화/N장 패턴 처리 (예: 외전 11화 → 외전 11, 외전 5장 → 외전 5)
    # 주의: 제목에 "외전"이 포함된 경우 (예: "혈기린외전")는 제외
    # 주의: 부 정보 (예: "1-3부")는 외전 범위가 아님
    # 한글이 아닌 문자 뒤에 오는 "외전"만 매칭하되, 뒤에 "부"가 오면 제외
    ext_patterns = [
        r'외전(\d{1,4}(?:-\d{1,4})?)\s*(화|장)',  # 외전11화, 외전 5장 (공백 있거나 없거나)
        r'외전(\d{1,4}(?:-\d{1,4})?)(?!\s*부)',  # 외전11, 외전 11 (단, "외전 1-3부"는 제외)
        r'(\d{1,4}(?:-\d{1,4})?)\s*(화|장)\s*외전',  # 11화 외전, 5장 외전
        r'(\d{1,4}(?:-\d{1,4})?)\s*외전(?:\s|,|$)'  # 11 외전 (공백, 쉼표, 끝)
    ]
    for pattern in ext_patterns:
        while True:
            m = re.search(pattern, text)
            if not m:
                break
            nums = m.group(1)
            ext_entry = f'외전 {nums}'
            if ext_entry not in extras:
                extras.append(ext_entry)
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # "특외" (특별외전) 패턴 처리
    # 패턴 1: 특외N화 → 특외 N (예: 특외8화 → 특외 8)
    m = re.search(r'특외(\d{1,4})화?', text)
    if m:
        ext_entry = f'특외 {m.group(1)}'
        if ext_entry not in extras:
            extras.append(ext_entry)
        text = text[:m.start()] + ' ' + text[m.end():]
    # 패턴 2: 특외 (단독)
    elif re.search(r'\b특외\b', text):
        if '특외' not in extras:
            extras.append('특외')
        text = re.sub(r'\b특외\b', '', text)
    
    # "특별편" 패턴 처리
    if re.search(r'\b특별편\b', text):
        if '특별편' not in extras:
            extras.append('특별편')
        text = re.sub(r'\b특별편\b', '', text)
    
    # 후일담 패턴 처리 (번외보다 먼저 처리)
    # 패턴 1: 후일담 N-M (예: 후일담 1-46)
    postscript_pattern = re.search(r'후일담\s*(\d{1,4}(?:-\d{1,4})?)', text)
    if postscript_pattern:
        nums = postscript_pattern.group(1)
        ext_entry = f'후일담 {nums}'
        if ext_entry not in extras:
            extras.append(ext_entry)
        text = text[:postscript_pattern.start()] + ' ' + text[postscript_pattern.end():]
    
    # 패턴 2: 후일담 (단독, 쉼표와 함께 제거)
    if re.search(r',\s*후일담\b', text):
        if '후일담' not in extras:
            extras.append('후일담')
        text = re.sub(r',\s*후일담\b', '', text)
    elif re.search(r'\b후일담\s*,', text):
        if '후일담' not in extras:
            extras.append('후일담')
        text = re.sub(r'\b후일담\s*,', '', text)
    elif re.search(r'\b후일담\b', text):
        if '후일담' not in extras:
            extras.append('후일담')
        text = re.sub(r'\b후일담\b', '', text)
    
    # "번외" 패턴 처리 (후일담 다음에 처리)
    if re.search(r'\b번외\b', text):
        if '번외' not in extras:
            extras.append('번외')
        text = re.sub(r'\b번외\b', '', text)
    
    # "인랑전", "귀환후일담", "추가외전" 같은 특수 외전 패턴 처리
    special_extras = ['인랑전', '귀환후일담', '추가외전']
    for extra_name in special_extras:
        if extra_name in text:
            if extra_name not in extras:
                extras.append(extra_name)
            text = text.replace(extra_name, '')
    
    # "추가외전"이 있으면 "외전"도 추가 (순서: 외전, 추가외전)
    if '추가외전' in extras and '외전' not in [e for e in extras if e == '외전']:
        # 외전을 추가외전 앞에 삽입
        idx = extras.index('추가외전')
        extras.insert(idx, '외전')
    
    if '외전포함' in text:
        if not any('외전' in e for e in extras):
            extras.append('외전')
        text = text.replace('외전포함', '')
    
    # 외전 N 패턴 먼저 추출 (예: 외전 3, 외전 1-5)
    # 주의: "외전 N"은 "외전"만 추출하지 않고 "외전 N"으로 추출
    ext_patterns_outside_bu = [
        r'외전\s*(\d{1,4}(?:-\d{1,4})?)\s*(화|장)',  # 외전 3화, 외전 5장
        r'외전\s*(\d{1,4}(?:-\d{1,4})?)(?!\s*부)',  # 외전 3, 외전 1-5 (단, "외전 1-3부"는 제외)
        r'(\d{1,4}(?:-\d{1,4})?)\s*(화|장)\s*외전',  # 3화 외전, 5장 외전
        r'(\d{1,4}(?:-\d{1,4})?)\s*외전(?:\s|,|$)'  # 3 외전 (공백, 쉼표, 끝)
    ]
    for pattern in ext_patterns_outside_bu:
        while True:
            m = re.search(pattern, text)
            if not m:
                break
            nums = m.group(1)
            ext_entry = f'외전 {nums}'
            if ext_entry not in extras:
                extras.append(ext_entry)
            text = text[:m.start()] + ' ' + text[m.end():]
    
    # 외전 추출 (쉼표와 함께 제거)
    # 패턴: ", 외전" 또는 "외전," 또는 "외전"
    # 주의: 외전을 extras 맨 앞에 추가 (순서 유지)
    # 주의: "외전 N" 형태는 위에서 이미 처리했으므로 여기서는 단독 "외전"만 처리
    if re.search(r',\s*외전\b(?!\s*\d)', text):
        if not any('외전' in e for e in extras):
            extras.insert(0, '외전')
        text = re.sub(r',\s*외전\b(?!\s*\d)', '', text)
    elif re.search(r'\b외전\s*,', text):
        if not any('외전' in e for e in extras):
            extras.insert(0, '외전')
        text = re.sub(r'\b외전\s*,', '', text)
    elif re.search(r'\b외전\b(?!\s*\d)', text):
        if not any('외전' in e for e in extras):
            extras.insert(0, '외전')
        text = re.sub(r'\b외전\b(?!\s*\d)', '', text)
    
    # 에필로그/에필/후기 추출 (에필로그는 에필로 통일)
    # 범위 정보가 있는 경우 먼저 처리 (예: 에필로그 1-3)
    epilogue_with_range = re.search(r'(에필로그|에필)\s*(\d{1,4}(?:-\d{1,4})?)', text)
    if epilogue_with_range:
        nums = epilogue_with_range.group(2)
        ext_entry = f'에필 {nums}'
        if ext_entry not in extras:
            extras.append(ext_entry)
        text = text[:epilogue_with_range.start()] + ' ' + text[epilogue_with_range.end():]
    
    # 단독 에필로그/에필/후기 추출 (쉼표와 함께 제거)
    for label in ['후기', '에필로그', '에필']:
        normalized_label = '에필' if label in ['에필로그', '에필'] else label
        
        # 패턴: ", 후기" 또는 "후기," 또는 "후기"
        if re.search(rf',\s*{label}\b', text):
            if normalized_label not in extras:
                extras.append(normalized_label)
            text = re.sub(rf',\s*{label}\b', '', text)
        elif re.search(rf'\b{label}\s*,', text):
            if normalized_label not in extras:
                extras.append(normalized_label)
            text = re.sub(rf'\b{label}\s*,', '', text)
        elif re.search(rf'\b{label}\b', text):
            if normalized_label not in extras:
                extras.append(normalized_label)
            text = re.sub(rf'\b{label}\b', '', text)

    return normalize_unicode_spaces(text), range_info, extras


def final_cleanup(text: str) -> str:
    # 1부-2부, 1부, 2부 패턴을 먼저 1-2부로 변환
    # 패턴 1: 1부-2부 → 1-2부
    text = re.sub(r'(\d{1,2})부\s*-\s*(\d{1,2})부\b', r'\1-\2부', text)
    # 패턴 2: 1부, 2부 → 1-2부
    text = re.sub(r'(\d{1,2})부\s*,\s*(\d{1,2})부\b', r'\1-\2부', text)
    # 패턴 3: 1, 2부 → 1-2부
    text = re.sub(r'(\d{1,2})\s*,\s*(\d{1,2})부\b', r'\1-\2부', text)
    
    # (19N) 1부 → 1부 (19N) 패턴 변환
    # 괄호 안의 내용 뒤에 부 정보가 있으면 순서 변경
    # 패턴 1: (19N) 1-2부 → 1-2부 (19N)
    text = re.sub(r'\(([^)]+)\)\s+(\d{1,2}-\d{1,2}부)', r'\2 (\1)', text)
    # 패턴 2: (19N) 1부 → 1부 (19N)
    text = re.sub(r'\(([^)]+)\)\s+(\d{1,2}부)(?!-)', r'\2 (\1)', text)
    
    # 괄호 안 공백 정리 (예: "(19N )" → "(19N)", "( 19N)" → "(19N)")
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    
    # 천 단위 구분 쉼표는 보존 (예: 1,000조, 6,421, 163,417,413번째)
    # 불필요한 쉼표만 제거
    # 주의: 숫자,숫자 패턴에서 쉼표 뒤가 3자리 숫자면 천 단위 구분으로 간주하여 보존
    # 예: "1,000조" (보존), "163,417,413번째" (보존), ", 1-431" (제거)
    
    # 불필요한 쉼표 제거 (공백 + 쉼표 + 공백)
    # 단, 천 단위 구분 쉼표는 보존 (숫자,3자리숫자 패턴)
    # 예: "163,417,413번째" (보존), ", 1-431" (제거)
    
    # 천 단위 구분 쉼표가 아닌 경우만 제거
    # 패턴: 쉼표 뒤가 3자리 숫자가 아니거나, 쉼표 앞이 숫자가 아닌 경우
    text = re.sub(r'(?<!\d)\s*,\s*(?=\d)', ' ', text)  # 숫자가 아닌 것 + 쉼표 + 숫자 → 공백
    text = re.sub(r'\s*,\s*(?=\d{1,2}\D)', ' ', text)  # 쉼표 + 1-2자리 숫자 + 비숫자 → 공백
    text = re.sub(r'\s*,\s*(?=\d{4,}(?!\d))', ' ', text)  # 쉼표 + 4자리 이상 숫자 (뒤에 숫자 없음) → 공백
    text = re.sub(r'^\s*,\s*', '', text)  # 시작 쉼표
    text = re.sub(r'\s*,\s*$', '', text)  # 끝 쉼표
    # 연속된 쉼표 제거 (예: ",,")
    text = re.sub(r',{2,}', '', text)
    # 공백 + 쉼표만 있는 경우 제거
    text = re.sub(r'\s+,\s*$', '', text)
    
    # 제목 중간의 구분자 보존 (-, ,, ., ~)
    # 패턴: "한글/영문 - 한글/영문" 형태는 보존
    # 예: "사신 - 설봉", "남(男) - 사마달", "경기당 1.12골"
    
    # 언더바만 공백으로 변환 (쉼표, 점, 하이픈은 보존)
    text = re.sub(r'_+', ' ', text)
    
    # 불필요한 점(.) 제거
    # 패턴 1: 한글/영문 뒤의 점 + 한글/영문 → 공백 (예: "제목.저자" → "제목 저자")
    text = re.sub(r'([가-힣a-zA-Z])\s*\.\s*([가-힣a-zA-Z])', r'\1 \2', text)
    # 패턴 2: 괄호 뒤의 점 + 한글/영문 → 공백 (예: "(귀도).송진용" → "(귀도) 송진용")
    text = re.sub(r'\)\s*\.\s*([가-힣a-zA-Z])', r') \1', text)
    # 패턴 3: 시작/끝 점 제거
    text = re.sub(r'^\s*\.\s*', '', text)
    text = re.sub(r'\s*\.\s*$', '', text)
    
    # 숫자가 아닌 곳의 하이픈 처리
    # 단, "한글/영문 - 한글/영문" 패턴은 보존
    # 예: "사신 - 설봉" (보존), "제목-부제목" (보존), "제목 - 저자" (보존)
    # 제거 대상: 끝 하이픈, 연속된 하이픈
    # 주의: 시작 하이픈은 제목의 일부일 수 있으므로 제거하지 않음 (예: "-99레벨 대마법사")
    # text = re.sub(r'^\s*-\s*', '', text)  # 시작 하이픈 제거 - 주석 처리
    text = re.sub(r'\s*-\s*$', '', text)  # 끝 하이픈 제거
    text = re.sub(r'-{2,}', '-', text)    # 연속 하이픈 하나로
    # 끝에 남는 불필요한 단일 '1' 제거
    text = re.sub(r'\s+\b1\b$', ' ', text)
    # 불필요한 "1-" 제거 (제목 중간이나 끝에 남은 경우)
    # 예: "제목 1- 1-100" → "제목 1-100"
    text = re.sub(r'\s+1-\s+(?=\d)', ' ', text)
    text = re.sub(r'\s+1-\s*$', ' ', text)
    # 불필요한 빈 괄호 제거 (여러 패턴)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)
    text = re.sub(r'\(\s*,\s*\)', '', text)
    
    # 괄호 안의 부 정보에서 불필요한 공백 제거 (예: "( 1부 )" → "(1부)")
    text = re.sub(r'\(\s+(\d{1,4}부)\s+\)', r'(\1)', text)
    # 괄호 안의 부 정보를 괄호 밖으로 (예: "(1부)" → "1부")
    text = re.sub(r'\((\d{1,4}부)\)', r'\1', text)
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    
    # 미완 키워드 제거 (최종 정리)
    text = re.sub(r'\b미완\b', '', text, flags=re.IGNORECASE)
    
    # 제목 끝 숫자 처리 (예: "무계술사1" → "무계술사")
    # 단, 범위가 아닌 경우에만, 그리고 "시즌", "부" 뒤의 숫자는 보존
    # "시즌1", "부1" 같은 패턴은 보존
    # 조건: 앞 2글자가 "시즌"이나 "부"가 아닌 경우만 제거
    if not re.search(r'(시즌|부)\d+\s*$', text):
        text = re.sub(r'([가-힣a-zA-Z])(\d)\s*$', r'\1', text)
    # 제목 중간의 불필요한 숫자 제거 (예: "제목1 이름수정" → "제목 이름수정")
    # 단, "시즌", "부" 뒤의 숫자는 보존
    text = re.sub(r'(?<!시즌)(?<!부)([가-힣a-zA-Z])(\d)\s+([가-힣a-zA-Z])', r'\1 \3', text)
    
    return text.strip()


def build_standard_name(category, title, range_info, has_complete, extras):
    # 제목에서 (완) 중복 제거
    title = re.sub(r'\s*\(완\)\s*', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    # 괄호 표현 앞뒤 공백 정리 (예: "제목(19N)" → "제목 (19N)")
    # 패턴: 한글/영문/숫자 + 괄호 → 공백 추가
    title = re.sub(r'([가-힣a-zA-Z0-9])\(', r'\1 (', title)
    # 괄호 + 한글/영문/숫자 → 공백 추가
    title = re.sub(r'\)([가-힣a-zA-Z0-9])', r') \1', title)
    # 연속된 공백 제거
    title = re.sub(r'\s+', ' ', title).strip()
    
    # 제목에서 개정판/완전판/수정판 정보 추출 (괄호 포함)
    # 패턴: (개정판), [개정판], {개정판}, (완전판), [수정판] 등
    # 주의: 괄호를 포함하여 추출하고, 괄호가 없으면 추가하지 않음
    edition_info = None
    
    # 먼저 괄호가 있는 패턴 찾기
    m = re.search(r'[\(\[\{](개정판|완전판|수정판|개정|완전|수정)[\)\]\}]', title)
    if m:
        edition_info = m.group(0)  # 괄호 포함 전체 매칭
        # 제목에서 제거
        title = title[:m.start()] + ' ' + title[m.end():]
        title = re.sub(r'\s+', ' ', title).strip()
    else:
        # 괄호 없는 경우 찾기
        m = re.search(r'\b(개정판|완전판|수정판)\b', title)
        if m:
            edition_info = m.group(0)  # 괄호 없이 그대로
            # 제목에서 제거
            title = title[:m.start()] + ' ' + title[m.end():]
            title = re.sub(r'\s+', ' ', title).strip()
    
    # 제목에서 "부" 정보 추출 (예: "1-2부", "1부", "2부")
    # 부 정보는 제목에서 분리하여 별도로 관리
    # 주의: "1부 (완전판)" 같은 패턴에서 개정판을 먼저 분리
    bu_info = None
    
    # 패턴 0-1: "N-M부" → 범위 부 정보 (예: "1-2부", "1-3부")
    m = re.search(r'(\d{1,4}-\d{1,4}부)(?:\s|$)', title)
    if m:
        bu_info = m.group(1)
        # 제목에서 제거
        title = title[:m.start()] + ' ' + title[m.end():]
        title = re.sub(r'\s+', ' ', title).strip()
    # 패턴 0-2: "N부 (개정판/완전판/수정판)" → 부 정보와 개정판 분리
    # 이 경우 개정판은 이미 추출되었으므로 부 정보만 추출
    elif re.search(r'(\d{1,4}부)\s+[\(\[\{](개정판|완전판|수정판|개정|완전|수정)[\)\]\}]', title):
        m = re.search(r'(\d{1,4}부)\s+[\(\[\{](개정판|완전판|수정판|개정|완전|수정)[\)\]\}]', title)
        bu_info = m.group(1)
        # 제목에서 부 정보만 제거 (개정판은 이미 제거됨)
        title = title[:m.start()] + ' ' + title[m.end():]
        title = re.sub(r'\s+', ' ', title).strip()
    else:
        # 패턴 1: "1부 2부", "1, 2부", "1,2부" 형태를 "1-2부"로 변환
        # 패턴 1-1: "1부 2부" (두 개 모두 부 있음)
        m = re.search(r'(\d{1,4})\s*부\s*[,\s]+\s*(\d{1,4})\s*부', title)
        if m:
            bu_info = f'{m.group(1)}-{m.group(2)}부'
            # 제목에서 제거
            title = title[:m.start()] + ' ' + title[m.end():]
            title = re.sub(r'\s+', ' ', title).strip()
        else:
            # 패턴 1-2: "1,2부" (첫 번째 부 없음)
            m = re.search(r'(\d{1,4})\s*,\s*(\d{1,4})\s*부', title)
            if m:
                bu_info = f'{m.group(1)}-{m.group(2)}부'
                # 제목에서 제거
                title = title[:m.start()] + ' ' + title[m.end():]
                title = re.sub(r'\s+', ' ', title).strip()
            else:
                # 패턴 1-3: 단일 부 정보 (예: "1부", "2부")
                # 주의: "1-2부" 같은 범위 부 정보는 제외
                m = re.search(r'(?<!-\d)(?<!-\d\d)(?<!-\d\d\d)(?<!-\d\d\d\d)(\d{1,4}부)(?:\s|$)', title)
                if m:
                    bu_info = m.group(1)
                    # 제목에서 제거
                    title = title[:m.start()] + ' ' + title[m.end():]
                    title = re.sub(r'\s+', ' ', title).strip()
    
    # 패턴 2: 범위 + 부 정보 (예: "1-226 1-2부", "1-201 1부")
    # 범위를 추출하고 부 정보는 별도로 관리
    # 주의: "1-2부"는 부 정보이지 범위가 아님 (부가 붙어있으면 부 정보)
    m = re.search(r'(\d{1,4}-\d{1,4})(?!부)\s+(\d{1,4}-\d{1,4}부|\d{1,4}부)', title)
    if m:
        # 범위가 이미 있으면 유지, 없으면 설정
        if not range_info:
            range_info = m.group(1)
        # 부 정보 추출
        if not bu_info:
            bu_info = m.group(2)
        # 제목에서 제거
        title = title[:m.start()] + ' ' + title[m.end():]
        title = re.sub(r'\s+', ' ', title).strip()
    
    # 제목에서 "시즌" 정보 분리 (예: "시즌1-2", "시즌1", "시즌2")
    season_info = None
    m = re.search(r'\s*(시즌\d{1,4}(?:-\d{1,4})?)\s*$', title)
    if m:
        season_info = m.group(1)
        title = title[:m.start()].strip()
    
    # 범위 정보의 앞 0 제거 (예: 001-185 → 1-185)
    if range_info:
        m = re.match(r'(\d+)-(\d+)', range_info)
        if m:
            range_info = f'{int(m.group(1))}-{int(m.group(2))}'
    
    # 파일명 조립
    # 순서: [장르] 제목 개정판 부정보 시즌정보 범위 (완) + extras
    parts: List[str] = []
    if category:
        parts.append(category)
    if title:
        parts.append(title)
    if edition_info:
        parts.append(edition_info)
    if bu_info:
        parts.append(bu_info)
    if season_info:
        parts.append(season_info)
    if range_info:
        parts.append(range_info)
    if has_complete and not has_incomplete_flag(title):
        parts.append('(완)')
    if extras:
        # extras가 "N부 N-M (완)" 형태인지 확인
        has_bu_complete = any(re.match(r'\d{1,4}부\s+\d{1,4}-\d{1,4}\s+\(완\)', e) for e in extras)
        if has_bu_complete:
            parts.extend(extras)
        else:
            parts.append('+ ' + ', '.join(extras))
    
    result = ' '.join(parts)
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'(\]|\))\s+', r'\1 ', result)
    return result.strip()


def needs_user_review(original: str, normalized: str) -> bool:
    """사용자 확인이 필요한 케이스 감지"""
    # 제목 끝에 숫자가 있고 범위가 없는 경우 (예: 매니저181)
    name_part, _ = extract_extension(normalized)
    # 범위 정보가 없고 제목 끝에 숫자가 있는 경우
    if not re.search(r'\d+-\d+', name_part) and re.search(r'[가-힣a-zA-Z]\d+\s*\(완\)', name_part):
        return True
    return False


def normalize_line(raw: str) -> Optional[str]:
    """
    파일명 정규화 (장르 추론 포함)
    
    CLI 모드 및 독립 실행 시 사용됩니다.
    장르 태그가 없으면 자동으로 추론하여 추가합니다.
    
    Args:
        raw: 원본 파일명 (확장자 포함)
        
    Returns:
        정규화된 파일명 또는 None
        
    Example:
        >>> normalize_line("헌터의 모험 1-100 완.txt")
        "[퓨판] 헌터의 모험 1-100 (완).txt"
    """
    name, ext = extract_extension(raw)

    if not name.strip():
        return None

    # 원본에서 미완/연재중 여부 감지(표시 삽입 억제용)
    is_incomplete_flag = has_incomplete_flag(name)

    category, rest = detect_category(name)
    
    # 카테고리가 없으면 파일명에서 장르 추론
    if not category:
        inferred_genre = infer_genre_from_filename(name)
        # None이 아니고 유효한 장르일 때만 추가
        if inferred_genre and inferred_genre != 'None':
            category = f'[{inferred_genre}]'
            print(f"3-1. 장르 추론: '{inferred_genre}' (키워드 기반)")
    
    rest = preprocess_symbols(rest)
    rest = remove_basic_noise(rest)
    rest = remove_author_info(rest)

    if is_incomplete_flag:
        rest = re.sub(r'\s*\(미완\)\s*|\s*\(연재중\)\s*|\s*미\s*\)\s*', ' ', rest, flags=re.IGNORECASE)
        rest = normalize_unicode_spaces(rest)
    
    rest, has_complete, range_from_complete, extras_from_complete = extract_complete_and_extras(rest)
    rest, range_info, extras = extract_range_and_extras(rest, extras_from_complete, range_from_complete)

    title = final_cleanup(rest)

    # 미완/연재중이면 (완) 강제 억제
    if is_incomplete_flag:
        has_complete = False

    std = build_standard_name(category, title, range_info, has_complete, extras)

    if ext:
        # 확장자 추가 전 공백 정리
        std = std.strip()
        std += ext
    
    return std if std.strip() else None


def normalize_line_without_genre_inference(raw: str) -> Optional[str]:
    """
    파일명 정규화 (장르 추론 제외)
    
    GUI 탭 2 (파일명 정규화)에서 사용됩니다.
    장르는 탭 1에서 이미 추가되었다고 가정하고, 정규화만 수행합니다.
    장르 태그가 없어도 추론하지 않고 그대로 진행합니다.
    
    Args:
        raw: 원본 파일명 (확장자 포함)
        
    Returns:
        정규화된 파일명 또는 None
        
    Example:
        >>> normalize_line_without_genre_inference("[판타지] 제목 1-100 완.txt")
        "[판타지] 제목 1-100 (완).txt"
        
        >>> normalize_line_without_genre_inference("제목 1-100 완.txt")
        "제목 1-100 (완).txt"  # 장르 추론하지 않음
    """
    name, ext = extract_extension(raw)

    if not name.strip():
        return None
    
    # 정규화가 필요한지 확인
    # 다음 중 하나라도 해당하면 정규화 필요:
    # 1. 완/完/Complete 같은 미정규화 완결 표시가 있음
    # 2. 外, 외포, 번외, 에필로그 같은 미정규화 extras가 있음
    # 3. 앞에 0이 있는 숫자가 있음 (예: 01권, 001-121)
    # 4. @, ⓒ 같은 저자 표시가 있음
    # 5. _, + 같은 특수 기호가 있음 (공백으로 변환 필요)
    # 6. (외전포함) 같은 패턴이 있음
    # 7. "회", "화", "권" 같은 단위가 범위에 붙어있음
    # 8. 개정판/완전판이 범위 뒤에 있음 (제목과 범위 사이로 이동 필요)
    # 9. "1부 2부" 같은 패턴이 있음 (1-2부로 변환 필요)
    
    # 이미 정규화된 패턴 체크 (멱등성 보장)
    # "N부 N-M (완) N부 N-M (완)" 패턴은 이미 정규화된 형태
    is_already_normalized_multi_bu = bool(re.search(
        r'\d{1,4}부\s+\d{1,4}-\d{1,4}\s+\(완\)\s+\d{1,4}부\s+\d{1,4}-\d{1,4}\s+\(완\)',
        name, re.IGNORECASE
    ))
    
    # 이미 정규화된 경우 그대로 반환
    if is_already_normalized_multi_bu:
        return raw
    
    needs_normalization = (
        bool(re.search(r'(?<!\()(完|완결?|Complete)(?!\))', name, re.IGNORECASE)) or  # 미정규화 완결
        bool(re.search(r'(?<!\+\s)(外|외포|번외|에필로그|외전포함)', name)) or  # 미정규화 extras
        bool(re.search(r'\b0\d+', name)) or  # 앞에 0이 있는 숫자
        bool(re.search(r'[@ⓒ]', name)) or  # 저자 표시
        bool(re.search(r'[_+](?!\s+(외전|에필|후기))', name)) or  # 특수 기호 (extras 제외)
        bool(re.search(r'\(외전포함\)', name, re.IGNORECASE)) or  # (외전포함)
        bool(re.search(r'\d+-\d+(회|화|권)', name)) or  # 범위에 단위 붙음
        bool(re.search(r'\d+-\d+\s+\(완\)\s+[\(\[\{]?(개정판|완전판|수정판)', name)) or  # 개정판이 범위 뒤
        bool(re.search(r'\d{1,4}부\s+[\(\[\{](개정판|완전판|수정판)', name)) or  # 개정판이 부 뒤 (이동 필요)
        bool(re.search(r'\d{1,4}부\s+\d{1,4}부', name)) or  # "1부 2부" 패턴
        bool(re.search(r'\d{1,4}부_\d{1,4}부', name)) or  # "1부_2부" 패턴
        bool(re.search(r'^\(', name)) or  # 소괄호로 시작 (대괄호로 변환 필요)
        bool(re.search(r'\(완\)\s*-\s*[가-힣]{2,4}', name)) or  # (완) - 저자명
        bool(re.search(r'\[[가-힣]{2,4}\]', name)) or  # [저자명]
        bool(re.search(r'\d{1,4}부,\d{1,4}부', name)) or  # "1부,2부" 패턴
        bool(re.search(r'\d+\(완\)', name, re.IGNORECASE)) or  # 숫자(완) - 공백 없음
        bool(re.search(r'[가-힣a-zA-Z]\d+\s*-\s*\d+', name)) or  # 제목숫자-숫자 - 공백 없음
        bool(re.search(r'\s+\+\s+\w+\s+\+\s+', name)) or  # + 에필 + 후기 (쉼표로 변경 필요)
        bool(re.search(r'외전\s+\d+-\d+\s+\(완\)', name, re.IGNORECASE))  # 외전 N-M (완) - (완) 제거 필요
    )
    
    # 정규화가 필요 없으면 그대로 반환
    if not needs_normalization:
        return raw

    # 원본에서 미완/연재중 여부 감지(표시 삽입 억제용)
    # 단, "N부完(연재중)" 패턴은 예외 (해당 부는 완결)
    is_incomplete_flag = has_incomplete_flag(name)
    has_bu_complete = bool(re.search(r'\d{1,4}부\s*(完|완|완결|Complete)', name, re.IGNORECASE))

    # 기존 장르 태그만 추출 (추론하지 않음)
    category, rest = detect_category(name)
    
    # 장르 추론 로직 제거
    # GUI 탭 1에서 이미 장르를 추가했다고 가정
    
    rest = preprocess_symbols(rest)
    rest = remove_basic_noise(rest)
    rest = remove_author_info(rest)

    if is_incomplete_flag:
        rest = re.sub(r'\s*\(미완\)\s*|\s*\(연재중\)\s*|\s*미\s*\)\s*', ' ', rest, flags=re.IGNORECASE)
        rest = normalize_unicode_spaces(rest)
    
    rest, has_complete, range_from_complete, extras_from_complete = extract_complete_and_extras(rest)
    rest, range_info, extras = extract_range_and_extras(rest, extras_from_complete, range_from_complete)

    title = final_cleanup(rest)
    
    # 제목 끝의 중복 파일 번호 추출 (예: "(1)", "(2)")
    # 이 번호는 맨 마지막에 다시 추가됨
    duplicate_number = None
    m = re.search(r'\s*\((\d+)\)\s*$', title)
    if m:
        duplicate_number = f'({m.group(1)})'
        title = title[:m.start()].strip()

    # 미완/연재중이면 (완) 강제 억제
    # 단, 부 완결 패턴이 있으면 예외 (3부 완결, 4부 연재중 같은 경우)
    if is_incomplete_flag and not has_bu_complete:
        has_complete = False

    std = build_standard_name(category, title, range_info, has_complete, extras)
    
    # 중복 파일 번호를 맨 뒤에 추가
    if duplicate_number:
        std = std.strip() + ' ' + duplicate_number

    if ext:
        # 확장자 추가 전 공백 정리
        std = std.strip()
        std += ext
    
    return std if std.strip() else None


def main():
    if not INPUT_FILE.exists():
        print(f"{INPUT_FILE}가 없습니다.")
        return
    originals = [line.strip() for line in INPUT_FILE.read_text(encoding='utf-8').splitlines() if line.strip()]
    mapping: Dict[str, str] = {}
    used: Dict[str, int] = {}
    for orig in originals:
        std = normalize_line(orig)
        if not std:
            continue
        name_part, ext_part = extract_extension(std)
        base = name_part
        if base in used:
            used[base] += 1
            std_final = f'{base} ({used[base]}){ext_part}'
        else:
            used[base] = 1
            std_final = std
        mapping[orig] = std_final

    normalized_rows = list(mapping.values())
    OUTPUT_LIST.write_text('\n'.join(normalized_rows) + '\n', encoding='utf-8')
    with OUTPUT_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['original_name', 'standard_name'])
        writer.writerows(mapping.items())
    print(f'정규화 완료: {len(mapping)}건')
    print(f'- 표준 목록: {OUTPUT_LIST}')
    print(f'- 매핑 CSV: {OUTPUT_CSV}')


if __name__ == '__main__':
    main()
