# 백엔드 작업 요청서 — 참고문헌 저장

프론트 세션 → 백엔드 세션. 원 스펙: `docs/superpowers/specs/2026-08-06-references-design.md`
(frontend 브랜치, 3bac5b6). 프론트 파트는 이미 frontend 브랜치에 구현 완료(4769966) —
아래 계약이 붙는 순간 바로 동작한다.

## 요약

레코드에 참고문헌 리스트를 저장한다. 필요한 변경은 세 가지, 전부 `src/horcrux/` 안이다.
새 코어 로직 없음 — 기존 load→수정→save 패턴 재사용.

## 1. records.py — Reference 모델

```python
class Reference(BaseModel):
    # Literal이 아니라 str — 나중에 "pdf" 타입이 추가돼도 구버전 백엔드가
    # 신버전 md를 읽다 검증 실패하지 않게 느슨하게 둔다. UI가 3종만 만든다.
    type: str = "link"        # "paper" | "link" | "record" ("pdf" 예약)
    title: str = ""           # 표시명
    url: str = ""             # paper/link용. DOI는 프론트가 https://doi.org/... 로 정규화해서 보냄
    record_id: str = ""       # record 타입만 사용
```

`ExperimentRecord`에 필드 추가:

```python
    references: list[Reference] = Field(default_factory=list)
```

`default_factory=list`이므로 기존 md 마이그레이션 불필요. frontmatter 직렬화는
기존 `model_dump()` 경로로 자동.

## 2. server.py — PUT 엔드포인트

```python
class ReferencesIn(BaseModel):
    references: list[Reference]   # records.py에서 import

@app.put("/api/records/{record_id}/references")
def api_put_references(record_id: str, inp: ReferencesIn):
    p = record_path(cfg.vault, record_id)
    if not p.exists():
        raise HTTPException(404, f"레코드 없음: {record_id}")
    with _VAULT_LOCK:
        rec, body = load_record(p)
        rec.references = inp.references
        save_record(cfg.vault, rec, ...)   # 기존 저장 경로에 맞게 — body 보존 필수
    return {"record": _meta(rec)}
```

주의: `save_record` 시그니처가 원문 body를 어떻게 받는지에 맞춰 **본문이 유실되지
않게** 저장할 것 (update_resolution/feedback.py가 이미 같은 문제를 풀었다면 그 경로 재사용).

## 3. server.py — 목록 메타 확장

`_META_KEYS` 튜플에 `"references"` 추가:

```python
_META_KEYS = ("id", "date", "experiment_type", "objective", "equipment", "materials",
              "symptom", "resolution", "needs_review", "followup_of", "references")
```

목적: 그래프뷰가 `GET /api/records` 한 번으로 record 참조 엣지를 클라이언트에서
유도한다. 상세(GET /api/records/{id})는 model_dump라 자동 포함.

## 응답 계약 (프론트가 이미 이 형태를 기대함)

- `PUT` 성공: `{"record": <_meta() 형식 메타>}` — references 포함
- 404: `{"detail": "레코드 없음: ..."}` (기존 HTTPException 기본 형식)
- 422: pydantic 검증 실패 (FastAPI 기본, 프론트는 detail 문자열 표시)

## 테스트 (pytest — `--basetemp=.pytest_tmp` 필수)

tests/test_server.py에:

1. **PUT 왕복**: 레코드 저장 → PUT references 2개(paper+record) → GET 상세로
   references 일치 + 본문(body) 보존 확인
2. **빈 references 호환**: 기존 스타일(references 키 없는) md를 직접 써두고
   GET 목록/상세가 `references: []`로 응답
3. **404**: 없는 id에 PUT → 404

## 하지 않는 것

- `web/` 파일 수정 금지 (프론트 세션 담당 — 이미 구현됨)
- retrieval/diagnose에 references 반영 안 함 (스펙에서 제외)
- 파일 업로드 없음 (별도 스펙 예정)

## 병합 순서

backend 브랜치 → main 머지·푸시가 먼저. 그 다음 프론트 세션이 frontend를 main에
머지해 실기기 검증한다. 끝나면 이 세션(프론트)에 알려달라.
