# 슬라이드 5 영상 콘티 v3 (30초 · 실사 + 화면 녹화 + AI 생성 하이브리드)

구조: 실사 오프닝 → 폰 줌인 → 데스크톱 앱(입력→파싱→재질문→저장→연구노트→그래프뷰)
→ **그래프 화면에서 그대로 이어지는 확장**: 노드 증식·줌아웃 → 대한민국을 뒤덮고 →
지구 전체 네트워크 → 화이트 전환·로고.

오디오: 나레이션·BGM 없음, **효과음만** (발표자 발화가 나레이션 역할). 후반부(컷 5)는
발화와 1:1 싱크가 아니라 "자산이 쌓여 확장된다"는 분위기 싱크다 — 의도된 선택.

| 컷 | 시간 | 내용 | 제작 방식 |
|---|---|---|---|
| 1 | 0~4s | 실험 끝, 연구원이 폰을 들고 타이핑 | 실사 촬영 (또는 AI 생성) |
| 2 | 4~7s | 폰 화면으로 쭉 줌인 → 화이트 플래시 → 컴퓨터 화면 | 실사 + 편집 전환 |
| 3 | 7~12s | 실험 로그가 입력되는 앱 화면 | 화면 녹화 (데스크톱) |
| 4 | 12~18s | 파싱→재질문→저장 → 연구노트 → **그래프뷰 진입** | 화면 녹화 (데스크톱) |
| 5 | 18~27s | 그 그래프에서 노드 증식·줌아웃 → 대한민국 → 지구 | AI 생성 (2단계 체인) |
| 6 | 27~30s | 화이트 전환 → LAB GENE 로고 | 편집 (CapCut) |

---

## 컷 1 — 실사: 폰 타이핑 (0~4초)

**추천: 직접 촬영.** 실험실(또는 실험대 느낌 배경)에서 팀원이 장갑을 벗으며 폰을
집어 들고 타이핑. 손과 폰 화면이 보이는 오버숄더/클로즈업. 조명은 실험실 형광등
그대로, 흔들림 약간 있어도 됨(현장감). 폰 화면 내용은 식별 안 되는 거리면 뭐든 OK.

**대안: AI 생성 프롬프트**:

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
- 화면이 프레임을 거의 채우는 순간 → **0.2초 화이트 플래시** → **데스크톱 앱
  화면(컷 3)으로 전환**. "폰으로 기록한 게 연구실 시스템에 들어갔다"는 읽힘.
- 라벨 없음 — 전환 컷은 깨끗하게.

## 컷 3 — 화면 녹화: 자연어 로그 입력 (7~12초)

**녹화 준비** (5분):

```powershell
$env:HORCRUX_VAULT = "C:\Users\지완\labgene-demo-vault"
cd C:\Users\지완\claude\horcrux\.claude\worktrees\web-impl
horcrux serve
```

- 크롬 시크릿 창, **F11 전체화면**, 줌 110~125%, 북마크바 숨김. 데스크톱 뷰로 녹화.
- 데모 볼트는 기록 11건 + 그래프 완전 연결(노드 30개) 상태로 시딩돼 있다.
- 홈 → "실험 기록" → 아래 로그 붙여넣기. **타이핑 연출**: 붙여넣은 뒤 마지막 한
  문장만 지웠다가 실제로 타이핑하면 "치는 중" 장면이 나온다.

```
오늘 ALD로 HfO2 증착 다시 함. 이번엔 사이클을 350으로 올려봄. 온도 250도,
압력 1.2, 오존은 80으로 유지. 두께는 11.7nm 나옴. 막질 확인은 다음주에 XRD로 할 예정.
```

- **후반**: 입력창 클로즈업. 라벨: **자연어 입력**.

## 컷 4 — 화면 녹화: 파싱→재질문→저장→그래프뷰 진입 (12~18초)

한 컷에 많이 들어가므로 **넉넉히 찍고 편집에서 점프컷+속도 램프로 6초에 압축**한다.

1. 전송 → 파싱 로딩("분석 중...") — 편집에서 1초로 압축
2. 구조 패널에 필드 채워진 모습(제목·ALD-02·단위 붙은 파라미터 — 관례 반영 결과)
3. AI 재질문 → 칩 **"문제 없음"** → **"특이사항 없음"** 클릭
4. "검토 후 저장" → **저장하기** → 연구노트 목록(제목 달린 기록들) 1초 스침
5. 사이드바 **그래프뷰** 클릭 → **진입 순간 노드들이 퍼지며 자리잡는 애니메이션**
   (이 마지막 1~1.5초가 컷 5로 이어지는 브릿지다)

- **후반**: 재질문 말풍선 클로즈업, 저장 클릭 리플. 라벨 2개: **AI 구조화**, **재질문**.
- **그래프 화면이 안정된 마지막 프레임을 스크린샷으로 저장**해둔다 — 컷 5 생성의
  시작 이미지가 된다.

## 컷 5 — AI 생성: 노드 증식 → 대한민국 → 지구 (18~27초)

컷 4의 그래프 화면에서 **그대로 이어지는** 확장 시퀀스. 9초라 대부분의 생성 모델
한도(5~10초)에 걸리니 **2단계 체인**으로 뽑는다: 클립 A(그래프→대한민국) 마지막
프레임을 캡처해 클립 B(대한민국→지구)의 시작 이미지로 넣는다.

**클립 A — 그래프 증식 → 대한민국 (약 5초)**
(시작 이미지: 컷 4 마지막 그래프 스크린샷)

> EN: Starting exactly from this screenshot of a web app's knowledge-graph view
> (colored nodes connected by thin lines on a light background): new glowing nodes
> keep popping into existence one after another, edges multiplying, the network
> growing denser and denser. The camera pulls back steadily; as it zooms out, the
> light background gradually dissolves into a night-time satellite view of South
> Korea, and the multiplying glowing blue nodes now blanket the entire Korean
> peninsula like interconnected city lights. Smooth continuous zoom-out, seamless
> transition, cinematic, no text, no narration, no music, no watermark.

> KO: 웹앱 지식 그래프 화면 스크린샷(밝은 배경 위 색색 노드와 가는 연결선)에서
> 정확히 이어서 시작: 빛나는 새 노드들이 연쇄적으로 계속 생겨나고 엣지가 증식하며
> 네트워크가 점점 조밀해진다. 카메라가 꾸준히 뒤로 빠지고, 줌아웃되는 동안 밝은
> 배경이 서서히 밤의 대한민국 위성 뷰로 디졸브되며, 증식하는 파란 발광 노드들이
> 한반도 전체를 도시 불빛처럼 뒤덮는다. 부드럽고 끊김 없는 줌아웃, 심리스 전환,
> 시네마틱. 텍스트·나레이션·음악·워터마크 없음.

**클립 B — 대한민국 → 지구 (약 4초)**
(시작 이미지: 클립 A 마지막 프레임)

> EN: Seamless continuation from this frame: the camera keeps pulling back from
> night-time South Korea covered in a glowing blue node network, rising into space.
> As the Earth's curvature appears, node clusters ignite across other continents,
> connecting into one luminous planetary knowledge network covering the whole globe.
> Slow majestic zoom-out ending on the full Earth from space, deep blue and white
> glow palette, cinematic, no text, no narration, no music, no watermark.

> KO: 이 프레임에서 심리스하게 이어서: 파란 발광 노드망으로 뒤덮인 밤의 대한민국에서
> 카메라가 계속 뒤로 빠져 우주로 상승한다. 지구 곡률이 드러나면서 다른 대륙들에서도
> 노드 클러스터가 연쇄 점화되어, 전 지구를 덮는 하나의 빛나는 행성 지식 네트워크로
> 연결된다. 느리고 장엄한 줌아웃, 우주에서 본 지구 전체로 마무리, 딥블루·화이트 발광
> 팔레트, 시네마틱. 텍스트·나레이션·음악·워터마크 없음.

- 컷 4 실녹화 끝 프레임과 클립 A 첫 프레임이 같은 그림이므로 이음새는 하드컷으로
  충분하다 (어긋나면 0.2초 디졸브).
- 생성 결과에서 노드 색·배경이 앱과 너무 다르면, 프롬프트 맨 앞에 "Match the exact
  colors of the input image."를 추가해 재생성.

## 컷 6 — 로고 (27~30초)

- CapCut: 화이트로 0.3초 플래시 전환 → 흰 배경 중앙에 **LAB GENE** 로고(엠블럼 +
  텍스트) 페이드인, 아래 작게 "연구실의 경험을 자산으로". 2초 홀드 후 끝.

---

## 녹화분(컷 3~4) 모션그래픽 레시피 — CapCut

밋밋한 화면 녹화를 "제작된 영상"으로 바꾸는 처리 6가지. 전부 캡컷 무료 기능이다.

1. **프레임 연출 (가장 효과 큼)** — 녹화본을 그대로 꽉 채우지 말고: 배경에 은은한
   그라데이션(네이비→블랙) 깔고, 녹화 클립을 95% 크기로 올려 모서리 라운드 + 그림자.
   순간적으로 "SaaS 광고 룩"이 된다. 단, 컷 4 끝(그래프)에서는 클립을 100%로 키워
   프레임을 없애야 컷 5와 이음새가 맞는다.
2. **줌 키프레임** — 클립의 배율·위치에 키프레임 2개: 행동 직전(100%) → 행동 지점
   (130~150%, 해당 영역 중앙). 클릭·입력마다 카메라가 따라다니는 느낌. 컷당 2회 이내.
3. **스포트라이트** — 구조 패널이 채워지는 순간: 클립 복제 → 위 클립에 마스크(패널
   영역) → 아래 클립 밝기 -40%. 주변이 어두워지고 패널만 빛난다.
4. **클릭 리플** — 칩 클릭·저장 클릭 순간에 스티커 "click circle" 또는 원형 도형을
   0.3초 스케일 팝으로.
5. **라벨 슬라이드인** — 빨간 텍스트 + 꺾인 지시선(스티커 "arrow"), 등장 0.3초
   슬라이드인, 사라질 때 페이드. 화면당 최대 2개.
6. **속도 램프** — 타이핑·로딩 구간 2~3배속, 재질문 답변·구조 패널 완성 순간은 정속.

지름길: 녹화 자체를 **클릭 자동 줌 녹화 툴**(크롬 확장 Cursorful 류)로 하면 2번이
공짜다. 그 결과물에 1·5·6번만 얹어도 충분히 간지난다. 전부 할 필요 없다 —
**1번은 필수, 나머지는 시간 되는 만큼.**

## 편집 체크리스트

- [ ] 총 길이 29초 내외 (발화가 밀리면 영상이 먼저 끝나는 게 낫다)
- [ ] 라벨은 발화 키워드와 동일 단어만: 자연어 입력 / AI 구조화 / 재질문
- [ ] 컷 4 끝 그래프 프레임 = 컷 5 클립 A 첫 프레임 (이음새 확인)
- [ ] **효과음** (CapCut 내장 라이브러리, 볼륨 40~60%):
  - 컷 2·6 화이트 플래시 → 짧은 우시(whoosh)
  - 컷 4 재질문 칩 클릭 → 가벼운 UI 탭음, 저장 → 확정음 1회
  - 컷 4 그래프 진입 + 컷 5 노드 증식 → 연쇄 팝(pop) 사운드
  - 컷 5 대한민국→지구 줌아웃 → 낮게 깔리는 라이저(riser) 하나
- [ ] BGM·나레이션 없음, AI 생성 클립에 딸려온 오디오 트랙 삭제
- [ ] 현장 리허설에서 스피커로 확인 — 효과음 과하면 파워포인트에서 영상 음소거
- [ ] 1080p 30fps 내보내기
