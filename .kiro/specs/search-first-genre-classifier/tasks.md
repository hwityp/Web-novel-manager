# Implementation Plan: Search-First Genre Classifier

## Overview

장르 분류 로직을 '검색 엔진 중심(Search-First Strategy)'으로 전면 개편합니다. 캐시 → 인터넷 검색 → 키워드 폴백 순서로 분류를 수행하며, 제목 유사도 검증과 외부 설정 파일을 통한 유지보수성 향상을 포함합니다.

## Tasks

- [x] 1. 설정 파일 생성
  - [x] 1.1 config/genre_mapping.json 생성
    - 플랫폼별 장르명 → 표준 장르명 매핑 규칙 정의
    - GENRE_WHITELIST 포함
    - _Requirements: 11.1, 11.4_
  - [x] 1.2 config/genre_cache.json 빈 구조 생성
    - 캐시 파일 초기 구조 정의
    - _Requirements: 9.1_

- [x] 2. 유틸리티 클래스 구현
  - [x] 2.1 core/utils/similarity.py - TitleSimilarityChecker 구현
    - Levenshtein Distance 알고리즘 구현
    - calculate_similarity() 메서드 구현
    - is_similar() 메서드 구현 (85% 임계값, 저자 일치 시 75%)
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  - [ ]* 2.2 Property test for TitleSimilarityChecker
    - **Property 8: Levenshtein Distance 유사도 계산**
    - **Property 9: 유사도 임계값에 따른 결과 채택/무시**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
  - [x] 2.3 core/utils/genre_mapping.py - GenreMappingLoader 구현
    - config/genre_mapping.json 로드
    - map_genre() 메서드 구현
    - is_valid_genre() 메서드 구현
    - 파일 로드 실패 시 기본 매핑 사용
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.3_
  - [ ]* 2.4 Property test for GenreMappingLoader
    - **Property 4: 플랫폼 장르 → 표준 장르 매핑**
    - **Property 5: 화이트리스트 검증**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
  - [x] 2.5 core/utils/genre_cache.py - GenreCache 구현
    - config/genre_cache.json 로드/저장
    - get() 메서드 구현
    - set() 메서드 구현
    - save() 메서드 구현
    - _Requirements: 9.1, 9.2, 9.4_
  - [ ]* 2.6 Property test for GenreCache
    - **Property 7: 캐시 저장 및 조회**
    - **Validates: Requirements 9.2, 9.4**

- [x] 3. 메인 어댑터 개편
  - [x] 3.1 core/adapters/genre_classifier_adapter.py를 SearchFirstClassifierAdapter로 개편
    - 기존 GenreClassifierAdapter 코드를 SearchFirstClassifierAdapter로 리팩토링
    - classify() 메서드에 3단계 전략 구현 (캐시 → 검색 → 폴백)
    - classify_batch() 메서드 구현
    - close() 메서드에 캐시 저장 추가
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.2, 5.3, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 8.4_
  - [ ]* 3.2 Property test for SearchFirstClassifierAdapter
    - **Property 1: 노이즈 제거 후 순수 제목 추출**
    - **Property 6: classify 메서드 필드 업데이트**
    - **Validates: Requirements 1.2, 1.3, 1.4, 8.4**
  - [x] 3.3 플랫폼 우선순위 및 제목 유사도 검증 통합
    - 기존 NaverGenreExtractorV4와 통합
    - 플랫폼 우선순위에 따른 장르 선택
    - TitleSimilarityChecker를 사용한 유사도 검증
    - _Requirements: 4.1, 4.3, 10.2, 10.3, 10.4_
  - [ ]* 3.4 Property test for 플랫폼 우선순위
    - **Property 2: 플랫폼 우선순위에 따른 장르 선택**
    - **Property 3: 장르 세분화 선택**
    - **Validates: Requirements 4.1, 4.3**

- [x] 4. Checkpoint - 유틸리티 및 어댑터 테스트
  - 22개 단위 테스트 통과 (2025-12-28)
  - TitleSimilarityChecker: 8개 테스트 통과
  - GenreMappingLoader: 7개 테스트 통과
  - GenreCache: 5개 테스트 통과
  - SearchFirstClassifierIntegration: 2개 테스트 통과

- [x] 5. 통합 테스트 및 검증
  - [x] 5.1 tests/test_search_first_classifier.py 생성
    - Hypothesis 기반 property tests
    - 단위 테스트
    - _Requirements: 12.1, 12.2, 12.3_
  - [x] 5.2 실제 제목 분류 테스트 수행
    - '100층의 올마스터' 분류 테스트
    - '1588 샤인머스캣으로 귀농 왔더니 신대륙' 분류 테스트
    - 결과 보고
    - _Requirements: 12.1, 12.2, 12.3_

- [x] 6. Final checkpoint - 전체 테스트 및 결과 보고
  - 22개 단위 테스트 통과 (2025-12-28)
  - 실제 분류 테스트 결과:
    - '100층의 올마스터' → 판타지 (high, 카카오페이지)
    - '1588 샤인머스캣으로 귀농 왔더니 신대륙' → 역사 (high, 문피아)
    - '나 혼자만 레벨업' → 퓨판 (medium, 캐시)
    - '전지적 독자 시점' → 현판 (high, 문피아)
    - '화산귀환' → 무협 (medium, 캐시)
  - 기존 대비 개선: 유명 작품들이 더 이상 '미분류'로 처리되지 않음
  - 검색 성공 시 high 신뢰도, 키워드 폴백 시 medium 신뢰도 부여

- [x] 7. 실제 웹 검색 통합 (2025-12-28)
  - [x] 7.1 NaverGenreExtractorV4 직접 통합
    - subprocess 방식에서 직접 import 방식으로 변경
    - 실제 네이버 웹 크롤링 수행
    - 플랫폼별 장르 추출기 활용
  - [x] 7.2 플랫폼 우선순위 적용 확인
    - 리디북스 > 문피아 > 네이버시리즈 > 카카오페이지 > 소설넷 > 노벨피아 > 조아라 > 웹툰가이드 > 미스터블루 > 교보문고 > YES24 > 알라딘
  - [x] 7.3 실제 검색 테스트 결과 (2025-12-28)
    - '100층의 올마스터' → 판타지 (90%, 카카오페이지_tag)
      - 네이버 웹 크롤링으로 303개 링크 발견
      - 네이버시리즈, 카카오페이지, 웹툰가이드 링크 추출
    - '120kg 돼지는 먹방이 너무 쉽다' → 현판 (92%, 문피아_meta_path)
      - 네이버 웹 크롤링으로 302개 링크 발견
      - 문피아, 노벨피아, 네이버시리즈, 카카오페이지, 소설넷, 미스터블루 링크 추출
      - 문피아에서 '현대판타지' → '현판' 장르 추출

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
