# horcrux

연구실 실험 기록·문제 진단 CLI. 실험 로그를 자연어로 입력하면 LLM이 구조화해
마크다운 볼트(옵시디언 호환)에 저장하고, 문제 질의 시 과거 유사 사례를 검색해
근거와 함께 진단을 보조한다.

## 설치

```
pip install -e .
set ANTHROPIC_API_KEY=...           # 또는 ant auth login
set HORCRUX_VAULT=example-vault     # 랩 볼트 경로 (연구실 1곳 = 볼트 1개)
```

검색은 LLM-select: LLM이 레코드·위키 카탈로그를 읽고 유사 사례를 직접 고른다.
임베딩·벡터 인덱스 없이 API 키 하나로 동작한다.

## 사용

```
horcrux seed          # 합성 데모 데이터 생성 + 위키 편찬 (개발용)
horcrux log           # 실험 로그 기록 (부족 정보 되물음, 저장 후 위키 자동 편찬)
horcrux ask           # 문제 질의 (과거 유사 사례·위키 근거로 답변)
horcrux absorb        # 위키 재편찬 (log/seed가 자동 실행 — 실패 시 재시도용)
horcrux feedback <id> --resolved y --cause "타겟 산화"   # 결과 피드백
```

## 연구실 설정 (§2a)

볼트에 `config.yaml`을 두면 기록 시 하드 게이트가 적용된다 (없으면 5개 카테고리 전부 기본):

```
required_fields: [objective, parameters, results, symptom, actions_taken]
required_parameters:
  - 기판 온도
  - 챔버 습도
```

설계 문서: `docs/superpowers/specs/2026-07-19-horcrux-mvp-design.md`
