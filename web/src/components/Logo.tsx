// LAB GENE 로고 마크 — 원 안의 DNA 이중나선 + 네트워크 노드 (사용자 시안의 SVG 재구현).
// 래스터 대신 SVG: 다크 레일에서도 투명 배경, 파비콘·소형 크기에서도 선명.
export default function Logo({ className = "", onDark = false }: {
  className?: string; onDark?: boolean;
}) {
  const ink = onDark ? "#dbe3ff" : "#1c2c74";  // 어두운 배경에선 남색 대신 밝은 잉크
  return (
    <svg viewBox="0 0 100 100" className={className} role="img" aria-label="LAB GENE 로고">
      <circle cx="50" cy="50" r="45" fill="none" stroke={ink} strokeWidth="5" />
      {/* 네트워크 간선 — 노드·나선보다 아래 */}
      <g stroke="#58a0f4" strokeWidth="2">
        <line x1="17" y1="48" x2="28" y2="30" />
        <line x1="17" y1="48" x2="34" y2="74" />
        <line x1="84" y1="42" x2="76" y2="66" />
        <line x1="28" y1="30" x2="44" y2="24" />
        <line x1="76" y1="66" x2="60" y2="76" />
      </g>
      <circle cx="28" cy="30" r="4" fill={ink} />
      <circle cx="17" cy="48" r="5.5" fill="#3f9af5" />
      <circle cx="84" cy="42" r="6.5" fill="#5636e8" />
      <circle cx="76" cy="66" r="5" fill="#2e7bf0" />
      <circle cx="34" cy="74" r="4" fill={ink} />
      {/* 염기쌍 가로대 — 나선 아래 깔린다 */}
      <g strokeWidth="4.5" strokeLinecap="round">
        <line x1="42" y1="24" x2="58" y2="24" stroke="#2e7bf0" />
        <line x1="46" y1="40" x2="54" y2="40" stroke="#5636e8" />
        <line x1="46" y1="46" x2="54" y2="46" stroke="#5636e8" />
        <line x1="42" y1="58" x2="58" y2="58" stroke="#3f9af5" />
        <line x1="40" y1="70" x2="60" y2="70" stroke="#2e7bf0" />
      </g>
      {/* 이중나선 */}
      <g fill="none" stroke={ink} strokeWidth="6" strokeLinecap="round">
        <path d="M38 18 C58 30 58 50 38 62 C27 69 27 76 37 83" />
        <path d="M62 18 C42 30 42 50 62 62 C73 69 73 76 63 83" />
      </g>
    </svg>
  );
}
