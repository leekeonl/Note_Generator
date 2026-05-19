# Release Notes Tool

업무에서 수동으로 하던 릴리스 노트 작성 워크플로우를 자동화한 데스크톱 GUI
도구입니다. 원시 개발자 체크인 노트로부터 고객 배포용 릴리스 노트를
생성하는 반복적이고 시간 소모적인 작업을 해결하기 위해 만들었고, 동시에
안전한 파일 변경, 커밋 전 미리보기, 모던 Python GUI 같은 디자인 패턴을
실험해본 프로젝트입니다.

---

## 문제 (Problem)

매번 패치 릴리스마다 수동으로 다음 작업을 해야 했습니다:

1. 50개 이상의 개발자 체크인을 ID별로 필터링
2. 내부용 메타데이터 제거 (`Developer:`, `Timestamp:`, auto-merge 블록 등)
3. 각 섹션을 고객용 템플릿 형식에 맞춰 재포맷
4. `DevNotes.txt`의 올바른 위치에 새 패치 블록 삽입
5. 고객 배포용 `ReleaseNotes.txt` 재생성

이 작업은 릴리스당 약 30분이 걸렸고, 에러가 발생하기 쉬웠습니다. 체크인
ID에 오타 하나만 있어도 그 수정 사항이 릴리스 노트에서 조용히 빠져버렸고,
고객이 발견하기 전까진 알 길이 없었습니다.

## 해결 (Solution)

|                                      | Before          | After             |
| ------------------------------------ | --------------- | ----------------- |
| 릴리스당 소요 시간                   | ~30분           | ~30초             |
| 수동 재포맷 단계                     | 50회 이상       | 0회               |
| ID 오타 시 누락 가능성               | 있음            | 미리보기에서 감지 |
| 문제 발생 시 롤백                    | 수동 복원       | 자동 백업         |

---

## 주요 기능

- **쓰기 전 미리보기** — 실행할 때마다 모달 미리보기 창이 열리며, 3개의
  탭(Check-in IDs / DevNotes preview / ReleaseNotes preview)에서 파일에
  어떤 변경이 이뤄질지 정확히 확인한 후 진행할 수 있습니다.
- **누락 ID 감지** — `checkinid.txt`에는 있지만 `Notes.txt`에는 없는 ID가
  있으면, 커밋 전에 미리보기에서 노란색 경고로 표시됩니다.
- **타임스탬프 자동 백업** — 커밋마다 원본 수정 전에
  `DevNotes.YYYYMMDD_HHMMSS.bak.txt` 형식으로 백업이 만들어져, 같은 날
  여러 번 실행해도 이전 백업이 덮어쓰여지지 않습니다.
- **유연한 패치 라벨** — `Patch`, `LabPatch`, `HomeMade` 또는 사용자
  정의 prefix를 지원하고, 정수(`10`) 또는 소수(`5.1`) 번호 모두 가능합니다.
- **포맷 정규화** — 개발자들이 실제로 쓰는 두 가지 노트 포맷(섹션 헤더가
  단독 줄로 있는 경우 vs 본문과 인라인으로 붙어 있는 경우)을 모두 처리하며
  어느 한 쪽도 깨지지 않습니다.
- **독립 실행 헬퍼 페이지** — 파이프라인의 한 단계만 필요할 경우 별도로
  실행할 수 있습니다.

---

## 설계 결정 (Design Decisions)

몇 가지 짚어볼 만한 선택들:

- **2단계 파이프라인 (`build_preview` + `commit_preview`).** 미리보기는
  파일을 전혀 건드리지 않는 순수 읽기 전용 작업이고, 커밋만이 디스크를
  변경합니다. 이 분리 덕분에 미리보기를 신뢰할 수 있고, 모달 미리보기 창을
  추가할 때 로직 중복 없이 깔끔하게 구현할 수 있었습니다.
- **타임스탬프 백업.** 단일 `.bak` 대신 타임스탬프 기반 이름을 써서,
  같은 날 여러 번 실행해도 이전 백업이 보존됩니다. 정렬도 자연스럽게 됩니다.
- **일반화된 패치 정규식.** `^[A-Za-z]+\d+(?:\.\d+)?$`는 `Patch10`,
  `LabPatch3`, `HomeMade5.1`, 그리고 사용자 정의 prefix까지 모두
  커버합니다. 실제로 팀들이 패치를 어떻게 라벨링하는지를 반영한 결과입니다.
- **메모리 기반 텍스트 변환 + 얇은 파일 I/O 래퍼.** 파싱과 포매팅 로직은
  모두 문자열에 대한 순수 함수로 구현했고, 파일을 읽거나 쓰는 함수는 두
  개뿐입니다. 핵심 로직을 테스트하고 추적하기 쉬워졌습니다.
- **GUI는 customtkinter.** 네이티브에 가까운 위젯, 모던 테마, 플랫폼별
  드로잉 코드 없이 균일한 룩 앤 필. PyInstaller로 단일 파일 빌드 가능.

---

## 스크린샷

*(스크린샷을 여기에 추가하세요. All-in-One 페이지와 Preview 다이얼로그
두 화면을 보여주는 것을 추천합니다.)*

---

## 요구 사항

- Python 3.10 이상
- [customtkinter](https://pypi.org/project/customtkinter/)

```bash
pip install customtkinter
```

---

## 사용 방법

```bash
python ReleaseNotesTool_UI_ctk.py
```

### All-in-One 워크플로우

1. 기존 `DevNotes.txt` 파일을 선택합니다.
2. 드롭다운에서 패치 타입을 선택하고(`Patch`, `LabPatch`, `HomeMade`, 또는
   직접 입력) 패치 번호를 입력합니다 (`10` 또는 `5.1`).
3. `checkinid.txt`(포함할 체크인 ID 목록)를 선택합니다.
4. `Notes.txt`(원시 개발자 노트)를 선택합니다.
5. **Run Full Pipeline** 버튼을 클릭합니다.
6. Preview 다이얼로그에서 결과를 확인하세요. 이상한 부분이 있으면
   **Cancel** 클릭.
7. **Confirm & Write Files**를 클릭하면 실제로 파일이 작성됩니다.

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
├── ReleaseNotesTool_UI_ctk.py   # GUI 진입점 (customtkinter)
├── ReleaseNotesTool_UI.py       # 원본 tkinter 프로토타입 (참고용)
├── full_pipeline.py             # build_preview() + commit_preview() + run_full_pipeline()
├── notes_to_for_devnotes.py     # 체크인 ID로 Notes.txt 필터링
├── ReleaseNotesCreatorv4.py     # DevNotes.txt → ReleaseNotes.txt 변환
├── docs/                        # README의 텍스트 버전
└── README.md
```

### 파이프라인 아키텍처

미리보기에서 사이드 이펙트가 발생하지 않도록 백엔드가 분리되어 있습니다:

```
build_preview(devnotes, patch, checkinids, notes)
    → PipelinePreview   (순수 / 읽기 전용)

commit_preview(preview, make_backup=True)
    → 파일 작성 + 백업 생성

run_full_pipeline(...)   # 하위 호환용 원샷 래퍼
    = commit_preview(build_preview(...))
```

---

## 입력 파일 형식

### `checkinid.txt`

`N.NNNN` 형식의 체크인 버전 번호를 포함하는 텍스트라면 무엇이든 가능합니다.
이름은 선택 사항이며, 매칭에는 숫자 부분만 사용됩니다.

```
alice 0.4091
bob 0.3968
0.4260
```

### `Notes.txt`

원시 개발자 노트. 각 체크인 블록은 `Checkin ID:`로 시작하며 80개 하이픈
구분선으로 분리됩니다. 도구는 DevNotes에 삽입하기 전 내부 전용 헤더
(`Developer:`, `Timestamp:`, `Release Notes Needed:`, `[Auto Merge Wizard]`
블록 등)를 자동으로 제거합니다.

### `DevNotes.txt`

`Base Version: ...` 라인으로 시작해야 합니다. 새 패치는 이 라인 바로
아래에 삽입됩니다.

---

## 독립 실행 파일로 빌드하기

### macOS / Linux

```bash
pip install pyinstaller

python3 -m PyInstaller --clean --onefile --windowed \
    --collect-all customtkinter --collect-all darkdetect \
    --name ReleaseNotesTool ReleaseNotesTool_UI_ctk.py
```

### Windows

```bat
pip install pyinstaller

python -m PyInstaller --clean --onefile --windowed --collect-all customtkinter --collect-all darkdetect --name ReleaseNotesTool ReleaseNotesTool_UI_ctk.py
```

결과물:
- macOS / Linux: `dist/ReleaseNotesTool`
- Windows: `dist/ReleaseNotesTool.exe`

`--collect-all` 플래그는 customtkinter의 테마 및 폰트 에셋을 실행 파일에
포함시키기 위해 필요합니다.

> **참고:** PyInstaller 빌드 결과물은 플랫폼별로 다릅니다. 배포 대상 OS와
> 같은 환경에서 빌드해야 합니다.

---

## 백업에서 복원하기

백업은 `DevNotes.txt`와 같은 폴더에 타임스탬프 파일명으로 저장됩니다:

```
DevNotes.txt
DevNotes.20260516_205412.bak.txt   ← 5월 16일 오후 8:54 백업
DevNotes.20260517_091203.bak.txt   ← 5월 17일 오전 9:12 백업
```

복원하려면 원하는 백업 파일의 이름을 `DevNotes.txt`로 변경하면 됩니다
(기존 파일은 덮어쓰기). 인앱 "Backup에서 복원" 기능은 향후 추가될 예정입니다.

---

## 로드맵 (Roadmap)

- [ ] 인앱 백업 복원 UI
- [ ] 세션 간 마지막 사용 경로 기억
- [ ] 기존 DevNotes 기반 다음 패치 번호 자동 제안
- [ ] 메인 창 내 출력 미리보기 패널

---

## 작성자

Written by Matthew Lee.
