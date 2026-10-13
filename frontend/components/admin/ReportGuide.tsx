import type { ReportGuideItem } from "@/lib/admin/reportGuides"

type ReportGuideProps = {
  title: string
  intro?: string
  items: ReportGuideItem[]
  footnote?: string
  testId?: string
}

export function ReportGuide({ title, intro, items, footnote, testId }: ReportGuideProps) {
  return (
    <div
      className="mt-6 border-t border-slate-800 pt-4"
      data-testid={testId}
    >
      <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
        {title}
      </h3>
      {intro ? <p className="text-sm text-slate-500 mb-3 leading-snug">{intro}</p> : null}
      <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
        {items.map((item) => (
          <div key={item.id}>
            <dt className="font-medium text-slate-200">{item.label}</dt>
            <dd className="text-slate-500 mt-0.5 leading-snug">{item.description}</dd>
          </div>
        ))}
      </dl>
      {footnote ? <p className="text-xs text-slate-600 mt-4 leading-snug">{footnote}</p> : null}
    </div>
  )
}
