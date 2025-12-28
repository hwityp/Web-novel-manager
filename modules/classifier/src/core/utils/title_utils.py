"""
제목 처리 유틸리티
"""

import re
from typing import List, Tuple, Optional


def normalize_title(title: str) -> str:
    """제목 정규화 (검색 성공률 향상)
    
    - 특수문자 처리
    - 괄호 내용 제거
    - 띄어쓰기 정규화
    
    Args:
        title: 원본 제목
        
    Returns:
        정규화된 제목
    """
    # 1. 괄호 내용 제거 (단, 중요 정보는 유지)
    # (RM), (완), (19금) 등 제거
    title = re.sub(r'\s*[\(\[](RM|완결?|단행본|연재중|개정판|합본|특별판|19[금Nn]|15금)[\)\]]\s*', ' ', title)
    
    # 2. 특수문자 정규화
    # ㆍ → 공백
    title = title.replace('ㆍ', ' ')
    # · → 공백
    title = title.replace('·', ' ')
    # ~ → 공백
    title = title.replace('~', ' ')
    
    # 3. 연속된 공백 제거
    title = re.sub(r'\s+', ' ', title)
    
    # 4. 앞뒤 공백 제거
    title = title.strip()
    
    return title


def add_spacing_to_title(title: str) -> str:
    """띄어쓰기 없는 제목에 자동 띄어쓰기 추가 (간단한 휴리스틱)
    
    예: "영마스터여행기" → "영 마스터 여행기"
    
    Args:
        title: 원본 제목
        
    Returns:
        띄어쓰기가 추가된 제목
    """
    # 이미 띄어쓰기가 있으면 그대로 반환
    if ' ' in title:
        return title
    
    # 너무 짧으면 그대로 반환
    if len(title) < 5:
        return title
    
    # 간단한 패턴 기반 띄어쓰기
    # 예: "영마스터여행기" → "영 마스터 여행기"
    
    # 패턴 1: 한글 + 영문 경계
    result = re.sub(r'([가-힣])([A-Za-z])', r'\1 \2', title)
    result = re.sub(r'([A-Za-z])([가-힣])', r'\1 \2', result)
    
    # 패턴 2: 숫자 + 한글 경계
    result = re.sub(r'(\d)([가-힣])', r'\1 \2', result)
    result = re.sub(r'([가-힣])(\d)', r'\1 \2', result)
    
    return result


def split_title_variants(title: str) -> List[str]:
    """제목을 여러 변형으로 분리
    
    Returns:
        [전체제목, 부분1, 부분2, ...]
    """
    variants = [title]
    
    # 저자명 패턴 감지
    def is_author_name(text):
        # 쉼표 또는 & 구분
        if ',' in text or '&' in text:
            # 쉼표와 &를 모두 구분자로 처리
            names = re.split(r'[,&]', text)
            names = [n.strip() for n in names]
            if len(names) >= 2 and all(2 <= len(n) <= 5 for n in names):
                return True
        return False
    
    def is_valid_title_part(text):
        """분리된 부분이 검색 가능한 완전한 제목인지 검증"""
        if not text or len(text) < 2:
            return False
        
        text_no_space = text.replace(' ', '').replace(',', '').replace('.', '')
        
        if len(text_no_space) < 5:
            return False
        
        if ' ' not in text.strip() and len(text_no_space) < 8:
            return False
        
        if text.endswith(('의', '은', '는', '이', '가', '을', '를', '에', '와', '과', '로', '으로')):
            return False
        
        if text in ['외전', '전기', '서', '편', '기', '록']:
            return False
        
        generic_words = [
            '되었다', '되어버렸다', '시작했다', '살아남다',
            '드래곤', '마법', '검', '용', '왕', '제국',
            '마왕', '용사', '던전', '몬스터'
        ]
        if text.strip() in generic_words:
            return False
        
        meaningless_patterns = [
            r'^[가-힣]*하시겠습니까$',
            r'^[가-힣]*되시겠습니까$',
            r'^[가-힣]*입니까$',
            r'^[가-힣]*습니까$',
            r'^[가-힣]*되었습니다$',
            r'^[가-힣]*했습니다$',
            r'^[가-힣]*합니다$',
            r'^[가-힣]*입니다$',
        ]
        
        for pattern in meaningless_patterns:
            if re.match(pattern, text.strip()):
                if not re.search(r'[가-힣]{2,}(을|를|이|가|은|는|의|에|와|과)', text):
                    return False
        
        return True
    
    # 0단계: 공백으로 저자명 분리
    if ' ' in title:
        parts = title.split(' ')
        
        if len(parts) >= 2:
            last_part = parts[-1]
            second_last_part = parts[-2] if len(parts) >= 2 else ''
            
            if is_author_name(last_part):
                title_without_author = ' '.join(parts[:-1])
                if len(title_without_author) >= 1:
                    variants.append(title_without_author)
                    return variants
            
            if (2 <= len(last_part) <= 4 and 
                last_part.replace(' ', '').isalpha() and
                not second_last_part.endswith(('은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '로', '으로'))):
                if last_part not in ['외전', '전기', '서', '편', '기', '록']:
                    title_without_author = ' '.join(parts[:-1])
                    if len(title_without_author) >= 3:
                        variants.append(title_without_author)
    
    # 짧은 제목은 더 이상 분리하지 않음
    title_length_no_space = len(title.replace(' ', '').replace(',', '').replace('.', ''))
    if title_length_no_space < 11:
        return variants
    
    # 1단계: "-" 기준 분리
    if ' - ' in title or ' -' in title or '- ' in title:
        parts = re.split(r'\s*-\s*', title)
        for part in parts:
            part = part.strip()
            if is_author_name(part):
                continue
            if is_valid_title_part(part) and part not in variants:
                variants.append(part)
    
    # 2단계: 외전 키워드 패턴
    if len(variants) == 1:
        match = re.search(r'^(.+)\s+([^\s]{3,}(?:전기|외전|서|편|기|록))\s*$', title)
        if match:
            part1 = match.group(1).strip()
            part2 = match.group(2).strip()
            
            if is_valid_title_part(part1) and is_valid_title_part(part2) and part1 != title and part2 != title:
                variants.append(part1)
                variants.append(part2)
            elif not is_valid_title_part(part1) and is_valid_title_part(part2):
                variants.append(part2)
    
    # 3단계: 짧은 제목 + 외전 패턴
    if len(variants) == 1 and ' ' in title:
        match = re.search(r'^(.+)\s+(외전|전기|서|편)\s*$', title)
        if match:
            part1 = match.group(1).strip()
            if is_valid_title_part(part1) and part1 != title:
                variants.append(part1)
    
    # 4단계: 조사 기준 분리
    if len(variants) == 1:
        josa_pattern = r'(은|는|이|가|을|를|의|에|와|과|로|으로)\s+([가-힣]{2,}(?:\s+[가-힣]+)*)\s*$'
        match = re.search(josa_pattern, title)
        
        if match:
            noun_part = match.group(2).strip()
            
            if is_valid_title_part(noun_part) and noun_part not in variants:
                variants.append(noun_part)
    
    return variants


def parse_title_info(title: str) -> dict:
    """제목 분석 및 정보 추출
    
    Returns:
        {
            'main_title': str,
            'subtitle': Optional[str],
            'author': Optional[str],
            'full_title': str
        }
    """
    original_title = title
    
    # 1단계: 저자명 추출
    author_name = None
    
    # 복수 저자 패턴 (쉼표 또는 & 구분, 공백 유무 무관)
    # 예: "검궁인, 사마달", "검궁인,사마달", "홍길동 & 김철수", "홍길동&김철수"
    author_match = re.search(r'\s+[-/]\s+([가-힣]{2,5}(?:\s*[,&]\s*[가-힣]{2,5})+)\s*(?:\(완\))?$', title)
    if author_match:
        author_name = author_match.group(1)
        # 공백 정규화 (쉼표/& 앞뒤 공백 제거)
        author_name = re.sub(r'\s*([,&])\s*', r'\1 ', author_name).strip()
        title = title[:author_match.start()].strip()
    else:
        # 단일 저자 (2~5글자, 예: "홍길동", "요도김남재")
        author_match = re.search(r'\s+[-/]\s+([가-힣]{2,5})\s*(?:\(완\))?$', title)
        if author_match:
            potential_author = author_match.group(1)
            # 제목 키워드가 아닌 경우만 저자명으로 인식
            if potential_author not in ['외전', '전기', '서', '편', '기', '록', '상권', '하권', '중권']:
                author_name = potential_author
                title = title[:author_match.start()].strip()
    
    # 2단계: 부제목 추출
    subtitle = None
    
    # 2-1: "N부" 패턴으로 분리 (예: "초능력 연대기 1부 더 맨이터")
    part_match = re.search(r'^(.+?)\s+(\d+부)\s+(.+)$', title)
    if part_match:
        main = part_match.group(1).strip()
        part_num = part_match.group(2)
        sub = part_match.group(3).strip()
        # 주제목과 부제목 분리
        title = main
        subtitle = f"{part_num} {sub}"
    
    # 2-2: 괄호 내용 추출
    if not subtitle:
        # 띄어쓰기 없이 바로 붙은 괄호 (부제목): "초능력 연대기(맨이터)"
        subtitle_match = re.search(r'([가-힣a-zA-Z0-9]+)\(([가-힣a-zA-Z0-9\s]+)\)\s*$', title)
        if subtitle_match:
            before_paren = subtitle_match.group(1)
            in_paren = subtitle_match.group(2).strip()
            
            # 부가 정보가 아닌 경우만 부제목으로 인식
            if in_paren not in ['완결', '완', '단행본', '연재중', '개정판', '합본', '특별판', '19금', '15금', '19N', '19n']:
                # 괄호 앞 부분이 있으면 주제목으로
                if before_paren:
                    title = title[:subtitle_match.start()] + before_paren
                    subtitle = in_paren
                else:
                    title = title[:subtitle_match.start()].strip()
                    subtitle = in_paren
        else:
            # 띄어쓰기 있는 괄호 (부가 정보): "초능력 연대기 (맨이터)"
            subtitle_match = re.search(r'\s+\(([가-힣a-zA-Z0-9\s]+)\)\s*$', title)
            if subtitle_match:
                in_paren = subtitle_match.group(1).strip()
                # 부가 정보는 제거만 하고 부제목으로 사용하지 않음
                if in_paren not in ['완결', '완', '단행본', '연재중', '개정판', '합본', '특별판', '19금', '15금', '19N', '19n']:
                    # 띄어쓰기가 있으면 부가 정보로 간주하고 제거
                    title = title[:subtitle_match.start()].strip()
                    subtitle = None
                else:
                    # 완결 등의 정보는 제거
                    title = title[:subtitle_match.start()].strip()
                    subtitle = None
    
    # 3단계: 에피소드 번호 제거 (단, 제목의 일부인 숫자는 유지)
    # "1-126화" 같은 범위는 제거하되, "1913" 같은 단독 숫자는 유지
    title = re.sub(r'\s+\d+[-~]\d+\s*화', '', title)  # "1-126화" 제거
    title = re.sub(r'\s+\d+[-~]\d+\s*\(완\)', '', title)  # "1-126 (완)" 제거
    title = re.sub(r'\s+\d+화(?=\s|$)', '', title)  # "126화" 제거
    
    # 4단계: 부가 정보 괄호 제거
    title = re.sub(r'\s*[\[\(](19[Nn]|완결|완|단행본|연재중|개정판|합본|특별판|19금|15금)[\]\)]\s*', ' ', title)
    
    # 5단계: 공백 정리
    title = re.sub(r'\s+', ' ', title)
    title = title.strip()
    
    return {
        'main_title': title,
        'subtitle': subtitle,
        'author': author_name,
        'full_title': original_title
    }


def is_short_title(title: str) -> bool:
    """짧은 제목 판단 (1단어 또는 공백 제외 6글자 이하)"""
    title_words = title.split()
    title_no_space = title.replace(' ', '')
    return (len(title_words) == 1) or (len(title_no_space) <= 6)
