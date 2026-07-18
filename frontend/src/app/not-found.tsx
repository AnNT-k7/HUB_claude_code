import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page-container grid min-h-[65vh] place-items-center py-12 text-center">
      <div>
        <p className="text-sm font-black uppercase tracking-[0.2em] text-primary">404</p>
        <h1 className="mt-3 text-4xl font-black tracking-tight">Không tìm thấy nội dung</h1>
        <p className="mt-3 text-muted-foreground">
          Trang hoặc hồ sơ bạn đang tìm không tồn tại.
        </p>
        <Link
          href="/cases"
          className="mt-6 inline-flex h-11 items-center rounded-xl bg-primary px-4 text-sm font-bold text-white hover:bg-primary/90"
        >
          Về danh sách hồ sơ
        </Link>
      </div>
    </main>
  );
}
