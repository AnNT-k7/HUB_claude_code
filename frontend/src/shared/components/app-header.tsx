import Link from "next/link";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/60 bg-background/90 backdrop-blur-xl">
      <div className="page-container flex h-16 items-center justify-between gap-4">
        <Link
          href="/"
          className="flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/20"
        >
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-sm font-black text-white shadow-lg shadow-primary/20">
            DE
          </span>
          <span className="leading-tight">
            <span className="block text-sm font-extrabold tracking-tight text-foreground sm:text-base">
              Digital Expert Agents
            </span>
            <span className="hidden text-[11px] font-medium text-muted-foreground sm:block">
              Human-verified banking intelligence
            </span>
          </span>
        </Link>
        <nav aria-label="Điều hướng chính" className="flex items-center gap-1">
          <Link
            href="/cases"
            className="rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground transition hover:bg-white hover:text-foreground focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/20"
          >
            Hồ sơ tín dụng
          </Link>
        </nav>
      </div>
    </header>
  );
}
