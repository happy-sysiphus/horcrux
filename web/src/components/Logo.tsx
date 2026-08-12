import logo from "../assets/logo.png";

// LAB GENE 로고 — 사용자 시안(문서 스택 나선, 투명 배경)을 256px로 축소한 원본.
export default function Logo({ className = "" }: { className?: string }) {
  return <img src={logo} alt="LAB GENE 로고" className={className} />;
}
