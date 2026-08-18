# 슬라이드 5 영상 콘티 v2 (30초 · 실사 + 화면 녹화 + AI 생성 하이브리드)

구조: 실사 오프닝 → 매치컷으로 서비스 진입(실녹화) → 그래프 버스트·지구 확장(AI 생성/모션그래픽) → 로고.
무음 영상 — 발표자 발화가 나레이션. 후반부(컷 5~)는 발화와 1:1 싱크가 아니라
"자산이 쌓여 확장된다"는 분위기 싱크다 — 의도된 선택.

| 컷 | 시간 | 내용 | 제작 방식 |
|---|---|---|---|
| 1 | 0~4s | 실험 끝, 연구원이 폰을 들고 타이핑 | 실사 촬영 (또는 AI 생성) |
| 2 | 4~7s | 폰 화면으로 쭉 줌인 → 컴퓨터 화면(서비스)으로 전환 | 실사 + 편집 전환 |
| 3 | 7~12s | 실험 로그가 입력되는 앱 화면 | 화면 녹화 (데스크톱) |
| 4 | 12~19s | 파싱 로딩 → 재질문 → 저장 | 화면 녹화 (데스크톱) |
| 5 | 19~24s | 그래프: 중앙 노드에서 파바바박 확산 | AI 생성 or 모션그래픽 |
| 6 | 24~27.5s | 줌아웃 — 노드망이 지구를 덮으며 연결 | AI 생성 |
| 7 | 27.5~30s | 화이트 전환 → LAB GENE 로고 | 편집 (CapCut) |

---

## 컷 1 — 실사: 폰 타이핑 (0~4초)

**추천: 직접 촬영.** 실험실(또는 실험대 느낌 배경)에서 팀원이 장갑을 벗으며 폰을
집어 들고 타이핑. 손과 폰 화면이 보이는 오버숄더/클로즈업. 조명은 실험실 형광등
그대로, 흔들림 약간 있어도 됨(현장감).

- 폰 화면엔 앱을 실제로 띄울 필요 없음 — 메모장이든 뭐든, 줌인이 시작되기 전엔
  화면 내용이 식별되지 않는 거리에서 찍는다.

**대안: AI 생성 프롬프트** (실촬영이 어려울 때):

> EN: Handheld cinematic shot, a young researcher in a white lab coat and nitrile
> gloves finishes an experiment at a cluttered wet-lab bench (beakers, ALD equipment
> panel with indicator lights), pulls off one glove, picks up a smartphone and starts
> typing quickly with both thumbs. Over-the-shoulder framing, shallow depth of field,
> fluorescent laboratory lighting, realistic, 4k, no text overlays, no narration, no music.

> KO: 핸드헬드 시네마틱 숏. 흰 실험 가운과 니트릴 장갑을 낀 젊은 연구원이 실험 기구가
> 널린 웻랩 실험대(비커, 지시등이 켜진 ALD 장비 패널)에서 실험을 마치고, 장갑 한쪽을
> 벗은 뒤 스마트폰을 집어 양손 엄지로 빠르게 타이핑한다. 오버숄더 구도, 얕은 심도,
> 실험실 형광등 조명, 실사풍, 4k. 텍스트 오버레이·나레이션·음악 없음.

## 컷 2 — 줌인 전환: 폰 → 컴퓨터 화면 (4~7초)

- 컷 1의 마지막 1초에서 폰 화면을 향해 **디지털 줌인**(CapCut 키프레임 확대).
- 화면이 프레임을 거의 채워 하얗게 뭉개지는 순간 → **0.2초 화이트 플래시** →
  **데스크톱 앱 화면(컷 3)으로 전환**. 기기가 폰→컴퓨터로 바뀌므로 하드컷보다
  화이트 플래시를 꼭 넣어야 어색하지 않다 ("폰으로 기록한 게 연구실 시스템에
  들어갔다"는 읽힘도 생긴다).
- 라벨 없음 — 전환 컷은 깨끗하게.

## 컷 3 — 화면 녹화: 자연어 로그 입력 (7~12초)

**녹화 준비** (5분):

```powershell
$env:HORCRUX_VAULT = "C:\Users\지완\labgene-demo-vault"
cd C:\Users\지완\claude\horcrux\.claude\worktrees\web-impl
horcrux serve
```

- 크롬 시크릿 창, **F11 전체화면**, 줌 110~125% (글자가 영상에서 읽히게), 북마크바 숨김.
  데스크톱 뷰 그대로 녹화한다. 데모 볼트는 기록 11건 시딩돼 있어 화면이 풍성하다.
- 홈 → "실험 기록" → 아래 로그를 붙여넣기. **타이핑 연출**: 붙여넣은 뒤 마지막
  한 문장만 지웠다가 실제로 타이핑하면 "치는 중" 장면이 나온다.

```
오늘 ALD로 HfO2 증착 다시 함. 이번엔 사이클을 350으로 올려봄. 온도 250도,
압력 1.2, 오존은 80으로 유지. 두께는 11.7nm 나옴. 막질 확인은 다음주에 XRD로 할 예정.
```

- **후반**: 입력창 클로즈업. 라벨: **자연어 입력**.

## 컷 4 — 화면 녹화: 파싱 → 재질문 → 저장 (12~19초)

- 전송 → 파싱 로딩("분석 중...") 잠깐 보여주고(편집에서 1초로 압축) →
  구조 패널/구조 탭에 필드가 채워진 모습(제목·ALD-02·단위 붙은 파라미터 — 관례가
  "ALD"→ALD-02, "250도"→250 °C로 채운 결과) → AI 재질문에 칩 **"문제 없음"** →
  **"특이사항 없음"** 클릭 → "검토 후 저장" → **저장하기**.
- **후반**: 재질문 말풍선 클로즈업 → 저장 버튼 클릭에서 컷아웃. 라벨 2개:
  **AI 구조화**, **재질문**. 대기 시간은 전부 점프컷.

## 컷 5 — AI 생성/모션그래픽: 그래프 버스트 (19~24초)

앱의 그래프뷰를 실녹화하지 않는다(버스트 애니메이션은 미구현 기능) — 옵시디언
그래프 스타일의 연출 컷으로 제작한다.

**AI 생성 프롬프트**:

> EN: Motion graphics, dark navy background. A single glowing blue node appears at
> center, then dozens of nodes burst outward one after another in rapid elastic pops,
> connected by thin glowing edges, forming an expanding knowledge-graph constellation.
> Some nodes are labeled with tiny Korean tags (장비, 재료, 실패사례) — keep labels
> minimal and crisp. Obsidian-style force-directed graph aesthetic, subtle depth of
> field, smooth 60fps motion, continuous outward growth, no camera shake,
> no narration, no music, no watermark.

> KO: 모션그래픽, 짙은 네이비 배경. 중앙에 빛나는 파란 노드 하나가 나타난 뒤,
> 수십 개의 노드가 탄성 있는 팝 모션으로 연쇄적으로 파바박 터져 나오며 가는 발광
> 엣지로 연결되어 확장하는 지식 그래프 성좌를 이룬다. 일부 노드에 작은 한글 라벨
> (장비, 재료, 실패사례) — 라벨은 최소한으로 선명하게. 옵시디언 그래프 뷰 스타일의
> 포스 그래프 미학, 은은한 심도, 부드러운 60fps, 끊김 없는 확산 모션, 카메라 흔들림
> 없음. 나레이션·음악·워터마크 없음.

- 컷 4(밝은 앱 화면)에서 컷 5(어두운 배경)로 넘어갈 때 0.3초 디졸브.
- 한글 라벨이 뭉개지면 라벨 없는 버전으로 뽑고 CapCut에서 텍스트를 얹어라 — 그게 안전하다.
- 라벨(편집에서): **기록이 자산이 된다**.

## 컷 6 — AI 생성: 지구를 덮는 노드망 (24~27.5초)

> EN: Seamless continuation: the camera pulls back from the glowing blue knowledge
> graph, revealing it floats above a dark Earth seen from space at night. As the
> zoom-out continues, thousands of node clusters light up across continents like city
> lights, connecting into one luminous planetary network. Cinematic space shot, deep
> blue and white glow palette, slow steady zoom-out, awe-inspiring scale,
> no text, no narration, no music, no watermark.

> KO: 이어지는 연속 샷: 카메라가 빛나는 파란 지식 그래프에서 뒤로 빠지면, 그것이
> 밤의 지구 위에 떠 있음이 드러난다. 줌아웃이 계속되며 대륙 곳곳에서 수천 개의 노드
> 클러스터가 도시 불빛처럼 켜지고, 하나의 발광하는 행성 네트워크로 연결된다.
> 시네마틱 우주 숏, 딥블루·화이트 발광 팔레트, 느리고 안정적인 줌아웃, 압도적 스케일.
> 텍스트·나레이션·음악·워터마크 없음.

- 컷 5와 같은 툴·같은 팔레트로 생성해야 이어진다 (가능하면 컷 5의 마지막 프레임을
  이미지 입력으로 넣고 이어서 생성 — image-to-video).

## 컷 7 — 로고 (27.5~30초)

- CapCut: 화이트로 0.3초 플래시 전환 → 흰 배경 중앙에 **LAB GENE** 로고(엠블럼 +
  텍스트) 페이드인, 아래 작게 "연구실의 경험을 자산으로". 2초 홀드 후 끝.

---

## 편집 체크리스트

- [ ] 총 길이 29초 내외 (발화가 밀리면 영상이 먼저 끝나는 게 낫다)
- [ ] 라벨은 발화 키워드와 동일 단어만: 자연어 입력 / AI 구조화 / 재질문
- [ ] 컷 4→5 밝음→어둠 전환에 0.3초 디졸브, 컷 6→7 화이트 플래시
- [ ] 무음 확인 (AI 생성 클립에 붙은 오디오 트랙 삭제)
- [ ] 1080p 30fps 내보내기
