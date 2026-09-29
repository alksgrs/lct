import { Leaf } from "lucide-react";
import type { ReactNode } from "react";

export default function Layout({
  children
}: {
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div
          className="brand"
          aria-label="Зелёный План"
        >
          <div className="brand-mark">
            <Leaf size={21} />
          </div>

          <div>
            <div className="brand-name">
              Зелёный План
            </div>

            <div className="brand-subtitle">
              автоматическое проектирование озеленения
            </div>
          </div>
        </div>

      </header>

      <main className="page">
        {children}
      </main>
    </div>
  );
}
