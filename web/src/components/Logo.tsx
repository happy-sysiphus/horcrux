// LAB GENE 로고 마크 — DNA 이중나선의 염기쌍이 문서(실험 기록)인 디자인.
// 사용자 시안(lab-gene-document-stack)의 SVG 재구현: 원본은 흰 배경 1254px 비트맵이라
// 다크 배경·소형 크기·번들 용량(1.2MB) 문제로 벡터로 다시 그렸다.
const DOC_STROKES = ["#2e7bf0", "#5636e8", "#4633e0", "#2e7bf0", "#5636e8"];

function Doc({ x, y, stroke }: { x: number; y: number; stroke: string }) {
  return (
    <g stroke={stroke} strokeWidth="1.8" fill="#ffffff">
      {/* 접힌 귀퉁이가 있는 문서 */}
      <path d={`M${x} ${y} h9.5 l3.5 3.5 v7.5 h-13 z`} strokeLinejoin="round" />
      <path d={`M${x + 9.5} ${y} v3.5 h3.5`} fill="none" />
      <line x1={x + 2.5} y1={y + 5} x2={x + 8} y2={y + 5} />
      <line x1={x + 2.5} y1={y + 8} x2={x + 10} y2={y + 8} />
    </g>
  );
}

export default function Logo({ className = "", onDark = false }: {
  className?: string; onDark?: boolean;
}) {
  const ink = onDark ? "#dbe3ff" : "#141f5c";  // 어두운 배경에선 남색 대신 밝은 잉크
  return (
    <svg viewBox="0 0 100 100" className={className} role="img" aria-label="LAB GENE 로고">
      <circle cx="50" cy="50" r="44" fill="none" stroke={ink} strokeWidth="6.5" />
      {/* 네트워크 간선 */}
      <g strokeWidth="2.2" fill="none">
        <line x1="33" y1="32" x2="46" y2="29" stroke={ink} />
        <line x1="33" y1="32" x2="24" y2="49" stroke="#2e7bf0" />
        <line x1="24" y1="49" x2="41" y2="72" stroke="#2e9bf5" />
        <line x1="76" y1="41" x2="61" y2="46" stroke="#2e7bf0" />
        <line x1="76" y1="41" x2="68" y2="64" stroke="#2e7bf0" />
        <line x1="68" y1="64" x2="57" y2="71" stroke="#2e9bf5" />
      </g>
      {/* 네트워크 노드 */}
      <circle cx="33" cy="32" r="4.5" fill={ink} />
      <circle cx="24" cy="49" r="6" fill="#2e9bf5" />
      <circle cx="41" cy="72" r="4.5" fill={ink} />
      <circle cx="76" cy="41" r="6.5" fill="#4b2ee8" />
      <circle cx="68" cy="64" r="5" fill="#2e7bf0" />
      {/* 문서 스택 — 나선 사이의 염기쌍 */}
      <Doc x={41} y={24} stroke={DOC_STROKES[0]} />
      <Doc x={45} y={35} stroke={DOC_STROKES[1]} />
      <Doc x={40} y={46} stroke={DOC_STROKES[2]} />
      <Doc x={44} y={56} stroke={DOC_STROKES[3]} />
      <Doc x={40} y={66} stroke={DOC_STROKES[4]} />
      {/* 이중나선 — 맨 위에 올려 문서가 사이에 낀 것처럼 보이게 */}
      <g fill="none" stroke={ink} strokeWidth="7.5" strokeLinecap="round">
        <path d="M39 17 C57 24 60 37 48 48 C36 59 38 70 54 79" />
        <path d="M63 19 C48 25 42 36 52 47 C63 58 59 72 44 80" />
      </g>
    </svg>
  );
}
