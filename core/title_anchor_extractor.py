"""
Title Anchor Extractor 모듈

파일명에서 핵심 제목(Title Anchor)을 추출하고, 잔여 문자열에서 메타데이터를 파싱합니다.
'제목 앵커 전략'의 핵심: 제목을 먼저 추출한 후, 나머지 문자열에서만 권수/범위/완결 정보를 파싱합니다.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9
"""
import re
import os
from dataclasses import dataclass
from typing import Tuple, Optional, List


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
    
    def to_normalized_filename(self, genre: str = "") -> str:
        """
        정규화된 파일명 생성
        형식: [장르] 제목 부정보 범위 (완) + 외전.확장자
        """
        parts = []
        
        # 장르
        if genre:
            parts.append(f"[{genre}]")
        
        # 제목
        parts.append(self.title)
        
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
    
    # 노이즈 패턴 (저자명, 번역 정보 등)
    AUTHOR_PATTERNS = [
        r'@\S+',                           # @닉네임
        r'ⓒ\S+',                           # ⓒ닉네임
        r'©\S+',                           # ©닉네임
        r'저자[:\s]*\S+',                  # 저자: 이름
        r'작가[:\s]*\S+',                  # 작가: 이름
        r'글[:\s]*\S+',                    # 글: 이름
        r'by\s+\S+',                       # by Author
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
        r'번역[:\s]*\S+',
        r'역자[:\s]*\S+',           # "역자: 이름" 형태만 매칭 (역전기 등 제외)
        r'\[번역\]',
        r'\(번역\)',
    ]
    
    # 장르 태그 패턴 (제거 대상) - 완결은 제외 (완결 마커로 처리)
    GENRE_TAG_PATTERNS = [
        r'\[(?:판타지|무협|현판|퓨판|로판|겜판|SF|역사|선협|언정|공포|스포츠|소설|단행본|연재중|개정판|합본|특별판|미분류)\]',
        r'\((?:판타지|무협|현판|퓨판|로판|겜판|SF|역사|선협|언정|공포|스포츠|소설|단행본|연재중|개정판|합본|특별판|미분류)\)',
    ]
    
    # 성인 등급 태그 패턴 (제거 대상)
    ADULT_TAG_PATTERNS = [
        r'\(\s*19N\s*\)',                   # (19N)
        r'\[\s*19N\s*\]',                   # [19N]
        r'\(\s*19금\s*\)',                  # (19금)
        r'\[\s*19금\s*\]',                  # [19금]
        r'\(\s*15금\s*\)',                  # (15금)
        r'\[\s*15금\s*\]',                  # [15금]
        r'\(\s*성인\s*\)',                  # (성인)
        r'\[\s*성인\s*\]',                  # [성인]
    ]
    
    # 플랫폼/번역자 태그 패턴 (제거 대상)
    PLATFORM_TAG_PATTERNS = [
        r'\[임아소\]',                       # [임아소] - 번역 사이트
        r'\[네이버시리즈\]',
        r'\[카카오페이지\]',
        r'\[문피아\]',
        r'\[조아라\]',
        r'\[리디북스\]',
        r'\[노벨피아\]',
        r'\(\s*AI번역\s*\)',                 # (AI번역)
        r'\[\s*AI번역\s*\]',                 # [AI번역]
    ]
    
    # 완결 마커 패턴
    COMPLETION_PATTERNS = [
        r'\(\s*완결\s*\)',                  # (완결)
        r'\[\s*완결\s*\]',                  # [완결]
        r'\(\s*完\s*\)',                    # (完)
        r'\[\s*完\s*\]',                    # [完]
        r'\(\s*완\s*\)',                    # (완)
        r'\[\s*완\s*\]',                    # [완]
        r'(?<!\S)完(?!\S)',                 # 完 (독립된 문자)
        r'\(\s*Complete\s*\)',              # (Complete)
        r'\(\s*END\s*\)',                   # (END)
        r'\(\s*Fin\s*\)',                   # (Fin)
        r'본편\s*및\s*외전\s*完',            # 본편 및 외전 完
        r'본편\s*완결',                      # 본편 완결
    ]
    
    # 외전 마커 패턴
    SIDE_STORY_PATTERNS = [
        r'番外',                            # 번외
        r'외전',
        r'후기',
        r'에필로그',
        r'에필',
        r'특별편',
        r'번외편',
        r'스핀오프',
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
        # 노이즈 패턴 통합
        all_noise = self.AUTHOR_PATTERNS + self.SITE_PATTERNS + self.TRANSLATOR_PATTERNS
        self.noise_pattern = re.compile('|'.join(all_noise), re.IGNORECASE)
        
        # 장르 태그 패턴
        self.genre_tag_pattern = re.compile('|'.join(self.GENRE_TAG_PATTERNS), re.IGNORECASE)
        
        # 성인 등급 태그 패턴
        self.adult_tag_pattern = re.compile('|'.join(self.ADULT_TAG_PATTERNS), re.IGNORECASE)
        
        # 플랫폼/번역자 태그 패턴
        self.platform_tag_pattern = re.compile('|'.join(self.PLATFORM_TAG_PATTERNS), re.IGNORECASE)
        
        # 완결 마커 패턴
        self.completion_pattern = re.compile('|'.join(self.COMPLETION_PATTERNS), re.IGNORECASE)
        
        # 외전 마커 패턴 (+ 외전, + 에필 등)
        self.side_story_pattern = re.compile(
            r'\s*\+\s*(?:' + '|'.join(self.SIDE_STORY_PATTERNS) + r')[\s\d\-~,]*',
            re.IGNORECASE
        )
        
        # 범위 패턴 (1-536, 1~536, 1-536화, 1-536권)
        self.range_pattern = re.compile(r'(\d+)\s*[-~]\s*(\d+)\s*[화권부편회장]?')
        
        # 단일 숫자 패턴 (120, 126 등 - 끝에 있는 단일 숫자)
        self.single_number_pattern = re.compile(r'\s+(\d+)\s*$')
        
        # 저자 구분자 패턴 (제목 - 저자)
        self.author_separator_pattern = re.compile(r'\s+[-–—]\s+([^-–—]+)$')
    
    def extract(self, raw_name: str) -> TitleParseResult:
        """파일명에서 제목과 메타데이터 추출"""
        # 1. 확장자 분리
        name, extension = self._split_extension(raw_name)
        
        # 빈 이름 처리
        if not name:
            return TitleParseResult(title="", extension=extension)
        
        # 2. 노이즈 제거
        cleaned, author = self._remove_noise(name)
        
        # 3. 제목 앵커 추출
        title, residual = self._extract_title_anchor(cleaned)
        
        # 4. 잔여 문자열에서 메타데이터 파싱
        volume_info, range_info, is_completed, side_story = self._parse_residual(residual)
        
        return TitleParseResult(
            title=title.strip(),
            author=author.strip(),
            volume_info=volume_info,
            range_info=range_info,
            is_completed=is_completed,
            side_story=side_story,
            extension=extension
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
    
    def _remove_noise(self, name: str) -> Tuple[str, str]:
        """노이즈 제거 및 저자명 추출"""
        author = ""
        
        # 저자 구분자 패턴 확인 (제목 - 저자)
        author_match = self.author_separator_pattern.search(name)
        if author_match:
            potential_author = author_match.group(1).strip()
            if len(potential_author) < 20 and not re.search(r'\d{2,}', potential_author):
                author = potential_author
                name = name[:author_match.start()].strip()
        
        # 노이즈 패턴 제거
        name = self.noise_pattern.sub('', name)
        
        # 장르 태그 제거
        name = self.genre_tag_pattern.sub('', name)
        
        # 성인 등급 태그 제거
        name = self.adult_tag_pattern.sub('', name)
        
        # 플랫폼/번역자 태그 제거
        name = self.platform_tag_pattern.sub('', name)
        
        # 연속 공백 정리
        name = ' '.join(name.split())
        
        return name.strip(), author
    
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
        plus_match = re.search(r'\s+\+\s+(?:외전|에필|번외|특별편|番外)[\s\d\-~,]*', name)
        if plus_match:
            main_part = name[:plus_match.start()].strip()
            side_part = name[plus_match.start():].strip()
            title, residual = self._extract_title_from_main(main_part)
            residual = (residual + " " + side_part).strip()
            return title, residual
        
        return self._extract_title_from_main(name)
    
    def _extract_title_from_main(self, name: str) -> Tuple[str, str]:
        """메인 파트에서 제목 추출"""
        # 단독 숫자+단위 패턴 먼저 찾기 (1화, 50권, 1부 등) - 범위보다 먼저!
        unit_match = re.search(r'\s+\d+\s*[화권부편회장](?:\s|$)', name)
        if unit_match:
            title = name[:unit_match.start()].strip()
            residual = name[unit_match.start():].strip()
            return title, residual
        
        # 숫자 범위 패턴 찾기 (1-536, 1~100 등)
        range_match = re.search(r'\s+\d+\s*[-~]\s*\d+', name)
        if range_match:
            title = name[:range_match.start()].strip()
            residual = name[range_match.start():].strip()
            return title, residual
        
        # 단일 숫자 패턴 찾기 (120, 126 등 - 끝에 있는 단일 숫자)
        # 완결 마커 앞의 숫자도 포함 (예: "126 完")
        single_num_match = re.search(r'\s+(\d+)\s*(?:完|완|\(완\)|\(完\)|\s*$)', name)
        if single_num_match:
            title = name[:single_num_match.start()].strip()
            residual = name[single_num_match.start():].strip()
            return title, residual
        
        # 완결 마커 찾기 (괄호 형태 포함)
        # 먼저 괄호 형태의 완결 마커 확인 (제목 끝에 있는 경우)
        # 마침표 포함 패턴: "제목. (완)" 또는 "제목 (완)"
        paren_completion_match = re.search(r'\.?\s*[\(\[]\s*완(?:결)?\s*[\)\]]\.?\s*$', name)
        if paren_completion_match:
            title = name[:paren_completion_match.start()].strip()
            # 제목 끝의 마침표 제거
            title = title.rstrip('.')
            residual = name[paren_completion_match.start():].strip()
            return title, residual
        
        # 일반 완결 마커 찾기
        completion_match = self.completion_pattern.search(name)
        if completion_match:
            title = name[:completion_match.start()].strip()
            residual = name[completion_match.start():].strip()
            return title, residual
        
        # 패턴 없으면 전체가 제목
        return name.strip(), ""
    
    def _parse_residual(self, residual: str) -> Tuple[str, str, bool, str]:
        """잔여 문자열에서 메타데이터 파싱"""
        if not residual:
            return "", "", False, ""
        
        volume_info = ""
        range_info = ""
        is_completed = False
        side_story = ""
        
        # 1. 완결 여부 확인
        if self.completion_pattern.search(residual):
            is_completed = True
            residual = self.completion_pattern.sub('', residual)
        
        # 2. 외전 정보 추출
        side_match = self.side_story_pattern.search(residual)
        if side_match:
            side_story = self._normalize_side_story(side_match.group(0))
            residual = residual[:side_match.start()] + residual[side_match.end():]
        
        # 3. "본편 및 외전" 패턴 처리
        if re.search(r'본편\s*및\s*외전', residual):
            is_completed = True
            side_story = "외전"
            residual = re.sub(r'본편\s*및\s*외전[,\s]*', '', residual)
        
        # 4. "후기 포함" 패턴 처리
        if re.search(r'후기\s*포함', residual):
            residual = re.sub(r'[,\s]*후기\s*포함', '', residual)
        
        # 5. 부 정보 추출 (1-2부, 1부 등)
        volume_match = re.search(r'(\d+)\s*[-~]\s*(\d+)\s*부|(\d+)\s*부', residual)
        if volume_match:
            if volume_match.group(1) and volume_match.group(2):
                volume_info = f"{volume_match.group(1)}-{volume_match.group(2)}부"
            elif volume_match.group(3):
                volume_info = f"{volume_match.group(3)}부"
            residual = residual[:volume_match.start()] + residual[volume_match.end():]
        
        # 6. 범위 정보 추출 (1-536, 1-536화 등)
        range_match = self.range_pattern.search(residual)
        if range_match:
            start = range_match.group(1)
            end = range_match.group(2)
            range_info = f"{start}-{end}"
        else:
            # 단일 숫자 범위 (120, 126 등)
            single_match = re.search(r'(\d+)', residual)
            if single_match:
                num = single_match.group(1)
                # 3자리 이상 숫자만 범위로 인식 (1-999화 범위)
                if len(num) >= 2:
                    range_info = f"1-{num}"
        
        return volume_info, range_info, is_completed, side_story
    
    def _normalize_side_story(self, side_text: str) -> str:
        """외전 정보 정규화"""
        side_text = re.sub(r'^\s*\+\s*', '', side_text)
        for pattern in ['番外', '번외편', '번외']:
            side_text = re.sub(pattern, '외전', side_text, flags=re.IGNORECASE)
        side_text = re.sub(r'에필로그', '에필', side_text, flags=re.IGNORECASE)
        return side_text.strip()
    
    def format_normalized_filename(self, parse_result: TitleParseResult, genre: str = "") -> str:
        """정규화된 파일명 생성"""
        return parse_result.to_normalized_filename(genre)
