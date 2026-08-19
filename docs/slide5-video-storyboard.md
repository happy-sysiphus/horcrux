# 슬라이드 5 영상 콘티 v5 — 최종 (30초 · AI 생성 + 화면 녹화 하이브리드)

구조: AI 오프닝(연구자 뒷모습 폰 타이핑) → 폰 줌인 → 데스크톱 앱(입력→파싱→재질문→
저장→연구노트→그래프뷰) → 그래프에서 줌아웃하면 **다시 그 연구자** → 놀라 폰 낙하 →
폰부터 실험실 전체가 노드로 변환 → **노드가 된 실험실이 플라스크에 담김** → 정면 샷
줌아웃 → 화이트 → 로고.

오디오: 나레이션·BGM 없음, **효과음만**. 라벨(빨간 지시선 자막)은 딱 2개 — 컷 3
"자연어 입력", 컷 4 "재질문". 후반부(컷 5)는 발화와 분위기 싱크(의도된 선택).

| 컷 | 시간 | 내용 | 제작 |
|---|---|---|---|
| 1 | 0~4s | 연구자(뒷모습) 실험 마치고 폰 타이핑 | AI 생성 |
| 2 | 4~7s | 폰 화면 줌인 → 화이트 플래시 → 데스크톱 화면 | 편집 전환 |
| 3 | 7~11s | 자연어 로그 입력 | 화면 녹화 |
| 4 | 11~17s | 파싱→재질문→저장→연구노트→**그래프뷰 진입** | 화면 녹화 |
| 5 | 17~27.5s | 줌아웃→연구자 복귀→폰 낙하·노드화→실험실 전체 노드화→플라스크 담김→정면 샷 | 합성 + AI 2클립 |
| 6 | 27.5~30s | 정면 샷 줌아웃 → 화이트 → LAB GENE 로고 | 편집 |

---

## 컷 1 — AI 생성: 연구자 뒷모습 폰 타이핑 (0~4초)

**이 클립의 마지막 프레임이 컷 5의 앵커다** — 폰 화면이 어깨 너머로 뚜렷이 보이고,
폰 위치가 안정적이어야 한다(컷 5 박자 1의 합성 대상).

> EN: Over-the-shoulder cinematic shot from behind: a researcher in a white lab coat,
> back to camera, finishes an experiment at a cluttered wet-lab bench (beakers, ALD
> equipment panel with indicator lights), pulls off one nitrile glove, picks up a
> smartphone and types quickly with both thumbs. The phone screen is clearly visible
> over the shoulder and held steady, face never shown. Shallow depth of field,
> fluorescent laboratory lighting, realistic, 4k, stable framing, no text overlays,
> no narration, no music, no watermark.

> KO: 뒤에서 잡은 오버숄더 시네마틱 숏: 흰 실험 가운을 입은 연구원이 카메라에 등을
> 보인 채, 실험 기구가 널린 웻랩 실험대(비커, 지시등 켜진 ALD 장비 패널)에서 실험을
> 마치고 니트릴 장갑 한쪽을 벗은 뒤 스마트폰을 집어 양손 엄지로 빠르게 타이핑한다.
> 폰 화면이 어깨 너머로 뚜렷하게 보이고 흔들림 없이 유지되며, 얼굴은 나오지 않는다.
> 얕은 심도, 실험실 형광등 조명, 실사풍, 4k, 안정된 구도. 텍스트 오버레이·나레이션·
> 음악·워터마크 없음.

## 컷 2 — 줌인 전환: 폰 → 컴퓨터 화면 (4~7초)

- 컷 1 마지막 1초에 폰 화면을 향해 **디지털 줌인**(캡컷 배율 키프레임).
- 화면이 프레임을 거의 채우는 순간 → **0.2초 화이트 플래시** → 데스크톱 앱 화면(컷 3).
- 라벨 없음.

## 컷 3 — 화면 녹화: 자연어 로그 입력 (7~11초)

**녹화 준비**:

```powershell
$env:HORCRUX_VAULT = "C:\Users\지완\labgene-demo-vault"
cd C:\Users\지완\claude\horcrux\.claude\worktrees\web-impl
horcrux serve
```

- 크롬 시크릿 창, F11 전체화면, 줌 110~125%. 데모 볼트는 기록 11건 + 그래프 완전
  연결(노드 30개) 시딩 상태.
- 홈 → "실험 기록" → 아래 로그 붙여넣기 (마지막 한 문장은 지웠다가 실제 타이핑
  — "치는 중" 장면 연출):

```
오늘 ALD로 HfO2 증착 다시 함. 이번엔 사이클을 350으로 올려봄. 온도 250도,
압력 1.2, 오존은 80으로 유지. 두께는 11.7nm 나옴. 막질 확인은 다음주에 XRD로 할 예정.
```

- 라벨: **자연어 입력**.

## 컷 4 — 화면 녹화: 파싱→재질문→저장→그래프뷰 진입 (11~17초)

넉넉히 찍고 편집에서 점프컷+속도 램프로 6초 압축.

1. 전송 → 파싱 로딩(편집에서 1초로)
2. 구조 패널 채워진 모습(제목·ALD-02·단위 붙은 파라미터)
3. 재질문 → 칩 "문제 없음" → "특이사항 없음"
4. 저장하기 → 연구노트 목록 1초 스침
5. 그래프뷰 클릭 → **노드들이 퍼지며 자리잡는 진입 애니메이션**
   → **안정된 마지막 프레임을 스크린샷으로 저장** (컷 5 박자 1의 소스)

- 라벨: **재질문** (말풍선 옆). 저장 클릭에 리플.

## 컷 5 — 합성 + AI 생성: 원상복귀 → 노드화 → 플라스크 (17~27.5초)

### 박자 1 (17~19s) — 캡컷 합성: 그래프 → 연구자 복귀

- AI 생성이 아니라 **캡컷 키프레임 합성**: 컷 4의 그래프 화면(전체 프레임)을 배율
  키프레임으로 축소시키며, 아래 레이어에 컷 1 영상(연구자 뒷모습)을 깐다. 그래프
  화면이 **연구자 폰 화면 위치로 빨려 들어가며** 안착 — "이 모든 게 폰 안의 서비스였다"
  는 원상복귀 리빌.
- 그래프 클립의 끝 크기·위치를 폰 화면에 맞추는 키프레임 2개면 된다.

### 박자 2~3 (19~24s) — AI 클립 D1: 놀람·폰 낙하 → 실험실 전체 노드화

(시작 이미지: 컷 1 마지막 프레임)

> EN: Seamless continuation from this frame, over-the-shoulder back view of a
> researcher in a white lab coat holding a phone in a laboratory: the researcher
> flinches in wonder and lets the phone slip from their hand. The instant the phone
> hits the floor it bursts softly into glowing blue nodes connected by thin luminous
> edges. The node network spreads outward in a chain reaction — across the floor, up
> the lab bench, transforming beakers, the ALD equipment, and finally the researcher
> themselves into constellations of glowing nodes and edges, until the entire
> laboratory is a luminous knowledge graph floating in dark space. Tone of awe and
> wonder, not horror; warm blue-white glow, cinematic, smooth continuous motion,
> no text, no narration, no music, no watermark.

> KO: 이 프레임에서 심리스하게 이어서, 실험실에서 폰을 든 흰 가운 연구원의 뒷모습
> 오버숄더 뷰: 연구원이 경이에 차 움찔하며 폰을 손에서 놓친다. 폰이 바닥에 닿는
> 순간 부드럽게 터지며 가는 발광 엣지로 연결된 파란 노드들로 변한다. 노드 네트워크가
> 연쇄 반응처럼 바깥으로 번진다 — 바닥을 타고, 실험대 위로, 비커와 ALD 장비, 그리고
> 마침내 연구원 자신까지 빛나는 노드와 엣지의 성좌로 변환되어, 실험실 전체가 어두운
> 공간에 떠 있는 발광 지식 그래프가 된다. 공포가 아니라 **경이와 감탄의 톤**, 따뜻한
> 블루-화이트 발광, 시네마틱, 부드럽고 끊김 없는 모션. 텍스트·나레이션·음악·워터마크 없음.

### 박자 4 (24~27.5s) — AI 클립 D2: 노드 실험실 → 플라스크 담김 → 정면 샷

(시작 이미지: D1 마지막 프레임)

> EN: Seamless continuation from this frame: the entire laboratory made of glowing
> blue nodes and edges begins to swirl gently and contract, flowing downward like a
> luminous liquid constellation into the wide mouth of a giant transparent
> Erlenmeyer flask below, camera looking down from above as the node-lab settles
> glowing inside the glass. Then the camera sweeps down in one smooth arc to an
> eye-level front view of the flask standing on a clean dark surface, the miniature
> glowing laboratory network floating inside. Cinematic product-shot lighting, deep
> blue and white glow palette, smooth camera path, no text, no narration, no music,
> no watermark.

> KO: 이 프레임에서 심리스하게 이어서: 발광하는 파란 노드와 엣지로 이루어진 실험실
> 전체가 부드럽게 소용돌이치며 수축하고, 빛나는 액체 성좌처럼 아래에 놓인 거대한
> 투명 삼각 플라스크의 넓은 입구로 흘러 들어간다. 카메라는 위에서 내려다보며 노드
> 실험실이 유리 안에 담겨 빛나는 것을 담는다. 이어 카메라가 한 번의 부드러운 호를
> 그리며 **아이레벨 정면 샷**으로 내려온다: 어두운 깔끔한 표면 위에 선 플라스크,
> 그 안에 미니어처 발광 실험실 네트워크가 떠 있다. 시네마틱 제품 촬영 조명, 딥블루·
> 화이트 발광 팔레트, 부드러운 카메라 경로. 텍스트·나레이션·음악·워터마크 없음.

- **폴백**: D1에서 놀람·낙하가 잘 안 뽑히면 낙하를 생략하고 "폰 화면에서 노드가
  흘러넘쳐 실험실로 번진다"로 단순화해도 서사는 성립한다. D2의 탑다운→정면 이동이
  한 클립에 안 되면 담기는 탑다운에서 끊고, 정면 샷은 이미지 생성 후 미세 모션으로.

## 컷 6 — 줌아웃 → 화이트 → 로고 (27.5~30초)

- 클립 D2 정면 샷 끝에 배율 키프레임(100%→60%)으로 플라스크가 멀어지게 하고,
  동시에 흰 오버레이 0%→100% 페이드인.
- 흰 화면 위 **LAB GENE 로고**(플라스크 엠블럼+워드마크) 페이드인, 아래 작게
  "연구실의 경험을 자산으로". 1.5초 홀드 후 끝.
- 방금 멀어진 플라스크와 로고의 플라스크 실루엣이 같은 중앙 위치에 겹치게 배치.

---

## 녹화분(컷 3~4) 모션그래픽 레시피 — CapCut

1. **프레임 연출 (필수)** — 그라데이션 배경 + 녹화 클립 95% 크기·라운드·그림자.
   단, 컷 4 끝(그래프)에서는 100%로 되돌려 컷 5 합성과 이음새를 맞춘다.
2. **줌 키프레임** — 행동 지점으로 130~150% 줌. 컷당 2회 이내.
3. **스포트라이트** — 구조 패널 완성 순간, 마스크로 주변 -40% 어둡게.
4. **클릭 리플** — 칩·저장 클릭에 0.3초 원형 팝.
5. **라벨 슬라이드인** — 빨간 텍스트+지시선, 컷 3 "자연어 입력"·컷 4 "재질문" 2개만.
6. **속도 램프** — 타이핑·로딩 2~3배속, 핵심 순간 정속.

지름길: 클릭 자동 줌 녹화 툴(크롬 확장 Cursorful 류)로 찍으면 2번이 공짜.

## 편집 체크리스트

- [ ] 총 29초 내외 (발화가 밀리면 영상이 먼저 끝나는 게 낫다)
- [ ] 컷 1 마지막 프레임 = D1 시작 이미지 / 컷 4 그래프 프레임 = 박자 1 합성 소스 /
      D1 마지막 프레임 = D2 시작 이미지
- [ ] **효과음** (캡컷 내장, 볼륨 40~60%):
  - 컷 2 화이트 플래시 → 우시(whoosh)
  - 컷 4 칩 클릭 → UI 탭음, 저장 → 확정음
  - 컷 4 그래프 진입 → 연쇄 팝(pop)
  - 컷 5 폰 낙하·노드 변환 → 팝 + 낮은 라이저(riser)
  - 컷 5 플라스크 담김 → 청량한 "퐁"
  - 컷 6 로고 → 잔잔한 스파클음
- [ ] BGM·나레이션 없음, AI 클립의 자체 오디오 삭제
- [ ] 현장 리허설에서 소리 확인 — 과하면 파워포인트에서 영상 음소거
- [ ] 1080p 30fps 내보내기
