"""
==============================================================================
파일: core/utils/auto_keyword_learner.py
역할 및 목적:
    인터넷 검색 결과(Search-First)로부터 고신뢰도로 판정된 소설의 제목, 음독,
    웹 태그, 시놉시스 등에서 신규 장르 키워드를 안전 가드레일을 거쳐 자동 추출하고,
    원자적 동기화기(KeywordSyncer)를 통해 사전에 실시간 등록하는 자동 학습 모듈.
주요 구성 요소:
    - AutoKeywordLearner: 안전 가드레일 기반 자동 키워드 마이닝 및 사전 동기화 엔진
==============================================================================
"""
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime

from config.pipeline_config import GENRE_WHITELIST
from core.novel_task import NovelTask
from core.utils.keyword_syncer import KeywordSyncer, SyncResult
from core.utils.genre_cache_miner import GenreCacheMiner


class AutoKeywordLearner:
    """인터넷 검색 결과 기반 사전 자동 학습 및 동기화 엔진"""

    # 장르 구분이 모호하여 단독 장르 키워드로 등록하면 오분류를 유발하는 일반 명사, 어미 및 동사류
    GENERIC_EXCLUSIONS: Set[str] = {
        '소설', '웹소설', '이야기', '주인공', '이야기들', '시작', '다시',
        '회귀', '환생', '빙의', '전생', '이세계', '차원', '시스템',
        '막내', '아들', '황제', '대공', '공작', '영애', '황녀', '왕자', '공녀',
        '천재', '재벌', '막내아들', '매니저', '플레이어', '헌터', '각성',
        '전문가', '마스터', '레벨업', '로그인', '퀘스트', '랭커',
        '어느날', '모든것', '하루', '세계', '사람', '인생', '역대급',
        '최강', '만렙', '천마', '신선', '도사', '검성', '마법사',
        '보고', '하세요', '알아서', '않을', '앞의', '되었다', '본편', '외전', '완결', '파일', '임의', '테스트'
    }

    # 한국어 조사 접미사 제거용 정규식
    JOSA_REGEX = re.compile(r'(?:으로|에서|부터|까지|하고|이며|이라|라는|처럼|보다|의|을|를|은|는|이|가|에|과|와|로|들)$')

    # 단어 분리 정규식
    WORD_REGEX = re.compile(r'[가-힣a-zA-Z0-9]+')

    # CJK 괄호 태그 정규식: (我真没想...), [乱世书] 등
    CJK_BRACKET_REGEX = re.compile(r'[\(\[\{]([\u4e00-\u9fff\u3400-\u4dbf]+)[\)\]\}]')

    def __init__(self, syncer: Optional[KeywordSyncer] = None):
        self.syncer = syncer or KeywordSyncer()
        self.stopwords = set(GenreCacheMiner.DEFAULT_STOPWORDS) | self.GENERIC_EXCLUSIONS

    def _strip_josa(self, word: str) -> str:
        """단어 끝의 조사 제거 (예: '수선자의' -> '수선자')"""
        if len(word) >= 3:
            stripped = self.JOSA_REGEX.sub('', word)
            if len(stripped) >= 2:
                return stripped
        return word

    def extract_candidates(
        self,
        title: str,
        target_genre: str,
        phonetic_title: str = "",
        translated_title: str = "",
        foreign_title: str = "",
        web_tags: Optional[List[str]] = None
    ) -> List[Tuple[str, int, str]]:
        """
        주어진 텍스트로부터 안전 가드레일을 통과한 키워드 후보 추출
        
        Returns:
            List[Tuple[keyword, suggested_weight, source_type]]
        """
        candidates: List[Tuple[str, int, str]] = []
        seen_words: Set[str] = set()

        # 1. CJK 원문-음독 쌍 추출 (품질 최우선)
        all_text_for_cjk = f"{title} {foreign_title}".strip()
        cjk_matches = self.CJK_BRACKET_REGEX.findall(all_text_for_cjk)
        for cjk in cjk_matches:
            # 괄호 앞의 한글 단어 추출
            before_cjk = all_text_for_cjk.split(cjk)[0].rstrip('([<{ ')
            korean_words = self.WORD_REGEX.findall(before_cjk)
            if korean_words:
                hangul = korean_words[-1]
                if len(hangul) >= 2 and hangul not in self.stopwords and hangul not in seen_words:
                    candidates.append((hangul, 2, 'cjk_pair'))
                    seen_words.add(hangul)
            # CJK 자체(2~4자 한자)도 선협/언정 등에서 중요한 키워드
            if 2 <= len(cjk) <= 4 and cjk not in seen_words:
                candidates.append((cjk, 2, 'cjk_char'))
                seen_words.add(cjk)

        # 2. 웹 태그(web_tags) 중 의미 있는 서브장르 태그 발굴
        if web_tags:
            for tag in web_tags:
                clean_tag = self._strip_josa(tag.strip().replace('#', ''))
                if 2 <= len(clean_tag) <= 6 and clean_tag not in self.stopwords and clean_tag not in seen_words:
                    # 순수 숫자는 배제
                    if not clean_tag.isdigit():
                        candidates.append((clean_tag, 2, 'web_tag'))
                        seen_words.add(clean_tag)

        # 3. 제목 및 음독 제목 내 단어 분석
        combined_title = f"{title} {phonetic_title} {translated_title}"
        cleaned = self.CJK_BRACKET_REGEX.sub('', combined_title)
        words = self.WORD_REGEX.findall(cleaned)

        for w in words:
            clean_w = self._strip_josa(w.strip())
            # 길이 가드레일: 2글자 이상 6글자 이하
            if len(clean_w) < 2 or len(clean_w) > 6:
                continue
            # 숫자가 포함된 단어(예: 123화, 1권, 2기 등) 또는 불용어 제외
            if any(char.isdigit() for char in clean_w) or clean_w in self.stopwords or clean_w in seen_words:
                continue
            
            # 음독 또는 고유명사성 어휘 기본 가중치 1
            candidates.append((clean_w, 1, 'ngram'))
            seen_words.add(clean_w)

        return candidates

    def learn_from_task(
        self,
        task: NovelTask,
        search_result: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        검색 성공한 NovelTask로부터 키워드를 안전하게 학습하고 사전에 동기화.
        
        Args:
            task: 분류 완료된 NovelTask
            search_result: 검색 결과 딕셔너리 (옵션)
            
        Returns:
            List[str]: 성공적으로 신규 등록된 키워드 목록
        """
        # [가드레일 1] 신뢰도 및 장르 유효성 검증
        if task.confidence != 'high' or not task.genre or task.genre == '미분류':
            return []

        primary_genre = task.genre.split(',')[0].strip()
        if primary_genre not in GENRE_WHITELIST or primary_genre == '미분류':
            return []

        # 원문 제목 및 메타데이터 준비
        pure_title = task.title if task.title else task.raw_name
        phonetic_title = task.metadata.get('phonetic_title', '')
        translated_title = task.metadata.get('translated_title', '')
        foreign_title = task.metadata.get('original_foreign_title', '')
        web_tags = search_result.get('tags', []) if search_result else []

        candidates = self.extract_candidates(
            title=pure_title,
            target_genre=primary_genre,
            phonetic_title=phonetic_title,
            translated_title=translated_title,
            foreign_title=foreign_title,
            web_tags=web_tags
        )

        if not candidates:
            return []

        # [가드레일 2] 기존 사전 데이터 로드 및 중복/충돌 검증
        master_data, err = self.syncer.load_master_data()
        if not master_data or err:
            return []

        single_keywords = master_data.setdefault("single_keywords", {})
        target_genre_dict = single_keywords.setdefault(primary_genre, {})
        auto_learned = master_data.setdefault("auto_learned_keywords", {})

        # 모든 장르에 걸친 기존 키워드 집합 생성 (장르 간 충돌 방지)
        all_existing_kws: Dict[str, str] = {}
        for g, kw_dict in single_keywords.items():
            for k in kw_dict:
                all_existing_kws[k.lower()] = g

        newly_learned: List[str] = []
        today_str = datetime.now().strftime("%Y-%m-%d")

        for kw, weight, src_type in candidates:
            kw_lower = kw.lower()

            # 이미 어떤 장르든 등록되어 있으면 자동 등록하지 않음 (오염 및 충돌 방지)
            if kw_lower in all_existing_kws:
                continue

            # 신규 등록
            target_genre_dict[kw] = weight
            all_existing_kws[kw_lower] = primary_genre
            newly_learned.append(kw)

            # 자동 학습 메타데이터 기록 (GUI에서 수작업 확인 및 편집 용도)
            auto_learned[kw] = {
                "genre": primary_genre,
                "weight": weight,
                "source_type": src_type,
                "title": pure_title,
                "learned_at": today_str
            }

        # 신규 추가된 키워드가 있는 경우에만 파일 저장 및 동기화 수행
        if newly_learned:
            backup_files = self.syncer.backup_files()
            master_data["last_updated"] = today_str
            master_data["version"] = self.syncer._bump_version(master_data.get("version", "1.6.0"))

            sync_res = self.syncer._save_and_sync(
                master_data=master_data,
                backup_files=backup_files,
                added_count=len(newly_learned),
                updated_count=0,
                run_regression_test=False
            )
            if not sync_res.success:
                return []

        return newly_learned
