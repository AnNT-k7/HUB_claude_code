import Link from "next/link";

const PIPELINE_STEPS = [
  {
    number: "01",
    title: "Orchestrator lập kế hoạch",
    description: "Hiểu yêu cầu, phân rã nhiệm vụ và chọn đúng chuyên gia cho từng phần hồ sơ.",
  },
  {
    number: "02",
    title: "Chuyên gia cùng phản biện",
    description: "Các agent làm việc trên Shared Board; Reviewer phát hiện lỗi và yêu cầu tinh chỉnh.",
  },
  {
    number: "03",
    title: "Con người quyết định",
    description: "Chuyên viên kiểm tra số liệu, tranh luận và căn cứ chính sách trước khi phê duyệt.",
  },
] as const;

export default function HomePage() {
  return (
    <main>
      <section className="relative overflow-hidden border-b border-border bg-slate-950 text-white">
        <div className="pointer-events-none absolute -right-32 -top-40 h-[34rem] w-[34rem] rounded-full bg-blue-600/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-48 left-1/4 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="page-container relative grid gap-12 py-20 lg:grid-cols-[1.15fr_0.85fr] lg:items-center lg:py-28">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-400/20 bg-blue-400/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.16em] text-blue-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Human-in-the-loop by design
            </div>
            <h1 className="mt-7 max-w-3xl text-4xl font-black leading-[1.08] tracking-[-0.035em] sm:text-6xl">
              Thẩm định tín dụng với một hội đồng chuyên gia số.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
              Digital Expert Agents phối hợp Credit, Risk, Legal & Compliance và Collateral trên một Shared Board minh bạch — nhưng quyền quyết định luôn thuộc về chuyên viên ngân hàng.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/cases"
                className="inline-flex h-12 items-center justify-center rounded-xl bg-blue-600 px-5 text-sm font-bold text-white shadow-lg shadow-blue-950/50 transition hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-400/30"
              >
                Mở không gian thẩm định →
              </Link>
              <a
                href="#pipeline"
                className="inline-flex h-12 items-center justify-center rounded-xl border border-white/15 bg-white/5 px-5 text-sm font-bold text-white transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white/20"
              >
                Xem quy trình 3 tầng
              </a>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-lg">
            <div className="rounded-3xl border border-white/10 bg-white/[0.07] p-5 shadow-2xl backdrop-blur-sm sm:p-6">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-blue-300">Live assessment</p>
                  <p className="mt-1 font-bold">Shared Board · Corporate Loan</p>
                </div>
                <span className="rounded-full bg-violet-400/15 px-2.5 py-1 text-xs font-bold text-violet-200">
                  Debate round 2/3
                </span>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3">
                {[
                  ["Credit", "DSCR 1.28x", "Complete"],
                  ["Risk", "Medium tier", "Reviewing"],
                  ["Legal", "1 flag", "Refining"],
                  ["Collateral", "LTV 62%", "Complete"],
                ].map(([agent, result, status]) => (
                  <div key={agent} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" />
                      <span className="text-xs font-bold text-slate-300">{agent}</span>
                    </div>
                    <p className="mt-3 text-lg font-black">{result}</p>
                    <p className="mt-1 text-xs text-slate-400">{status}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 rounded-2xl border border-amber-300/10 bg-amber-300/[0.07] p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-amber-200">Reviewer challenge</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Credit Agent cần tính lại stressed DSCR với nghĩa vụ pháp lý tiềm tàng.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="pipeline" className="page-container py-16 sm:py-20">
        <div className="max-w-2xl">
          <p className="eyebrow">Three-tier pipeline</p>
          <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
            Tự động hóa phân tích, không tự động hóa quyết định.
          </h2>
          <p className="mt-4 leading-7 text-muted-foreground">
            Mọi nhận định chính sách đều cần trích dẫn RAG. Mọi vòng phản biện đều được lưu vết. Mọi tác vụ vận hành đều chờ xác nhận thủ công.
          </p>
        </div>
        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {PIPELINE_STEPS.map((step) => (
            <article key={step.number} className="rounded-2xl border border-border bg-white p-6 shadow-card">
              <span className="text-sm font-black text-primary">{step.number}</span>
              <h3 className="mt-5 text-lg font-bold">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
