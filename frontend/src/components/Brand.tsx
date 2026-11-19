import { Link2 } from "lucide-react";

export default function Brand() {
  return (
    <a className="brand" href="/dashboard" aria-label="Cutlink home">
      <span className="brand-icon">
        <Link2 size={23} strokeWidth={2.5} />
      </span>
      cutlink<span className="brand-dot">.</span>
    </a>
  );
}
