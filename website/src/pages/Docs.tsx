import { Link } from "react-router-dom";
import content from "@/content.json";

const { site, docs } = content;

// Block types
type Block =
  | { type: "p";     text: string }
  | { type: "pre";   text: string }
  | { type: "note";  text: string }
  | { type: "warn";  text: string }
  | { type: "list";  items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] };

function renderBlock(block: Block, i: number) {
  switch (block.type) {
    case "p":
      return <p key={i} className="text-sm text-white/40 leading-relaxed mb-3">{block.text}</p>;
    case "pre":
      return (
        <pre key={i} className="bg-white/[0.03] border border-white/8 rounded-lg px-5 py-4 text-xs font-mono text-white/50 overflow-x-auto my-4 leading-7">
          {block.text}
        </pre>
      );
    case "note":
      return (
        <div key={i} className="border-l-2 border-white/10 pl-4 my-4 text-xs text-white/30 leading-relaxed">
          {block.text}
        </div>
      );
    case "warn":
      return (
        <div key={i} className="border-l-2 border-white/20 pl-4 my-4 text-xs text-white/35 leading-relaxed">
          {block.text}
        </div>
      );
    case "list":
      return (
        <ul key={i} className="my-4 space-y-1.5">
          {block.items.map((item, j) => (
            <li key={j} className="text-sm text-white/35 flex gap-2">
              <span className="text-white/20 flex-shrink-0">–</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      );
    case "table":
      return (
        <div key={i} className="overflow-x-auto my-4 border border-white/8 rounded-lg">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8">
                {block.headers.map(h => (
                  <th key={h} className="text-left px-4 py-2.5 text-white/25 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, j) => (
                <tr key={j} className="border-b border-white/5 last:border-0">
                  {row.map((cell, k) => (
                    <td key={k} className={`px-4 py-2.5 ${k === 0 ? "font-mono text-white/60" : "text-white/35"}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
  }
}

// Top-level sections (no parent) for the sidebar
const topSections = docs.sections.filter(s => !("parent" in s));

export default function Docs() {
  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-black/95 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 flex items-center justify-between h-13" style={{ height: "52px" }}>
          <div className="flex items-center gap-3">
            <Link to="/" className="text-sm font-semibold text-white">{site.name}</Link>
            <span className="text-white/10">/</span>
            <span className="text-xs text-white/30">Docs</span>
          </div>
          <a href="/#purchase" className="text-xs font-medium text-black bg-white hover:bg-white/90 px-4 py-1.5 rounded-full transition-colors hidden sm:block">
            Get it — ${site.price}
          </a>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 flex gap-12">
        {/* Sidebar */}
        <aside className="hidden lg:block w-40 flex-shrink-0 pt-10">
          <nav className="sticky top-16 space-y-0.5">
            {topSections.map(s => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="block py-1 text-xs text-white/25 hover:text-white/55 transition-colors"
              >
                {s.title}
              </a>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <article className="flex-1 min-w-0 pt-10 pb-24 lg:border-l lg:border-white/5 lg:pl-12 max-w-2xl">
          <div className="mb-10 pb-8 border-b border-white/5">
            <h1 className="text-2xl font-black text-white mb-1">Docs</h1>
            <p className="text-sm text-white/30">Command reference for {site.name}.</p>
          </div>

          {docs.sections.map(section => {
            const isSubsection = "parent" in section;
            return (
              <section key={section.id} id={section.id} className="mb-10">
                {isSubsection
                  ? <h3 className="text-sm font-semibold text-white mt-8 mb-3 scroll-mt-20">{section.title}</h3>
                  : <h2 className="text-base font-bold text-white mt-12 mb-4 scroll-mt-20 first:mt-0">{section.title}</h2>
                }
                {(section.blocks as Block[]).map((block, i) => renderBlock(block, i))}
              </section>
            );
          })}

          {/* CTA */}
          <div className="mt-16 border border-white/8 rounded-xl p-8 text-center">
            <p className="text-sm font-semibold text-white mb-1">Ready to control?</p>
            <p className="text-xs text-white/30 mb-5">{site.name} is ${site.price}, one-time.</p>
            <a href="/#purchase" className="inline-block text-sm font-medium text-black bg-white hover:bg-white/90 px-6 py-2.5 rounded-full transition-colors">
              Get {site.name}
            </a>
          </div>
        </article>
      </div>
    </div>
  );
}
