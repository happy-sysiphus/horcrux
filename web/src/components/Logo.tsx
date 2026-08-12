import logo from "../assets/logo.png";

// LAB GENE 로고 — 사용자 시안 원본(문서 스택 나선)을 원 테두리에 맞춰 잘라 256px로 축소.
// rounded-full로 원형 클리핑해 흰 배경이 다크 레일에서도 배지처럼 보이게 한다.
export default function Logo({ className = "" }: { className?: string }) {
  return <img src={logo} alt="LAB GENE 로고" className={`rounded-full ${className}`} />;
}
