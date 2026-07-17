interface CasePageProps {
  params: {
    id: string;
  };
}

export default function CasePage({ params }: CasePageProps) {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="text-3xl font-semibold">Case {params.id}</h1>
    </main>
  );
}

