# 연구노트 참고문헌 설계

2026-08-06 · 브레인스토밍 확정본

## 목적

저장된 실험 레코드에 참고문헌(논문·웹 링크·내부 레코드)을 사후에 붙이고,
연구노트 상세에서 보고, 내부 레코드 참조는 그래프뷰 엣지로 탐색한다.

## 범위

**이번:** 텍스트 참조 3종 — paper(논문), link(웹), record(내부 레코드).
**제외 (다음 스펙):** PDF 등 파일 첨부 — 업로드·저장 인프라가 필요해서 "파일 첨부
인프라" 스펙으로 분리. `type` 필드에 `pdf`가 들어갈 자리만 예약한다.
**제외 (YAGNI):** 논문·링크의 그래프 노드화, 저장 전 미리보기에서 참조 입력,
로그 본문 LLM 추출, 진단(retrieval) 반영.

## 데이터 모델 (백엔드 — records.py)

```python
class Reference(BaseModel):
    # Literal이 아니라 str — 나중에 "pdf" 타입이 추가돼도 구버전 백엔드가
    # 신버전 md를 읽다 검증 실패하지 않게 느슨하게 둔다. UI가 3종만 만든다.
    type: str = "link"        # "paper" | "link" | "record" ("pdf" 예약)
    title: str = ""           # 표시명. paper는 "제목 (첫저자, 연도)" 권장
    url: str = ""             # paper/link. DOI는 https://doi.org/... 로 정규화된 값
    record_id: str = ""       # record 타입만 사용

class ExperimentRecord(BaseModel):
    ...
    references: list[Reference] = Field(default_factory=list)
```

- `default_factory=list` → 기존 md 레코드 마이그레이션 불필요.
- frontmatter에 그대로 직렬화된다 (`model_dump()` 경유, 기존 save/load 재사용).

## API 계약 (백엔드 — server.py)

계약 변경은 아래 두 개가 전부다.

### PUT /api/records/{record_id}/references

- body: `{"references": [{"type": "paper", "title": "...", "url": "...", "record_id": ""}, ...]}`
- 동작: 리스트 통째 교체 (추가·수정·삭제 모두 이 하나로). `_VAULT_LOCK` 잡고
  load → `rec.references = ...` → `save_record` 패턴 (update_resolution과 동일).
- 응답: `{"record": <갱신된 메타>}` (기존 `_meta()` 형식)
- 404: 레코드 없음. 422: pydantic 검증 실패 (FastAPI 기본).

### GET /api/records 메타 확장

- `_META_KEYS`에 `"references"` 추가 — 목록 응답의 각 레코드에 references 포함.
- 그래프뷰가 클라이언트에서 엣지를 유도하는 기존 방식을 유지하기 위함.
- 상세(GET /api/records/{id})는 `model_dump()`라 자동 포함.

## DOI 자동 조회 (프론트 전용 — 백엔드 무관)

- paper 타입 폼에서 DOI 입력 → "조회" 버튼 → 브라우저가 Crossref
  `https://api.crossref.org/works/{doi}` 직접 fetch (CORS 허용, 서버 경유 없음).
- 응답의 `message.title[0]`, `message.author[0].family`, 발행 연도를
  `"제목 (성, 연도)"`로 조합해 title 자동 채움. 저자·연도 없으면 제목만.
- DOI 정규화: `10.x/...` 입력과 `https://doi.org/10.x/...` 붙여넣기 모두 허용,
  저장 시 항상 `https://doi.org/...` URL로 변환. (순수 함수 `normalizeDoi`,
  DOI 패턴(`10.`으로 시작)이 아니면 null 반환 → [조회] 비활성, 값은 일반 URL로 저장)
- 실패 처리: 5초 타임아웃·404·네트워크 오류 → 폼에 에러 한 줄, 수동 입력으로
  계속 진행 가능. 조회는 보조 수단이며 필수 경로가 아니다.

## UI (프론트 — 연구노트 상세 Notes.tsx)

"원인 후보" 섹션 아래 "참고문헌" 섹션.

- **목록**: 타입 아이콘(📄 paper / 🔗 link / 🧪 record) + title.
  - paper·link: 새 탭으로 url 열기 (`rel="noreferrer"`)
  - record: `/notes/{record_id}` 이동. 대상 md가 없으면 "(없는 레코드)" 표시
  - 각 항목 우측 ✕ 삭제
- **추가 폼** ("＋ 참고문헌 추가" 버튼으로 토글):
  - 타입 칩 3개 (논문/링크/레코드)
  - paper: DOI 입력 + [조회] + title 입력(자동 채움 후 수정 가능)
  - link: URL 입력 + 설명(title) 입력
  - record: 레코드 셀렉트 (listRecords에서 id + objective 표시, 자기 자신 제외)
- 추가·삭제 즉시 PUT 반영. 실패 시 에러 문구 + 변경 롤백(목록 재조회).
- 모바일: 폼 필드 세로 스택, 터치 타깃 44px — 기존 반응형 규칙 준수.

## 그래프뷰 (프론트 — graph.ts / Graph.tsx)

- `buildGraph`: 각 레코드의 `references` 중 `type === "record"`이고 대상이
  존재하는 것만 실험→실험 엣지로 추가 (followup_of와 동일 규칙, 중복 엣지 dedup).
- 노드 추가 없음. paper/link는 그래프에 올리지 않는다.

## 구현 분담

| 파트 | 내용 | 담당 |
|---|---|---|
| 백엔드 | Reference 모델, PUT 엔드포인트, _META_KEYS 확장, pytest | **backend 세션** (src/horcrux/는 이 세션 수정 금지) |
| 프론트 | types/api 클라이언트, Notes 참고문헌 섹션, DOI 조회, graph 엣지, vitest | frontend 세션 (web-impl 워크트리) |

병합 순서: 백엔드 → 프론트 (백엔드 전에는 PUT이 404라 프론트 수동 검증 불가).
프론트 구현은 계약 기준으로 백엔드와 병행 시작 가능.

## 테스트

- 백엔드 (pytest): PUT 왕복(저장→조회 일치), 빈 references 기존 md 로드 호환,
  404 케이스.
- 프론트 (vitest): `normalizeDoi` 순수 함수(3케이스: bare DOI/doi.org URL/무효),
  buildGraph 참조 엣지(대상 존재/부재/중복), 참조 목록 렌더 1개.

## 에러 처리 요약

| 상황 | 동작 |
|---|---|
| PUT 404/500 | 에러 문구 + 목록 재조회로 롤백 |
| Crossref 실패 | 폼에 한 줄 안내, 수동 입력 지속 |
| record 참조 대상 삭제됨 | 상세 "(없는 레코드)", 그래프 엣지 미생성 |
