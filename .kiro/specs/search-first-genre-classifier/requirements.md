# Requirements Document

## Introduction

이 문서는 장르 분류 로직을 '검색 엔진 중심(Search-First Strategy)'으로 전면 개편하기 위한 요구사항을 정의합니다. 현재 시스템에서 유명 작품들이 '미분류'로 처리되는 심각한 로직 결함을 해결하고, 인터넷 검색을 최우선으로 활용하여 분류 정확도를 대폭 향상시킵니다.

## Glossary

- **Search_First_Classifier**: 검색 엔진 중심의 새로운 장르 분류 어댑터
- **TitleAnchorExtractor**: 파일명에서 순수 제목을 추출하는 기존 모듈
- **Platform_Extractor**: 각 웹소설 플랫폼에서 장르 정보를 추출하는 모듈
- **GENRE_WHITELIST**: 시스템에서 허용하는 표준 장르 목록 (현판, 퓨판, 무협, 로판, 겜판, 판타지, SF, 역사, 선협, 언정, 스포츠, 소설, 미분류)
- **Platform_Priority**: 플랫폼 우선순위 (리디북스 > 문피아 > 네이버시리즈 > 카카오페이지 > 소설넷 > 노벨피아 > 조아라 > 웹툰가이드 > 미스터블루 > 교보문고 > YES24 > 알라딘)
- **Confidence_Level**: 분류 신뢰도 수준 (high, medium, low)
- **Title_Noise**: 제목에 포함된 불필요한 정보 (1-100화, 완결, 저자명 등)

## Requirements

### Requirement 1: 검색 쿼리 최적화

**User Story:** As a 사용자, I want 파일명에서 노이즈가 제거된 순수 제목으로 검색이 수행되기를, so that 검색 정확도가 향상됩니다.

#### Acceptance Criteria

1. WHEN 장르 분류가 시작되면, THE Search_First_Classifier SHALL TitleAnchorExtractor를 사용하여 순수 제목을 추출한다
2. WHEN 제목에 '1-100화', '완결', '(완)', '[완결]' 등의 패턴이 포함되어 있으면, THE Search_First_Classifier SHALL 해당 패턴을 제거한 순수 제목만 검색어로 사용한다
3. WHEN 제목에 저자명(@저자, 저자: 이름 등)이 포함되어 있으면, THE Search_First_Classifier SHALL 저자명을 분리하여 별도로 저장하고 순수 제목만 검색어로 사용한다
4. WHEN 제목에 장르 태그([판타지], [무협] 등)가 포함되어 있으면, THE Search_First_Classifier SHALL 해당 태그를 제거한 순수 제목만 검색어로 사용한다

### Requirement 2: 3단계 분류 전략 (Search-First Strategy)

**User Story:** As a 사용자, I want 인터넷 검색이 최우선으로 수행되고 키워드 매칭은 최후의 수단으로만 사용되기를, so that 유명 작품들이 정확하게 분류됩니다.

#### Acceptance Criteria

1. THE Search_First_Classifier SHALL Stage 1(인터넷 검색) → Stage 2(플랫폼 우선순위 적용) → Stage 3(로컬 키워드 폴백) 순서로 분류를 수행한다
2. WHEN Stage 1에서 검색 결과가 발견되면, THE Search_First_Classifier SHALL Stage 3(키워드 매칭)을 건너뛰고 검색 결과를 사용한다
3. WHEN Stage 1과 Stage 2에서 장르를 찾지 못한 경우에만, THE Search_First_Classifier SHALL Stage 3(로컬 키워드 폴백)을 수행한다

### Requirement 3: Stage 1 - 인터넷 검색 수행

**User Story:** As a 사용자, I want 순수 제목으로 구글/네이버 검색 및 웹소설 플랫폼 검색이 수행되기를, so that 플랫폼에 등록된 작품의 장르 정보를 가져올 수 있습니다.

#### Acceptance Criteria

1. WHEN 순수 제목이 추출되면, THE Search_First_Classifier SHALL 네이버 검색 API 또는 웹 크롤링을 통해 검색을 수행한다
2. WHEN 검색 결과에서 플랫폼 링크가 발견되면, THE Search_First_Classifier SHALL 해당 플랫폼 페이지에서 장르 정보를 추출한다
3. WHEN 검색 결과가 없거나 플랫폼 링크가 없으면, THE Search_First_Classifier SHALL 검색 실패로 처리하고 다음 단계로 진행한다

### Requirement 4: Stage 2 - 플랫폼 우선순위 적용

**User Story:** As a 사용자, I want 여러 플랫폼에서 장르 정보가 발견될 때 신뢰도 높은 플랫폼의 정보가 우선 채택되기를, so that 가장 정확한 장르 정보를 얻을 수 있습니다.

#### Acceptance Criteria

1. WHEN 여러 플랫폼에서 장르 정보가 발견되면, THE Search_First_Classifier SHALL 다음 우선순위에 따라 정보를 채택한다: 리디북스 > 문피아 > 네이버시리즈 > 카카오페이지 > 소설넷 > 노벨피아 > 조아라 > 웹툰가이드 > 미스터블루 > 교보문고 > YES24 > 알라딘
2. WHEN 상위 우선순위 플랫폼에서 장르를 찾으면, THE Search_First_Classifier SHALL 하위 플랫폼 검색을 중단하고 해당 장르를 사용한다
3. WHEN 동일 플랫폼에서 여러 장르가 발견되면, THE Search_First_Classifier SHALL 더 세분화된 장르를 선택한다 (예: 판타지보다 퓨판 우선)

### Requirement 5: Stage 3 - 로컬 키워드 폴백

**User Story:** As a 사용자, I want 인터넷 검색이 실패했을 때만 키워드 매칭이 수행되기를, so that 검색되지 않는 작품도 분류될 수 있습니다.

#### Acceptance Criteria

1. WHEN Stage 1과 Stage 2에서 장르를 찾지 못하면, THE Search_First_Classifier SHALL genre_keywords.json을 이용한 키워드 매칭을 수행한다
2. WHEN 키워드 매칭이 수행되면, THE Search_First_Classifier SHALL 기존 GenreClassifier의 로직을 사용한다
3. WHEN 키워드 매칭도 실패하면, THE Search_First_Classifier SHALL 장르를 '미분류'로 설정한다

### Requirement 6: 플랫폼 장르 → 표준 장르 매핑

**User Story:** As a 사용자, I want 각 플랫폼의 장르명이 시스템의 표준 장르명으로 자동 변환되기를, so that 일관된 장르 분류 결과를 얻을 수 있습니다.

#### Acceptance Criteria

1. WHEN 플랫폼에서 '로맨스 판타지', '로맨스판타지' 장르가 추출되면, THE Search_First_Classifier SHALL '로판'으로 매핑한다
2. WHEN 플랫폼에서 '현대판타지', '현대 판타지', '현대물' 장르가 추출되면, THE Search_First_Classifier SHALL '현판'으로 매핑한다
3. WHEN 플랫폼에서 '퓨전판타지', '퓨전 판타지', '퓨전물' 장르가 추출되면, THE Search_First_Classifier SHALL '퓨판'으로 매핑한다
4. WHEN 플랫폼에서 '게임판타지', '게임 판타지' 장르가 추출되면, THE Search_First_Classifier SHALL '겜판'으로 매핑한다
5. WHEN 매핑된 장르가 GENRE_WHITELIST에 없으면, THE Search_First_Classifier SHALL '미분류'로 설정한다

### Requirement 7: 신뢰도(Confidence) 설정

**User Story:** As a 사용자, I want 분류 방법에 따라 신뢰도가 적절히 설정되기를, so that 분류 결과의 신뢰성을 파악할 수 있습니다.

#### Acceptance Criteria

1. WHEN 인터넷 검색으로 장르를 찾으면, THE Search_First_Classifier SHALL confidence를 'high'로 설정한다
2. WHEN 인터넷 검색 실패 후 키워드 매칭으로 장르를 찾으면, THE Search_First_Classifier SHALL confidence를 'medium'으로 설정한다
3. WHEN 모든 방법이 실패하여 '미분류'가 되면, THE Search_First_Classifier SHALL confidence를 'low'로 설정한다

### Requirement 8: 기존 어댑터 인터페이스 호환성

**User Story:** As a 개발자, I want 새로운 분류기가 기존 GenreClassifierAdapter와 동일한 인터페이스를 제공하기를, so that 파이프라인 코드 변경 없이 교체할 수 있습니다.

#### Acceptance Criteria

1. THE Search_First_Classifier SHALL classify(task: NovelTask) -> NovelTask 메서드를 제공한다
2. THE Search_First_Classifier SHALL classify_batch(tasks: List[NovelTask]) -> List[NovelTask] 메서드를 제공한다
3. THE Search_First_Classifier SHALL close() 메서드를 제공하여 리소스를 정리한다
4. WHEN classify 메서드가 호출되면, THE Search_First_Classifier SHALL task.genre, task.confidence, task.status를 업데이트하여 반환한다

### Requirement 9: 검색 결과 캐싱 (Performance)

**User Story:** As a 사용자, I want 동일한 제목에 대한 반복 검색이 방지되기를, so that 분류 성능이 향상됩니다.

#### Acceptance Criteria

1. THE Search_First_Classifier SHALL 'config/genre_cache.json' 파일을 사용하여 검색 결과를 캐싱한다
2. WHEN 검색이 성공하면, THE Search_First_Classifier SHALL 제목(Key)과 장르/신뢰도/소스(Value)를 캐시에 저장한다
3. WHEN 새로운 분류 요청이 들어오면, THE Search_First_Classifier SHALL 인터넷 검색보다 캐시 확인을 최우선으로 수행한다
4. WHEN 캐시에 해당 제목이 존재하면, THE Search_First_Classifier SHALL 캐시된 결과를 즉시 반환하고 인터넷 검색을 건너뛴다

### Requirement 10: 제목 유사도 검증 (Accuracy)

**User Story:** As a 사용자, I want 검색 결과의 작품명이 원본 제목과 충분히 유사한지 검증되기를, so that 잘못된 작품의 장르가 채택되지 않습니다.

#### Acceptance Criteria

1. WHEN 플랫폼에서 작품 정보를 추출하면, THE Search_First_Classifier SHALL Levenshtein Distance 알고리즘으로 제목 유사도를 측정한다
2. WHEN 제목 유사도가 85% 이상이면, THE Search_First_Classifier SHALL 해당 장르 정보를 채택한다
3. WHEN 제목 유사도가 85% 미만이면, THE Search_First_Classifier SHALL 해당 결과를 무시하고 다음 플랫폼을 확인한다
4. WHEN 저자명이 일치하면, THE Search_First_Classifier SHALL 유사도 임계값을 75%로 완화한다

### Requirement 11: 장르 매핑 테이블 외부화 (Maintainability)

**User Story:** As a 개발자, I want 장르 매핑 규칙이 외부 설정 파일로 관리되기를, so that 코드 수정 없이 매핑 규칙을 변경할 수 있습니다.

#### Acceptance Criteria

1. THE Search_First_Classifier SHALL 'config/genre_mapping.json' 파일에서 플랫폼별 장르 매핑 규칙을 로드한다
2. WHEN 새로운 플랫폼이나 장르 명칭이 추가되면, THE Search_First_Classifier SHALL JSON 설정 수정만으로 대응 가능하다
3. WHEN 매핑 파일이 없거나 로드 실패하면, THE Search_First_Classifier SHALL 내장된 기본 매핑을 사용한다
4. THE genre_mapping.json SHALL 플랫폼별 장르명 → 표준 장르명 매핑을 포함한다

### Requirement 12: 검증 테스트 케이스

**User Story:** As a 개발자, I want 기존에 실패했던 제목들이 올바르게 분류되는지 검증하기를, so that 개선 효과를 확인할 수 있습니다.

#### Acceptance Criteria

1. WHEN '100층의 올마스터' 제목이 입력되면, THE Search_First_Classifier SHALL 인터넷 검색을 통해 장르를 찾아 '미분류'가 아닌 결과를 반환한다
2. WHEN '1588 샤인머스캣으로 귀농 왔더니 신대륙' 제목이 입력되면, THE Search_First_Classifier SHALL 인터넷 검색을 통해 장르를 찾아 '미분류'가 아닌 결과를 반환한다
3. WHEN 검색 결과가 있는 유명 작품이 입력되면, THE Search_First_Classifier SHALL confidence가 'high'인 결과를 반환한다
