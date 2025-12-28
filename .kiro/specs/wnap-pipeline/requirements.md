# Requirements Document

## Introduction

Web Novel Archive Pipeline (WNAP)은 웹소설 아카이브 파일을 자동으로 정리하는 통합 파이프라인입니다. 기존에 독립적으로 운영되던 3개의 모듈(폴더 정리기, 장르 분류기, 파일명 정규화 도구)을 하나의 워크플로우로 통합하여, '압축 해제 및 정리' → '장르/제목 확정' → '표준 파일명 변경'이 한 번에 일어나도록 합니다.

### 핵심 기술 과제
- **파일명 파편화 대응**: 다양한 파일명 규칙을 '제목 앵커(Title Anchor)' 전략으로 통합
- **중국 소설 대응**: 선협, 언정 등 중국 번역 소설의 특유 패턴(~지, ~기)과 한자 독음 처리
- **장르 표준화**: 네이버/카카오 등 플랫폼별 장르명을 표준 장르명으로 매핑

## Glossary

- **NovelTask**: 웹소설 처리의 모든 상태를 담는 데이터 객체 (core/novel_task.py)
- **Pipeline_Orchestrator**: 전체 파이프라인을 조율하는 메인 컨트롤러
- **Folder_Organizer**: 압축 파일 해제 및 폴더 구조 정리 모듈
- **Genre_Classifier**: 파일명/메타데이터 기반 장르 분류 모듈
- **Filename_Normalizer**: 파일명을 표준 형식으로 변환하는 모듈
- **Title_Anchor**: 파일명에서 핵심 제목을 추출하는 전략
- **Genre_Mapping**: 플랫폼별 장르명을 표준 장르명으로 변환하는 매핑 테이블
- **Confidence_Level**: 분류/추론 결과의 신뢰도 (high/medium/low)

## Requirements

### Requirement 1: NovelTask 데이터 표준

**User Story:** As a 개발자, I want 모든 모듈이 동일한 데이터 구조를 사용하도록, so that 파이프라인 단계 간 데이터 전달이 일관되게 이루어집니다.

#### Acceptance Criteria

1. THE NovelTask SHALL contain original_path, current_path, raw_name, title, author, genre, volume_info, is_completed, status, confidence, metadata fields
2. WHEN a NovelTask is created, THE Pipeline_Orchestrator SHALL initialize status to "pending" and confidence to "none"
3. WHEN a module processes a NovelTask, THE module SHALL update the status field to reflect current processing state
4. THE NovelTask SHALL support serialization to JSON for persistence and logging
5. WHEN deserializing a NovelTask from JSON, THE system SHALL restore all fields to their original values (round-trip property)

---

### Requirement 2: 폴더 정리 단계 (Stage 1)

**User Story:** As a 사용자, I want 압축 파일이 자동으로 해제되고 정리되도록, so that 수동으로 압축을 풀고 파일을 정리하는 시간을 절약합니다.

#### Acceptance Criteria

1. WHEN a source folder is provided, THE Folder_Organizer SHALL scan all subfolders excluding protected folders (Downloads, Tempfile, 정리완료)
2. WHEN an archive file (.zip, .rar, .7z, .zipx) is found, THE Folder_Organizer SHALL analyze its contents before extraction
3. WHEN an archive contains a single text file, THE Folder_Organizer SHALL extract only that file to the target folder
4. WHEN an archive contains multiple top-level folders, THE Folder_Organizer SHALL extract and recompress each folder separately
5. WHEN extraction is complete, THE Folder_Organizer SHALL create a NovelTask object for each extracted file
6. IF an archive extraction fails, THEN THE Folder_Organizer SHALL log the error and continue with remaining files
7. WHEN processing is complete, THE Folder_Organizer SHALL remove empty source folders

---

### Requirement 3: 장르 분류 단계 (Stage 2)

**User Story:** As a 사용자, I want 파일의 장르가 자동으로 분류되도록, so that 파일을 장르별로 정리할 수 있습니다.

#### Acceptance Criteria

1. WHEN a NovelTask is received, THE Genre_Classifier SHALL analyze the raw_name field for genre keywords
2. THE Genre_Classifier SHALL use genre_keywords.json as the single source of truth for keyword weights
3. WHEN multiple genres match, THE Genre_Classifier SHALL return the genre with highest weighted score
4. THE Genre_Classifier SHALL calculate confidence level based on score gap between top two genres
5. WHEN confidence is "high" (>90%), THE Genre_Classifier SHALL auto-assign the genre
6. WHEN confidence is "medium" (50-90%), THE Genre_Classifier SHALL flag for user review
7. WHEN confidence is "low" (<50%), THE Genre_Classifier SHALL mark as "미분류"
8. THE Genre_Classifier SHALL apply compound patterns (e.g., "무공"+"시스템"→무협) before single keywords
9. WHEN a platform-specific genre is detected (e.g., "현대판타지"), THE Genre_Classifier SHALL map it to standard genre (e.g., "현판")
10. WHEN no keywords match AND no platform search results exist, THE Genre_Classifier SHALL assign default genre "미분류" with confidence "low"
11. WHEN platform API search returns empty results, THE Genre_Classifier SHALL fallback to keyword-only classification with confidence reduced by one level

---

### Requirement 4: 제목 앵커 추출 (Title Anchor Strategy)

**User Story:** As a 시스템, I want 다양한 파일명 패턴에서 핵심 제목을 추출하도록, so that 정규화된 파일명을 생성할 수 있습니다.

#### Acceptance Criteria

1. WHEN parsing a filename, THE Title_Anchor_Extractor SHALL identify the core title by removing noise patterns
2. THE Title_Anchor_Extractor SHALL remove author markers (@닉네임, ⓒ닉네임, 저자:)
3. THE Title_Anchor_Extractor SHALL first extract the title anchor, THEN parse volume/range information ONLY from the residual string (remaining characters after title extraction)
4. THE Title_Anchor_Extractor SHALL extract volume/range information (1-536화, 1-2부) from the residual string only
5. THE Title_Anchor_Extractor SHALL identify completion markers (完, 완, Complete) from the residual string and normalize to "(완)"
6. THE Title_Anchor_Extractor SHALL extract side story markers (番外, 외전, 후기) from the residual string
7. WHEN a Chinese novel pattern is detected (~지, ~기 endings), THE Title_Anchor_Extractor SHALL preserve the original title structure
8. FOR ALL valid filenames, parsing then formatting SHALL produce a semantically equivalent filename (round-trip property)
9. THE Title_Anchor_Extractor SHALL process in strict order: (1) extract title anchor → (2) parse residual string → (3) assemble normalized filename, to prevent regex conflicts between title and metadata

---

### Requirement 5: 파일명 정규화 단계 (Stage 3)

**User Story:** As a 사용자, I want 파일명이 일관된 형식으로 변환되도록, so that 파일을 쉽게 찾고 관리할 수 있습니다.

#### Acceptance Criteria

1. THE Filename_Normalizer SHALL produce filenames in format: `[카테고리] 제목 부정보 범위 (완) + 외전정보.확장자`
2. WHEN a genre is assigned, THE Filename_Normalizer SHALL use the standard genre name from GENRE_WHITELIST
3. THE Filename_Normalizer SHALL normalize unicode spaces to single ASCII spaces
4. THE Filename_Normalizer SHALL preserve file extensions (.txt, .epub, .zip, .7z, .rar)
5. WHEN volume info exists, THE Filename_Normalizer SHALL place it before range info
6. IF the normalized filename already exists, THEN THE Filename_Normalizer SHALL append a numeric suffix
7. FOR ALL NovelTask objects, normalizing the filename SHALL not lose any semantic information from the original

---

### Requirement 6: 파이프라인 오케스트레이션

**User Story:** As a 사용자, I want 전체 파이프라인이 자동으로 실행되도록, so that 한 번의 명령으로 모든 처리가 완료됩니다.

#### Acceptance Criteria

1. WHEN the pipeline starts, THE Pipeline_Orchestrator SHALL execute stages in order: Folder_Organizer → Genre_Classifier → Filename_Normalizer
2. WHEN a stage completes, THE Pipeline_Orchestrator SHALL pass the updated NovelTask to the next stage
3. THE Pipeline_Orchestrator SHALL support dry-run mode that simulates changes without modifying files
4. WHEN dry-run mode is enabled, THE Pipeline_Orchestrator SHALL output a preview of all planned changes
5. THE Pipeline_Orchestrator SHALL generate a mapping.csv file recording original→normalized filename mappings
6. IF any stage fails for a NovelTask, THEN THE Pipeline_Orchestrator SHALL log the error, mark the task as "failed", and continue with remaining tasks (fault-tolerance)
7. IF a critical error occurs for a specific file, THEN THE Pipeline_Orchestrator SHALL skip only that file and SHALL NOT terminate the entire pipeline
8. WHEN all stages complete, THE Pipeline_Orchestrator SHALL output a summary of processed/failed/skipped files with counts for each category
9. THE Pipeline_Orchestrator SHALL implement a retry mechanism with configurable max_retries (default: 1) for transient errors
10. WHEN a file is skipped due to error, THE Pipeline_Orchestrator SHALL record the error reason in the mapping.csv for post-processing review

---

### Requirement 7: 중국 소설 특수 처리

**User Story:** As a 사용자, I want 중국 번역 소설이 올바르게 분류되도록, so that 선협/언정 등의 장르가 정확히 식별됩니다.

#### Acceptance Criteria

1. WHEN a filename contains Chinese-Korean transliteration patterns, THE Genre_Classifier SHALL apply special detection rules
2. THE Genre_Classifier SHALL recognize 선협 keywords (선인, 수련, 도술, 법술, 영약, 단약, 승천, 선계)
3. THE Genre_Classifier SHALL recognize 언정 keywords (낭자, 금리, 공자, 소저, 후상, 화리)
4. WHEN a filename is pure Korean with no semantic meaning (e.g., "가급일개노황제"), THE Genre_Classifier SHALL flag for manual review
5. THE Title_Anchor_Extractor SHALL preserve Chinese title structures when detected

---

### Requirement 8: 사용자 인터페이스

**User Story:** As a 사용자, I want CLI와 GUI 모두에서 파이프라인을 실행할 수 있도록, so that 선호하는 방식으로 작업할 수 있습니다.

#### Acceptance Criteria

1. THE system SHALL provide a CLI interface with --source, --target, --dry-run, --yes options
2. THE system SHALL provide a GUI interface for interactive processing
3. WHEN confidence is "medium", THE GUI SHALL display a confirmation dialog with suggested genre
4. THE GUI SHALL display real-time progress for each processing stage
5. THE GUI SHALL allow users to manually override genre assignments before final processing

---

### Requirement 9: 로깅 및 감사

**User Story:** As a 관리자, I want 모든 처리 과정이 기록되도록, so that 문제 발생 시 원인을 추적할 수 있습니다.

#### Acceptance Criteria

1. THE system SHALL log all file operations with timestamps
2. THE system SHALL generate a mapping.csv with columns: original_path, normalized_path, genre, confidence, status
3. WHEN an error occurs, THE system SHALL log the error with full stack trace
4. THE system SHALL support log levels: DEBUG, INFO, WARNING, ERROR
5. THE system SHALL rotate log files when they exceed 10MB

---

### Requirement 10: 설정 관리

**User Story:** As a 사용자, I want 파이프라인 동작을 설정 파일로 커스터마이즈할 수 있도록, so that 내 환경에 맞게 조정할 수 있습니다.

#### Acceptance Criteria

1. THE system SHALL load configuration from config/pipeline_config.json
2. THE configuration SHALL include: source_folder, target_folder, protected_folders, genre_whitelist, log_level
3. WHEN a configuration file is missing, THE system SHALL use default values
4. THE system SHALL validate configuration on startup and report invalid settings
5. FOR ALL valid configuration objects, serializing then deserializing SHALL produce an equivalent object (round-trip property)
