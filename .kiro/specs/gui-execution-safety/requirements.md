# Requirements Document

## Introduction

WNAP GUI의 실행 로직과 UX에서 발견된 논리적 모순과 안전성 문제를 해결하기 위한 전면 수정 요구사항입니다. 주요 목표는 실행/미리보기 로직의 완전 분리, 원본 파일 보존을 위한 복사 기반 로직 도입, 안전한 실행 시퀀스 구현, 그리고 모듈 임포트 오류 해결입니다.

## Glossary

- **GUI**: Graphical User Interface, 사용자가 상호작용하는 그래픽 인터페이스
- **Dry_Run_Mode**: 실제 파일 시스템 변경 없이 분석 결과만 미리보기하는 모드
- **Preview_Button**: 미리보기(Dry-run) 버튼, 분석만 수행하고 결과를 테이블에 표시
- **Execute_Button**: 실행 버튼, 테이블에 올라온 리스트를 바탕으로 실제 파일 복사 수행
- **Reset_Button**: 초기화 버튼, 테이블 데이터와 상태를 초기화
- **Source_Folder**: 정리할 원본 파일들이 있는 폴더
- **Target_Folder**: 정리된 파일들이 저장될 대상 폴더
- **Confirm_Dialog**: 실행 전 사용자에게 확인을 요청하는 대화상자
- **Copy_Operation**: shutil.copy2를 사용한 파일 복사 작업
- **Move_Operation**: shutil.move를 사용한 파일 이동 작업 (제거 대상)
- **Pipeline_Orchestrator**: 파이프라인 전체를 조율하는 메인 컨트롤러
- **Result_Table**: 처리 결과를 표시하는 Treeview 테이블
- **sys_path**: Python 모듈 검색 경로 목록

## Requirements

### Requirement 1: 미리보기 버튼의 독립적 동작

**User Story:** As a 사용자, I want 미리보기 버튼이 설정창의 Dry-run 스위치 상태와 무관하게 항상 분석만 수행하도록, so that 실수로 파일이 변경되는 것을 방지할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 Preview_Button을 클릭하면 THEN THE GUI SHALL 설정창의 Dry_Run_Mode 스위치 상태와 상관없이 항상 분석만 수행한다
2. WHEN Preview_Button이 클릭되면 THEN THE GUI SHALL 파일 이동이나 복사를 절대 수행하지 않는다
3. WHEN Preview_Button이 클릭되면 THEN THE GUI SHALL 분석 결과를 Result_Table에 표시한다
4. THE GUI SHALL Preview_Button 클릭 시 Dry_Run_Mode 스위치 값을 변경하지 않는다

### Requirement 2: 안전한 실행 시퀀스 구현

**User Story:** As a 사용자, I want 실행 버튼이 미리보기 완료 후에만 활성화되고 확인 대화상자를 거치도록, so that 실수로 파일을 변경하는 것을 방지할 수 있다.

#### Acceptance Criteria

1. WHEN 프로그램이 시작되면 THEN THE GUI SHALL Execute_Button을 비활성화(Disabled) 상태로 설정한다
2. WHEN Preview_Button 실행이 완료되고 Result_Table에 1개 이상의 항목이 존재하면 THEN THE GUI SHALL Execute_Button을 활성화한다
3. WHEN Result_Table에 항목이 없으면 THEN THE GUI SHALL Execute_Button을 비활성화 상태로 유지한다
4. WHEN 사용자가 Execute_Button을 클릭하면 THEN THE GUI SHALL "N개의 파일을 실제로 변환하시겠습니까?" 형식의 Confirm_Dialog를 표시한다
5. WHEN Confirm_Dialog에서 사용자가 '예'를 선택하면 THEN THE GUI SHALL 실제 파일 복사를 시작한다
6. WHEN Confirm_Dialog에서 사용자가 '아니오'를 선택하면 THEN THE GUI SHALL 파일 처리를 취소하고 대기 상태로 돌아간다
7. THE Execute_Button SHALL Dry_Run_Mode 스위치 상태와 무관하게 항상 실제 파일 복사를 수행한다

### Requirement 3: 버튼 및 상태 UX 명확화

**User Story:** As a 사용자, I want 각 버튼의 역할이 명확하게 구분되도록, so that 혼란 없이 원하는 작업을 수행할 수 있다.

#### Acceptance Criteria

1. THE Preview_Button SHALL 분석을 수행하고 Result_Table을 채우는 용도로만 동작한다
2. THE Execute_Button SHALL Result_Table에 올라온 리스트를 바탕으로 실제 파일 복사를 수행한다
3. WHEN Reset_Button이 클릭되면 THEN THE GUI SHALL Result_Table의 모든 데이터를 삭제한다
4. WHEN Reset_Button이 클릭되면 THEN THE GUI SHALL 프로그레스 바를 0으로 초기화한다
5. WHEN Reset_Button이 클릭되면 THEN THE GUI SHALL 대시보드의 결과 요약 수치(총 파일, 성공, 실패, 건너뜀)를 모두 '-'로 초기화한다
6. WHEN Reset_Button이 클릭되면 THEN THE GUI SHALL 상태 레이블을 '대기 중'으로 변경한다
7. WHEN Reset_Button이 클릭되면 THEN THE GUI SHALL Execute_Button을 비활성화(Disabled) 상태로 되돌린다

### Requirement 4: 원본 보존을 위한 복사 기반 로직

**User Story:** As a 사용자, I want 파일 변환 시 원본 파일이 보존되도록, so that 데이터 손실 위험 없이 안전하게 파일을 정리할 수 있다.

#### Acceptance Criteria

1. WHEN 파일 변환 및 정리가 실행되면 THEN THE Pipeline_Orchestrator SHALL Move_Operation 대신 Copy_Operation을 사용한다
2. THE Pipeline_Orchestrator SHALL Source_Folder의 원본 파일을 어떠한 경우에도 삭제하거나 훼손하지 않는다
3. THE Pipeline_Orchestrator SHALL 모든 결과물을 Target_Folder에 생성한다
4. WHEN 파일 복사가 완료되면 THEN THE Pipeline_Orchestrator SHALL Source_Folder의 파일 개수가 실행 전과 동일하게 유지되어야 한다
5. THE core/adapters 모듈들 SHALL shutil.move 대신 shutil.copy2를 사용한다
6. THE Pipeline_Orchestrator SHALL 파일 복사 시 메타데이터(수정 시간 등)를 보존한다

### Requirement 5: 실행 완료 후 결과 확인 자동화

**User Story:** As a 사용자, I want 실행 완료 후 결과 폴더가 자동으로 열리도록, so that 처리 결과를 즉시 확인할 수 있다.

#### Acceptance Criteria

1. WHEN Execute_Button 실행이 성공적으로 완료되면 THEN THE GUI SHALL subprocess를 통해 Target_Folder를 자동으로 연다
2. WHEN Target_Folder 자동 열기가 실패하면 THEN THE GUI SHALL 오류 메시지를 표시하고 계속 진행한다
3. THE GUI SHALL 실행 전후 Source_Folder의 파일 개수를 대조하여 원본 보존 여부를 UI에 표시한다

### Requirement 6: 모듈 임포트 오류 해결

**User Story:** As a 사용자, I want GUI 실행 시 모듈 임포트 오류가 발생하지 않도록, so that 프로그램을 정상적으로 실행할 수 있다.

#### Acceptance Criteria

1. THE main_gui.py SHALL 프로젝트 루트를 sys_path에 추가하는 경로 보정 코드를 포함한다
2. WHEN main_gui.py가 실행되면 THEN THE System SHALL 'gui.main_window' 모듈을 정상적으로 임포트한다
3. WHEN PyInstaller로 패키징된 EXE가 실행되면 THEN THE System SHALL 모든 모듈을 정상적으로 임포트한다
4. THE main_gui.py SHALL 일반 Python 실행 환경과 PyInstaller 패키징 환경 모두에서 동작한다

### Requirement 7: 실행 결과 무결성 검증

**User Story:** As a 개발자, I want 실행 전후 소스 폴더의 파일 개수가 유지되는지 검증할 수 있도록, so that 원본 보존 로직이 정상 동작함을 확인할 수 있다.

#### Acceptance Criteria

1. WHEN 파이프라인 실행이 시작되면 THEN THE Pipeline_Orchestrator SHALL 실행 전 Source_Folder의 파일 개수를 기록한다
2. WHEN 파이프라인 실행이 완료되면 THEN THE Pipeline_Orchestrator SHALL 실행 후 Source_Folder의 파일 개수를 확인한다
3. IF 실행 전후 Source_Folder의 파일 개수가 다르면 THEN THE Pipeline_Orchestrator SHALL 경고 로그를 출력한다
4. THE Pipeline_Orchestrator SHALL 실행 결과에 원본 파일 보존 상태를 포함한다
5. THE GUI SHALL 원본 보존 상태를 사용자에게 시각적으로 표시한다
