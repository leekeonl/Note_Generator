# Release Notes Tool

업무에서 수동으로 하던 릴리스 노트 작성 워크플로우를 자동화한 데스크톱 GUI
도구입니다. 원시 개발자 체크인 노트로부터 고객 배포용 릴리스 노트를
생성하는 반복적이고 시간 소모적인 작업을 해결하기 위해 만들었고, 동시에
안전한 파일 변경, 커밋 전 미리보기, 플러그 가능한 데이터 소스, 모던
Python GUI 같은 디자인 패턴을 실험해본 프로젝트입니다.

**버전 1.2.0** — 커밋 추적 시스템에서의 자동 노트 fetch 기능과 기존 패치
재구성을 위한 머지 모드가 추가되었습니다.

---

## 문제 (Problem)

매번 패치 릴리스마다 수동으로 다음 작업을 해야 했습니다:

1. 커밋 시스템에서 50개 이상의 개발자 체크인을 하나씩 찾기
2. `Notes.txt` 파일에 일일이 붙여넣기
3. 체크인 ID로 필터링
4. 내부용 메타데이터 제거 (`Developer:`, `Timestamp:`, auto-merge 블록 등)
5. 각 섹션을 고객용 템플릿 형식에 맞춰 재포맷
6. `DevNotes.txt`의 올바른 위치에 새 패치 블록 삽입
7. 고객 배포용 `ReleaseNotes.txt` 재생성

이 작업은 릴리스당 약 30분이 걸렸고, 에러가 발생하기 쉬웠습니다. 체크인
ID에 오타 하나만 있어도 그 수정 사항이 릴리스 노트에서 조용히 빠져버렸고,
고객이 발견하기 전까진 알 길이 없었습니다.

## 해결 (Solution)

|                                  | Before          | After                    |
| -------------------------------- | --------------- | ------------------------ |
| 릴리스당 소요 시간               | ~30분           | ~30초                    |
| 수동 재포맷 단계                 | 50회 이상       | 0회                      |
| 노트 수집 방식                   | 일일이 복붙     | PR 번호로 자동 fetch     |
| ID 오타 시 누락 가능성           | 있음            | 미리보기에서 감지        |
| 문제 발생 시 롤백                | 수동 복원       | 자동 백업                |
| 기존 패치에 PR 추가하기          | 파일 직접 수정  | 머지 모드                |

---

## 주요 기능

### Auto-Generate (v1.2)

`Notes.txt` 수집 단계를 완전히 생략할 수 있습니다. PR 번호나 체크인 ID
목록을 입력하면, 도구가 구성된 커밋 추적 시스템에서 직접 노트를 가져오고,
정규화한 뒤, 전체 파이프라인을 실행합니다.

- **브랜치 자동 감지** — DevNotes의 `Base Version:` 라인에서 자동으로
  추출, 수동 오버라이드 가능.
- **우선순위 fallback** — 감지된 브랜치를 먼저 시도하고, 매칭이 없으면
  구성된 fallback 브랜치로 자동 전환.
- **포맷 정규화** — 커밋 메시지 스타일 헤더를 파이프라인이 기대하는
  Notes.txt 표준 형식으로 변환.

### 기존 패치에 머지 (v1.2)

패치를 완료한 후 PR 하나를 더 추가해야 할 때를 위한 기능. 드롭다운에서
기존 패치 라벨을 선택하고 새 체크인을 fetch하면, 도구가:

1. DevNotes에서 기존 패치 블록을 읽어들이고
2. 이미 있는 것과 충돌하는 체크인 ID들을 감지하고
3. 충돌별로 묻습니다: 기존 유지 vs 새 것으로 교체
4. 전체 패치 블록을 체크인 ID 내림차순으로 재구성

### 쓰기 전 미리보기

실행할 때마다 모달 미리보기 창이 열리며, 3개의 탭(Check-in IDs /
DevNotes preview / ReleaseNotes preview)에서 파일에 어떤 변경이
이뤄질지 정확히 확인한 후 진행할 수 있습니다.

### 누락 ID 감지

입력에는 있지만 가져온 데이터에는 없는 체크인 ID가 있으면, 커밋 전에
미리보기에서 노란색 경고로 표시됩니다.

### 타임스탬프 자동 백업

커밋마다 원본 수정 전에 `DevNotes.YYYYMMDD_HHMMSS.bak.txt` 형식으로
백업이 만들어져, 같은 날 여러 번 실행해도 이전 백업이 덮어쓰여지지
않습니다.

### 유연한 패치 라벨

`Patch`, `LabPatch`, `HomeMade` 또는 사용자 정의 prefix를 지원하고,
정수(`10`) 또는 소수(`5.1`) 번호 모두 가능합니다.

### 포맷 정규화

개발자들이 실제로 쓰는 두 가지 노트 포맷(섹션 헤더가 단독 줄로 있는
경우 vs 본문과 인라인으로 붙어 있는 경우)을 모두 처리하며 어느 한 쪽도
깨지지 않습니다.

### 독립 실행 헬퍼 페이지

파이프라인의 한 단계만 필요할 경우 별도로 실행할 수 있습니다.

---

## 설계 결정 (Design Decisions)

몇 가지 짚어볼 만한 선택들:

- **2단계 파이프라인 (`build_preview` + `commit_preview`).** 미리보기는
  파일을 전혀 건드리지 않는 순수 읽기 전용 작업이고, 커밋만이 디스크를
  변경합니다. 이 분리 덕분에 미리보기를 신뢰할 수 있고, 모달 미리보기
  창을 추가할 때 로직 중복 없이 깔끔하게 구현할 수 있었습니다.
- **플러그 가능한 노트 소스.** 각 데이터 소스가 작은 `NoteSource`
  인터페이스를 구현합니다. priority merger가 이들을 fallback 의미로 순서
  대로 순회합니다. 새로운 추적 시스템을 추가하려면 100줄 정도의 클래스
  하나만 작성해서 `sources/`에 넣으면 됩니다 — 파이프라인이나 UI는
  건드릴 필요 없음.
- **독립적인 머지 파이프라인.** 기존 패치 재구성은 메인 파이프라인에
  덧붙이는 대신 자체 파이프라인(`merge_pipeline.py`)으로 두었습니다.
  같은 preview-then-commit 모양을 따르지만 자체 preview 타입을 가짐.
  두 경로 모두 추론하기 쉬워집니다.
- **단일 `.bak` 대신 타임스탬프 백업.** 같은 날 여러 번 실행해도 이전
  백업이 보존됩니다. 정렬도 자연스러움.
- **일반화된 패치 정규식.** `^[A-Za-z]+\d+(?:\.\d+)?$`는 `Patch10`,
  `LabPatch3`, `HomeMade5.1`, 그리고 사용자 정의 prefix까지 모두 커버
  합니다. 실제로 팀들이 패치를 어떻게 라벨링하는지를 반영한 결과.
- **메모리 기반 텍스트 변환 + 얇은 파일 I/O 래퍼.** 파싱과 포매팅
  로직은 모두 문자열에 대한 순수 함수로 구현했고, 파일을 읽거나 쓰는
  함수는 소수에 불과합니다. 핵심 로직을 테스트하고 추적하기 쉬워졌습니다.
- **순환 import 방지를 위한 지연 import.** Auto-Generate 페이지와 메인
  UI 모듈은 서로를 import합니다. 모듈 레벨 import는 데드락을 일으키지만,
  메서드 본문 안으로 import를 지연시키면 모듈을 억지로 분리하지 않고도
  해결됩니다.
- **GUI는 customtkinter.** 네이티브에 가까운 위젯, 모던 테마, 플랫폼별
  드로잉 코드 없이 균일한 룩 앤 필. PyInstaller로 단일 파일 빌드 가능.

---

## 스크린샷

*(스크린샷을 여기에 추가하세요. Auto-Generate 페이지, Preview 다이얼로그,
conflict-resolution 다이얼로그 세 화면을 보여주는 것을 추천합니다.)*

---

## 요구 사항

- Python 3.10 이상
- [customtkinter](https://pypi.org/project/customtkinter/)
- [requests](https://pypi.org/project/requests/) — Auto-Generate에만 필요
  (네트워크 호출). Manual-Generate는 없어도 작동.

```bash
pip install customtkinter requests
```

---

## 사용 방법

```bash
python ReleaseNotesTool_UI_ctk.py
```

### Manual-Generate (v1.0 워크플로우)

1. 기존 `DevNotes.txt` 파일을 선택합니다.
2. 패치 타입과 번호를 선택합니다.
3. `checkinid.txt`(포함할 체크인 ID 목록)를 선택합니다.
4. `Notes.txt`(직접 수집한 원시 개발자 노트)를 선택합니다.
5. **Run Full Pipeline** 버튼을 클릭합니다.
6. 미리보기를 확인하세요. 이상한 부분이 있으면 **Cancel** 클릭.
7. **Confirm & Write Files**를 클릭하면 실제로 파일이 작성됩니다.

### Auto-Generate

1. 기존 `DevNotes.txt` 선택 — 브랜치가 자동 감지되고 기존 패치 드롭다운
   이 자동 채워집니다.
2. **New patch** 모드 선택, 패치 타입과 번호 입력.
3. PR 번호 또는 체크인 ID를 박스에 입력 (한 줄에 하나씩 또는 쉼표로
   구분), 또는 `checkinid.txt` 파일 선택.
4. **Fetch & Preview** 클릭.
5. 미리보기 확인 후 **Confirm & Write Files**.

### Auto-Generate — 기존 패치에 머지

1. 기존 `DevNotes.txt` 선택.
2. **Merge into existing patch** 모드 선택, 드롭다운에서 패치 선택.
3. 추가할 새 PR 번호 / 체크인 ID 입력.
4. **Fetch & Preview** 클릭.
5. 기존 패치와 충돌하는 체크인 ID가 있으면 conflict 다이얼로그가 열림
   — 각 ID별로 기존 유지 vs 새로 가져온 것 교체 중 선택.
6. 머지된 미리보기 확인 후 **Confirm & Write Files**.

### 패치 라벨 예시

| 타입      | 번호   | 결과           |
| --------- | ------ | -------------- |
| Patch     | 10     | `Patch10`      |
| Patch     | 5.1    | `Patch5.1`     |
| LabPatch  | 3      | `LabPatch3`    |
| HomeMade  | 5      | `HomeMade5`    |
| *사용자*  | 2      | `HotFix2`      |

---

## 파일 구조

```
NoteGenerator/
├── ReleaseNotesTool_UI_ctk.py   # GUI 진입점
├── full_pipeline.py             # build_preview / commit_preview (새 패치)
├── merge_pipeline.py            # build_merge_preview / commit_merge_preview
├── auto_generate_page.py        # Auto-Generate 페이지 + conflict 다이얼로그
├── branch_detector.py           # "Base Version: ..." → 브랜치 토큰 파싱
├── devnotes_parser.py           # 기존 패치 블록 읽기/편집
├── notes_to_for_devnotes.py     # 체크인 ID로 원시 노트 필터링
├── ReleaseNotesCreatorv4.py     # DevNotes.txt → ReleaseNotes.txt 변환
├── sources/
│   ├── base.py                  # NoteSource 인터페이스 + FetchResult
│   └── file_source.py           # 로컬 파일에서 노트 읽기
├── merger/
│   └── priority_merger.py       # fallback 의미로 소스들 순회
├── docs/                        # README의 텍스트 버전
└── README.md
```

### 파이프라인 아키텍처

```
새 패치 플로우:
  build_preview(devnotes, patch, checkinids, notes)
      → PipelinePreview   (순수 / 읽기 전용)
  commit_preview(preview, make_backup=True)
      → 파일 작성 + 백업 생성

머지 플로우:
  build_merge_preview(devnotes, patch_label, new_notes, resolutions)
      → MergePreview   (순수 / 읽기 전용; 감지된 충돌 노출)
  commit_merge_preview(preview, make_backup=True)
      → 파일 작성 + 백업 생성
```

### 새 노트 소스 추가하기

다른 커밋 추적 시스템과 통합하려면:

1. `sources/your_source.py`에서 `NoteSource`를 상속.
2. `fetch(queries)`를 구현하여 Notes.txt 스타일 텍스트가 든 `FetchResult`
   반환.
3. `auto_generate_page.py`의 `_build_sources`에서 인스턴스를 만들어
   priority chain에 추가.

파이프라인은 노트가 어디서 왔는지 신경 쓰지 않습니다 — 예상 텍스트 형식
만 맞으면 OK.

---

## 입력 파일 형식

### `checkinid.txt`

체크인 버전 번호(`N.NNNN`) 또는 PR 번호(`PR-NNNNNN`)를 포함하는 텍스트.
한 줄에 하나씩 또는 쉼표로 구분. 이름과 기타 텍스트는 무시 — 숫자와 PR
패턴만 매칭됩니다.

```
alice 0.4091
bob 0.3968
PR-214308
0.4260
```

### `Notes.txt`

원시 개발자 노트 (Manual-Generate에서만 필요). 각 체크인 블록은
`Checkin ID:`로 시작하며 80개 하이픈 구분선으로 분리됩니다. 도구는
DevNotes에 삽입하기 전 내부 전용 헤더(`Developer:`, `Timestamp:`,
`Release Notes Needed:`, `[Auto Merge Wizard]` 블록 등)를 자동으로
제거합니다.

### `DevNotes.txt`

`Base Version: ...` 라인으로 시작해야 합니다. 새 패치는 이 라인 바로
아래에 삽입됩니다. 기존 패치는 newest-first 순으로 그 아래에 나열됩니다.

---

## 독립 실행 파일로 빌드하기

### macOS / Linux

```bash
pip install pyinstaller

python3 -m PyInstaller --clean --onefile --windowed \
    --collect-all customtkinter --collect-all darkdetect \
    --collect-all requests \
    --hidden-import auto_generate_page \
    --hidden-import branch_detector \
    --hidden-import devnotes_parser \
    --hidden-import merge_pipeline \
    --hidden-import sources \
    --hidden-import sources.base \
    --hidden-import sources.file_source \
    --hidden-import merger \
    --hidden-import merger.priority_merger \
    --name ReleaseNotesTool ReleaseNotesTool_UI_ctk.py
```

### Windows

같은 플래그, `python3` 대신 `python` 사용.

결과물:
- macOS / Linux: `dist/ReleaseNotesTool`
- Windows: `dist/ReleaseNotesTool.exe`

`--collect-all` 플래그는 라이브러리 에셋(테마, 폰트 등) 번들링용입니다.
`--hidden-import` 플래그는 앱이 사용하는 지연 import를 PyInstaller의
정적 분석이 항상 감지하지 못하기 때문에 필요합니다.

> **참고:** PyInstaller 빌드 결과물은 플랫폼별로 다릅니다. 배포 대상
> OS와 같은 환경에서 빌드해야 합니다.

---

## 백업에서 복원하기

백업은 `DevNotes.txt`와 같은 폴더에 타임스탬프 파일명으로 저장됩니다:

```
DevNotes.txt
DevNotes.20260516_205412.bak.txt   ← 5월 16일 오후 8:54 백업
DevNotes.20260603_091203.bak.txt   ← 6월 3일 오전 9:12 백업
```

복원하려면 원하는 백업 파일의 이름을 `DevNotes.txt`로 변경하면 됩니다
(기존 파일은 덮어쓰기). 인앱 "Backup에서 복원" 기능은 향후 추가될
예정입니다.

---

## 로드맵 (Roadmap)

- [ ] 인앱 백업 복원 UI
- [ ] 세션 간 마지막 사용 경로 기억
- [ ] 기존 DevNotes 기반 다음 패치 번호 자동 제안
- [ ] 메인 창 내 출력 미리보기 패널
- [ ] conflict resolution 다이얼로그에 side-by-side diff 보기

---

## 변경 이력 (Changelog)

### 1.2.0

- 새 **Auto-Generate** 워크플로우 — 구성된 커밋 추적 시스템에서 직접
  노트 fetch.
- 새 **기존 패치에 머지** 모드 — 충돌별 선택 가능.
- 새 `sources/` 및 `merger/` 패키지 — 우선순위 fallback이 있는 플러그
  가능한 노트 소스.
- `Base Version:`에서 브랜치 자동 감지.
- 사이드바 재구성: Auto-Generate가 메인 워크플로우로, Manual-Generate는
  백업 경로로 유지.
- 레거시 `ReleaseNotesTool_UI.py` 프로토타입 제거.

### 1.1.0

- 3-탭 모달 미리보기 다이얼로그.
- 미리보기에서 누락 ID 감지.
- 타임스탬프 백업.
- 유연한 패치 라벨 드롭다운 (Patch / LabPatch / HomeMade / 사용자 정의).
- 인라인 섹션 헤더 정규화.

### 1.0.0

- 초기 릴리스: 체크인 ID로 노트를 필터링하고 결과로부터 DevNotes /
  ReleaseNotes를 생성하는 단일 플로우 GUI.
