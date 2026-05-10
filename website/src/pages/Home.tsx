import { Link } from "react-router-dom";
import content from "@/content.json";
import Navbar from "@/components/Navbar";
import RadarCanvas from "@/components/RadarCanvas";
import BuyButton from "@/components/BuyButton";
import ScrollReveal from "@/components/ScrollReveal";

const { site, hero, features, pricing, roadmap } = content;

export default function Home() {
  return (
    <>
      <Navbar />

      {/* Hero */}
      <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 overflow-hidden">
        <RadarCanvas />
        <div className="hero-vignette" aria-hidden="true" />
        <div className="relative z-10 max-w-xl">
          <h1 className="text-7xl sm:text-8xl font-black text-white tracking-tight leading-none mb-4">
            {site.name}
          </h1>
          <p className="text-white/35 text-sm font-mono tracking-widest uppercase mb-6">
            {site.tagline}
          </p>
          <p className="text-white/45 mb-10 leading-relaxed">
            {hero.description}
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-14">
            <a href="#purchase" className="font-semibold text-black bg-white hover:bg-white/90 px-7 py-3 rounded-full text-sm transition-colors">
              Get {site.name} — ${site.price}
            </a>
            <Link to="/docs" className="font-medium text-white/40 hover:text-white/70 border border-white/10 hover:border-white/25 px-7 py-3 rounded-full text-sm transition-colors">
              Documentation
            </Link>
          </div>
          <div className="flex justify-center gap-10">
            {hero.stats.map(s => (
              <div key={s.label}>
                <div className="text-2xl font-black text-white font-mono">{s.value}</div>
                <div className="text-xs text-white/25 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <main className="max-w-4xl mx-auto px-6">

        {/* Features */}
        <section className="py-24 border-t border-white/5" id="features">
          <h2 className="text-xs font-mono tracking-widest text-white/25 uppercase mb-10">Features</h2>
          <div className="grid sm:grid-cols-2 gap-x-12 gap-y-8">
            {features.map((f, i) => (
              <ScrollReveal key={f.title} delay={i * 50}>
                <div>
                  <h3 className="text-sm font-semibold text-white mb-1">{f.title}</h3>
                  <p className="text-sm text-white/35 leading-relaxed">{f.desc}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </section>

        {/* Pricing */}
        <section className="py-24 border-t border-white/5" id="purchase">
          <h2 className="text-xs font-mono tracking-widest text-white/25 uppercase mb-10">Pricing</h2>
          <div className="max-w-xs">
            <div className="text-xs text-white/20 font-mono uppercase mb-4">{pricing.label}</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-xl text-white/25 font-bold">$</span>
              <span className="text-5xl font-black text-white font-mono leading-none">{site.price}</span>
            </div>
            <p className="text-xs text-white/20 mb-7">one-time purchase</p>
            <ul className="space-y-2.5 mb-7">
              {pricing.includes.map(item => (
                <li key={item} className="flex items-center gap-3 text-sm text-white/35">
                  <span className="text-white/60 text-xs">✓</span> {item}
                </li>
              ))}
            </ul>
            <BuyButton />
          </div>
        </section>

        {/* Docs */}
        <section className="py-24 border-t border-white/5" id="docs">
          <div className="flex items-baseline justify-between mb-10">
            <h2 className="text-xs font-mono tracking-widest text-white/25 uppercase">Documentation</h2>
            <Link to="/docs" className="text-xs text-white/25 hover:text-white/50 transition-colors">View all →</Link>
          </div>
          <div className="grid sm:grid-cols-2 gap-px bg-white/5">
            {[
              { href: "/docs#getting-started", label: "Getting Started",    desc: "Your first pushback to your first departure." },
              { href: "/docs#commands",        label: "All Commands",       desc: "Complete command reference with examples." },
              { href: "/docs#states",          label: "Aircraft States",    desc: "PARKED → PUSHBACK → HOLDING → TAXI → TAKEOFF." },
              { href: "/docs#shortcuts",       label: "Keyboard Shortcuts", desc: "Every key binding in the simulator." },
            ].map(d => (
              <Link key={d.href} to={d.href} className="group block bg-black px-6 py-5 hover:bg-white/[0.02] transition-colors">
                <div className="text-sm font-medium text-white mb-1 group-hover:text-white/80">{d.label}</div>
                <div className="text-sm text-white/30">{d.desc}</div>
              </Link>
            ))}
          </div>
        </section>

        {/* Roadmap */}
        <section className="py-24 border-t border-white/5" id="roadmap">
          <h2 className="text-xs font-mono tracking-widest text-white/25 uppercase mb-10">Roadmap</h2>
          <div>
            {roadmap.map((item, i) => (
              <ScrollReveal key={item.label} delay={i * 40}>
                <div className="flex items-start gap-4 py-4 border-b border-white/5">
                  <span className={`mt-0.5 text-xs font-mono flex-shrink-0 w-4 text-center ${item.done ? "text-white/50" : item.progress ? "text-white/25" : "text-white/10"}`}>
                    {item.done ? "✓" : item.progress ? "◐" : "○"}
                  </span>
                  <div>
                    <span className={`text-sm font-medium ${item.done ? "text-white" : "text-white/25"}`}>{item.label}</span>
                    <span className="text-xs text-white/15 ml-3">{item.desc}</span>
                  </div>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 px-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <span className="text-sm font-semibold text-white">{site.name}</span>
          <nav className="flex gap-6">
            {[["#features","Features"],["#purchase","Purchase"],["#roadmap","Roadmap"],["/docs","Docs"]].map(([href,label]) => (
              <a key={label} href={href} className="text-xs text-white/20 hover:text-white/45 transition-colors">{label}</a>
            ))}
          </nav>
          <p className="text-xs text-white/10">© {new Date().getFullYear()} {site.name}</p>
        </div>
      </footer>
    </>
  );
}
