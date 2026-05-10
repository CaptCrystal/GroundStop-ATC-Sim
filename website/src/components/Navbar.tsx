import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <nav className={`fixed inset-x-0 top-0 z-50 transition-colors duration-200 ${scrolled ? "bg-black/90 backdrop-blur-sm border-b border-white/5" : ""}`}>
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link to="/" className="font-semibold text-white text-sm tracking-tight">GroundStop</Link>

        <div className="hidden md:flex items-center gap-7">
          <Link to="/docs" className="text-sm text-white/40 hover:text-white transition-colors">Docs</Link>
          <a href="/#purchase" className="text-sm font-medium text-black bg-white hover:bg-white/90 px-4 py-1.5 rounded-full transition-colors">
            Get it — $15
          </a>
        </div>

        <button onClick={() => setOpen(!open)} className="md:hidden p-2" aria-label="Menu">
          <div className={`w-5 h-px bg-white mb-1.5 transition-all ${open ? "rotate-45 translate-y-[7px]" : ""}`} />
          <div className={`w-5 h-px bg-white mb-1.5 transition-all ${open ? "opacity-0" : ""}`} />
          <div className={`w-5 h-px bg-white transition-all ${open ? "-rotate-45 -translate-y-[7px]" : ""}`} />
        </button>
      </div>

      {open && (
        <div className="md:hidden bg-black border-b border-white/5 px-6 py-4 flex flex-col gap-4">
          <Link to="/docs" onClick={() => setOpen(false)} className="text-sm text-white/40">Docs</Link>
          <a href="/#purchase" onClick={() => setOpen(false)} className="text-sm font-medium text-black bg-white px-4 py-2 rounded-full text-center">
            Get it — $15
          </a>
        </div>
      )}
    </nav>
  );
}
