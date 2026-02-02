# WNAP - Web Novel Archive Pipeline

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="파이썬 3.13">
  <img src="https://img.shields.io/badge/Core%20Tests-138%20passed-00C853?style=for-the-badge&logo=pytest&logoColor=white" alt="138개 핵심 테스트 통과">
  <img src="https://img.shields.io/badge/Mock%20Tests-21%20scenarios-00C853?style=for-the-badge&logo=pytest&logoColor=white" alt="21개 모의 시나리오 통과">
  <img src="https://img.shields.io/badge/PBT-Property%20Based-FF6F00?style=for-the-badge" alt="속성 기반 테스트">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="윈도우">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="MIT 라이선스">
</p>

<p align="center">
  <strong>🚀 웹소설 아카이브 파일(zip, rar, 7z, zipx)을 지능적으로 정리하고 장르를 분류하는 통합 솔루션</strong>
</p>

---

## 📖 프로젝트 개요

**WNAP (Web Novel Archive Pipeline)**은 수천 개의 웹소설 아카이브 파일을 자동으로 분석하고, 장르를 분류하며, 표준화된 파일명으로 정리하는 **엔터프라이즈급 자동화 도구**입니다.

### 🎯 핵심 가치

| 핵심 기술 | 설명 |
|-----------|------|
| **타이틀 앵커 전략 (Title Anchor)** | 다양한 파일명 패턴에서 핵심 제목을 정확하게 추출하는 독자적 파싱 알고리즘. 저자명, 번역 정보, 플랫폼 태그 등의 노이즈를 제거하고 순수한 제목만 추출 |
| **검색 우선 장르 분류 (Search-First)** | 네이버 검색 + 12개 플랫폼 크롤링을 통한 정확한 장르 추출. 캐시 → 검색 → 키워드 폴백의 3단계 전략으로 90% 이상의 분류 정확도 달성 |
| **지능형 아카이브 처리** | 압축 파일 내용을 분석하여 최적의 처리 방식을 자동 결정. 단일 TXT 추출, 전체 해제, 폴더별 재압축 등 8가지 시나리오 지원 |

---

## ✨ 주요 기능

### 1. 폴더 정리 (Folder Organizer)

압축 파일 내용을 분석하여 최적의 처리 방식을 자동으로 결정합니다. **모든 작업은 `shutil.copy2`를 사용하여 원본 파일을 100% 보존합니다.**

#### 자동 분기 로직 (개요.txt 8가지 시나리오 준수)

| 시나리오 | 조건 | 처리 방식 |
|----------|------|-----------|
| **단일 TXT 추출** | 압도적으로 큰 텍스트 파일 1개 존재 | 해당 파일만 목적 폴더에 추출 |
| **전체 해제** | 비슷한 크기의 텍스트 파일 다수 | 새 폴더 생성 후 전체 압축 해제 |
| **폴더별 재압축** | 루트에 폴더만 존재 (파일 없음) | 각 폴더를 개별 ZIP으로 재압축 |
| **내부 압축 유지** | 압축 파일 내에 압축 파일 존재 | 내부 압축 파일은 해제하지 않고 유지 |
| **일반 파일 3개 이하** | 비압축 파일 3개 이하 | 목적 폴더에 직접 이동 |
| **일반 파일 4개 이상** | 비압축 파일 4개 이상 | 새 폴더 생성 후 이동 |
| **압축 파일 2개 이상** | 압축 파일 2개 이상 | 새 폴더 생성, 압축 해제 없이 이동 |
| **보호 폴더 제외** | Downloads, Tempfile, 정리완료 | 작업 대상에서 제외 |

### 2. 장르 분류 (Search-First Genre Classifier)

인터넷 검색 우선 전략으로 정확한 장르를 추출합니다.

```
분류 순서:
1. 캐시 확인 (Cache-First) - 이전 분류 결과 재사용
2. 네이버 웹 검색 → 플랫폼 링크 추출
3. 플랫폼별 장르 추출 (우선순위 적용)
4. 키워드 폴백 (검색 실패 시)
```

#### 플랫폼 우선순위

```
리디북스 > 문피아 > 네이버시리즈 > 카카오페이지 > 소설넷 > 
노벨피아 > 조아라 > 웹툰가이드 > 미스터블루 > 교보문고 > YES24 > 알라딘
```

### 3. 현대적 GUI

| 기능 | 설명 |
|------|------|
| **고대비 다크 테마** | 배경 #2b2b2b, 텍스트 #FFFFFF로 눈의 피로 감소 |
| **윈도우 상태 보존** | 창 위치/크기 자동 저장 및 복원 |
| **더블클릭 탐색기 열기** | 결과 테이블 행 더블클릭 시 해당 폴더 열기 |
| **동적 진행 바** | Dry-run 시 하늘색, 실행 시 초록색 |
| **툴팁 시스템** | 각 옵션에 대한 상세 도움말 제공 |
| **안전 실행 팝업** | 2단계 확인(미리보기 필수), 파일 수 명시로 실수 방지 |
| **자동 폴더 열기** | 작업 완료 후 결과 폴더 자동 오픈 |
| **장르 확인 다이얼로그** | 대형 폰트(26pt), CardView 스타일, 넓은 여백 |

---

## ✅ 품질 보증 (QA)

### 테스트 현황

```
============================= 138 Core Tests + 21 Mock Scenarios =============================
                              100% PASSED
```

| 테스트 유형 | 개수 | 설명 |
|-------------|------|------|
| **핵심 유닛 테스트 (Core Unit Tests)** | 138개 | 개별 함수/클래스 검증 |
| **폴더 정리 모의 테스트 (Mock Tests)** | 21개 | 개요.txt 8가지 시나리오 + 보호 폴더 + 결정 로직 검증 |
| **속성 기반 테스트 (Property-based)** | 24개 | Hypothesis 기반 데이터 무결성 검증 |

### Property-Based Testing (PBT)

[Hypothesis](https://hypothesis.readthedocs.io/) 라이브러리를 사용하여 데이터 무결성을 보장합니다.

| Property | 설명 |
|----------|------|
| **유사도 범위 (Similarity Range)** | 유사도 값은 항상 0.0 ~ 1.0 범위 |
| **유사도 대칭성 (Similarity Symmetry)** | similarity(A, B) == similarity(B, A) |
| **유효 장르 매핑 (Valid Genre)** | 매핑 결과는 항상 유효한 장르 |
| **캐시 왕복 (Cache Round-Trip)** | 캐시 저장 후 조회 시 동일 값 반환 |
| **파이프라인 순서 (Pipeline Order)** | 파이프라인 단계 순서 보장 (1→2→3) |
| **결함 격리 (Fault Isolation)** | 개별 파일 오류가 전체 파이프라인에 영향 없음 |
| **Dry-Run 불변성 (Immutability)** | Dry-run 모드에서 파일 시스템 변경 없음 |

---

## 📦 설치 및 실행

### 요구사항

- Python 3.10 이상
- Windows 10/11

### 설치

```bash
# 저장소 클론
git clone https://github.com/your-repo/wnap.git
cd wnap

# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 실행

```bash
# GUI 모드 (권장)
python main_gui.py

# CLI 모드 - 미리보기 (Dry-run)
python main.py -s ./novels

# CLI 모드 - 실제 실행
python main.py -s ./novels --no-dry-run

# 타겟 폴더 지정
python main.py -s ./novels -t ./정리완료
```

### EXE 빌드

```bash
# 클린 빌드 (권장)
python build_exe.py --clean
```

---

## 📁 프로젝트 구조

```
wnap/
├── main.py                     # CLI 진입점 (Entry Point)
├── main_gui.py                 # GUI 진입점 (Entry Point)
├── core/                       # 핵심 모듈
│   ├── adapters/               # 어댑터 패턴 (Adapter Pattern) 구현
│   │   ├── folder_organizer_adapter.py
│   │   ├── genre_classifier_adapter.py
│   │   └── filename_normalizer_adapter.py
│   └── utils/                  # 유틸리티
├── modules/                    # 독립 모듈
│   ├── classifier/             # 검색 우선 장르 분류기
│   ├── normalizer/             # 파일명 정규화
│   └── organizer/              # 폴더 정리기
├── gui/                        # GUI 모듈
│   └── utils/                  # 상태 관리, 툴팁
├── tests/                      # 테스트 (138 + 21)
└── config/                     # 설정 파일
```

---

## 📋 지원 장르

| 장르 | 키워드 예시 |
|------|-------------|
| **무협** | 무공, 강호, 협객, 문파, 내공, 검법 |
| **판타지** | 마법, 드래곤, 엘프, 던전, 마나, 소환 |
| **현판** | 현대판타지, 헌터, 각성, 게이트, 아이템 |
| **퓨판** | 퓨전판타지, 회귀, 환생, 빙의, 차원 |
| **로판** | 로맨스판타지, 빙의, 회귀, 영애, 공작 |
| **겜판** | 게임판타지, 레벨업, 스탯, 퀘스트, NPC |
| **선협** | 선인, 수련, 도술, 영약, 단약, 선계 |
| **언정** | 낭자, 금리, 공자, 소저, 후상, 왕야 |

---

## 📌 버전 히스토리

| 버전 | 날짜 | 주요 변경 사항 |
|------|------|----------------|
| **v1.2.0** | 2024-12-28 | **안전 우선 리팩토링 (Safety First)**: 원본 보존 엔진(Copy-based), 경로 오류 수정, UX 고도화 (버튼 제어, 안전 팝업) |
| **v1.1.0** | 2024-12-28 | 검색 우선(Search-First) 장르 분류, GUI UX 전면 개선, 장르 확인 다이얼로그 재설계 |
| **v1.0.0** | 2024-12-28 | 최초 릴리스 - 3개 모듈 통합, 타이틀 앵커 파싱(Title Anchor Parsing), 138개 테스트 통과 |

---

## 📄 라이선스

MIT 라이선스 - Copyright (c) 2024

---

<p align="center">
  <strong>웹소설 애호가를 위해 정성을 담아 만들었습니다</strong>
</p>

<p align="center">
  <sub>WNAP - 웹소설 정리의 새로운 기준</sub>
</p>
