"""
==============================================================================
파일: core/utils/content_header_extractor.py
역할 및 목적:
    소설 텍스트 파일(.txt)의 앞부분(2~4KB, 헤더/시놉시스)을 초고속 스트리밍으로 읽어,
    번역본 및 원문 소설의 메타데이터(장르, 카테고리, 태그, 작품 소개)를 추출하는 유틸리티.
    국내 포털 검색으로 찾기 어려운 해외(중국/일본) 웹소설 및 AI 번역작의 장르를 높은 정확도로 판정합니다.
주요 구성 요소:
    - ContentHeaderResult: 추출 결과 데이터클래스 (raw_genre, tags, snippet)
    - ContentHeaderGenreExtractor: 파일 헤더 스트리밍 리더 및 장르/태그 파서
상호 연관 관계 및 의존성:
    - Caller: core.adapters.genre_classifier_adapter.GenreClassifierAdapter
    - Callee: pathlib.Path, re
수정 시 주의사항:
    - 파일 전체를 메모리에 올리지 않고, 최대 MAX_READ_BYTES(4KB)만 바이너리로 읽은 후 디코딩하여
      수백 MB 크기의 텍스트 파일도 1~2ms 이내에 안전하게 처리해야 합니다.
    - 다중 인코딩(UTF-8, UTF-8-sig, CP949, GB18030, Shift-JIS)을 순차적으로 시도하여 디코딩 에러를 방지합니다.
==============================================================================
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
import re


@dataclass
class ContentHeaderResult:
    """본문 헤더 메타데이터 추출 결과"""
    raw_genre: str = ""                # 감지된 원시 장르명 (예: "선협", "仙侠", "고전 로맨스")
    tags: List[str] = field(default_factory=list)  # 추출된 태그 목록 (예: ["수진", "시스템"])
    snippet: str = ""                  # 시놉시스/작품소개 텍스트
    translated_title: str = ""         # 본문 도입부에서 발견된 번역본/원문 책 제목
    is_foreign: bool = False           # CJK(중/일) 메타데이터 여부
    has_explicit_synopsis: bool = False # 명시적 작품소개 블록 존재 여부


class ContentHeaderGenreExtractor:
    """텍스트 파일 도입부 스니펫 장르 및 메타데이터 추출기"""

    # 헤더 분석을 위해 읽을 최대 바이트 수 (약 4KB, 40~100줄 분량)
    MAX_READ_BYTES = 4096

    # 시도할 텍스트 인코딩 목록 (한국어/중국어/일본어/유니코드 전반)
    CANDIDATE_ENCODINGS = [
        "utf-8",
        "utf-8-sig",
        "cp949",
        "euc-kr",
        "gb18030",   # 중국어 간체/번체
        "shift_jis", # 일본어
    ]

    # 명시적 번역본/원문 책 제목 패턴 (헤더 도입부 1~3줄)
    TRANSLATED_TITLE_PATTERNS = [
        re.compile(r'《([^》\r\n]{2,80})》'),
        re.compile(r'〈([^〉\r\n]{2,80})〉'),
        re.compile(r'『([^』\r\n]{2,80})』'),
        re.compile(r'^[#＃]\s*([^\r\n]{2,80})', re.MULTILINE),
        re.compile(r'^(?:서명|책\s*제목|원제|제목)\s*[:：\-]\s*([^\r\n]{2,80})', re.MULTILINE),
        re.compile(r'^([가-힣\w\s:,\!\?]{2,80})》', re.MULTILINE),
    ]

    # 괄호형 장르/카테고리 태그 패턴 (예: [고전 로맨스], [고장미정], 【연대물+공간+빙의】, (천월중생))
    BRACKET_GENRE_PATTERNS = [
        re.compile(r'\[([가-힣\s]{2,15})(?:\([^\)]*\))?\]'),
        re.compile(r'【([가-힣\s\+]{2,30})(?:\([^\)]*\))?】'),
        re.compile(r'\(([가-힣\s]{2,15})\)'),
    ]

    # 제외할 비장르 단어 목록
    NON_GENRE_WORDS = {
        '제1장', '완결', '단독', '텍본', '외전', '공지', '19금', '19N', '성인',
        '미완', '번역', 'AI번역', '수정', '개정판', '합본', '단편', '스포', '후기'
    }

    # 명시적 장르/카테고리 라인 패턴
    GENRE_LINE_PATTERNS = [
        # 한국어 패턴: 장르: 선협, [장르] 판타지, 【장르】 언정, 카테고리: 무협
        re.compile(r'^(?:\[장르\]|【장르】|장르|카테고리|분류)\s*[:：]?\s*([^\r\n\[\]【】]{1,30})', re.IGNORECASE | re.MULTILINE),
        # 중국어 패턴: 【作品类型】 仙侠, 类型: 言情, 分类: 玄幻, 作品类型: 仙侠
        re.compile(r'^(?:【作品类型】|【分类】|作品类型|类型|分类|题材)\s*[:：]?\s*([^\r\n\[\]【】]{1,30})', re.IGNORECASE | re.MULTILINE),
        # 일본어 패턴: 【ジャンル】 ハイファンタジー, ジャンル: 恋愛
        re.compile(r'^(?:【ジャンル】|ジャンル|カテゴリー)\s*[:：]?\s*([^\r\n\[\]【】]{1,30})', re.IGNORECASE | re.MULTILINE),
    ]

    # 태그 목록 라인 패턴 (예: 태그: #선협 #수진 / 【태그】 회귀, 빙의 / 【标签】 穿越 农家)
    TAG_LINE_PATTERNS = [
        re.compile(r'^(?:\[태그\]|【태그】|【タグ】|【标签】|【作品标签】|태그|키워드|タグ|キーワード|标签|作品标签)\s*[:：]?\s*([^\r\n]+)', re.IGNORECASE | re.MULTILINE),
    ]

    # 작품 소개 블록 헤더 패턴
    SYNOPSIS_HEADER_PATTERNS = [
        re.compile(r'(?:【작품\s*소개】|【내용\s*소개】|【줄거리】|【시놉시스】|【문안】|【内容简介】|【作品简介】|【简介】|【あらすじ】|책\s*소개\s*[:：]?|작품\s*소개\s*[:：]?|줄거리\s*[:：]?|문안\s*[:：]?|소개\s*[:：]?)(.*?)(?:(?=【|\n\s*\n\s*\n)|$)', re.DOTALL),
    ]

    @classmethod
    def read_header_text(cls, file_path: Path) -> Optional[str]:
        """
        파일의 앞부분 MAX_READ_BYTES를 안전하게 읽어 문자열로 디코딩
        """
        if not file_path or not file_path.exists() or not file_path.is_file():
            return None

        # .txt 파일이 아닌 경우 건너뜀
        if file_path.suffix.lower() != '.txt':
            return None

        try:
            with open(file_path, 'rb') as f:
                raw_bytes = f.read(cls.MAX_READ_BYTES)
        except Exception:
            return None

        if not raw_bytes:
            return None

        for encoding in cls.CANDIDATE_ENCODINGS:
            # 멀티바이트 문자 중간에서 MAX_READ_BYTES가 잘렸을 수 있으므로 0~4바이트를 잘라내며 디코딩 시도
            for trim in range(0, 5):
                chunk = raw_bytes if trim == 0 else raw_bytes[:-trim]
                try:
                    text = chunk.decode(encoding)
                    return text
                except (UnicodeDecodeError, LookupError):
                    continue

        # 모든 표준 디코딩 실패 시 utf-8 replace 모드로 디코딩
        try:
            return raw_bytes.decode('utf-8', errors='replace')
        except Exception:
            return None

    @classmethod
    def extract_from_text(cls, header_text: str) -> Optional[ContentHeaderResult]:
        """
        도입부 텍스트에서 번역 제목, 장르, 태그 및 시놉시스 메타데이터 분석
        """
        if not header_text or not header_text.strip():
            return None

        result = ContentHeaderResult()
        header_head = header_text[:800]

        # 0. 번역본/원문 책 제목 탐색 (도입부 800자)
        for t_pat in cls.TRANSLATED_TITLE_PATTERNS:
            t_match = t_pat.search(header_head)
            if t_match:
                cand_title = t_match.group(1).strip()
                # 괄호나 잡음 제거
                cand_title = re.sub(r'[\r\n]+', ' ', cand_title).strip()
                if len(cand_title) >= 2 and not any(nw in cand_title for nw in ['제1장', '완결', '다운로드']):
                    result.translated_title = cand_title
                    break

        # 0-1. 명시적 패턴으로 번역제목이 없으면, 도입부 첫 번째 유효 라인 확인 (단순 제목형 라인)
        if not result.translated_title:
            cand_lines = [l.strip() for l in header_head.splitlines() if l.strip()]
            if cand_lines:
                first_l = cand_lines[0]
                # 제목 느낌의 3~40자 라인 (특수태그/안내문/제1장 등 제외)
                if 2 <= len(first_l) <= 40 and not any(nw in first_l for nw in ['제1장', '1장', '프롤로그', 'prologue', 'http', '다운로드', 'Episode', 'EP.', '==', '작가의 말', '공지']):
                    if not first_l.startswith(('【', '[', '(', '#', '!', '?', '*')):
                        result.translated_title = first_l

        # 1. 명시적 장르 라인 탐색 (예: 장르: 선협)
        for pattern in cls.GENRE_LINE_PATTERNS:
            match = pattern.search(header_text)
            if match:
                raw_genre = match.group(1).strip()
                parts = [p.strip() for p in re.split(r'[,/|·\s]+', raw_genre) if p.strip()]
                if parts:
                    result.raw_genre = parts[0]
                    if len(parts) > 1:
                        result.tags.extend(parts[1:])
                break

        # 2. 괄호형 장르/카테고리 탐색 (예: [고전 로맨스], [고장미정], (천월중생))
        if not result.raw_genre:
            for b_pat in cls.BRACKET_GENRE_PATTERNS:
                for match in b_pat.finditer(header_head):
                    cand = match.group(1).strip()
                    if cand and cand not in cls.NON_GENRE_WORDS:
                        # 복합 태그인 경우 '+' 구분 처리
                        if '+' in cand:
                            sub_parts = [sp.strip() for sp in cand.split('+') if sp.strip()]
                            if sub_parts:
                                result.raw_genre = sub_parts[0]
                                result.tags.extend(sub_parts[1:])
                                break
                        else:
                            result.raw_genre = cand
                            break
                if result.raw_genre:
                    break

        # 3. 태그 라인 탐색
        for tag_pattern in cls.TAG_LINE_PATTERNS:
            tag_match = tag_pattern.search(header_text)
            if tag_match:
                tag_content = tag_match.group(1).strip()
                raw_tags = re.findall(r'#?([^\s,#|/]+)', tag_content)
                for t in raw_tags:
                    t_clean = t.strip()
                    if t_clean and t_clean not in result.tags and t_clean not in cls.NON_GENRE_WORDS:
                        result.tags.append(t_clean)

        # 4. 작품 소개(시놉시스) 블록 추출
        for syn_pattern in cls.SYNOPSIS_HEADER_PATTERNS:
            syn_match = syn_pattern.search(header_text)
            if syn_match:
                result.snippet = syn_match.group(1).strip()[:600]
                result.has_explicit_synopsis = True
                break

        # 5. 시놉시스가 아직 없고 헤더 전체가 짧다면 앞 400자를 스니펫으로 설정
        if not result.snippet:
            clean_lines = [l.strip() for l in header_text.splitlines() if l.strip()]
            result.snippet = " ".join(clean_lines[:12])[:400]
            result.has_explicit_synopsis = False

        # 6. CJK 문자 포함 여부 확인
        all_text = f"{result.raw_genre} {' '.join(result.tags)} {result.translated_title}"
        if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]', all_text):
            result.is_foreign = True

        # 장르, 태그, 번역제목, 시놉시스 중 하나라도 존재하면 유의미한 결과 반환
        if result.raw_genre or result.tags or result.translated_title or result.snippet:
            return result

        return None

    @classmethod
    def extract_from_file(cls, file_path: Path) -> Optional[ContentHeaderResult]:
        """
        파일 경로로부터 직접 헤더 메타데이터를 추출
        """
        header_text = cls.read_header_text(file_path)
        if not header_text:
            return None
        return cls.extract_from_text(header_text)
