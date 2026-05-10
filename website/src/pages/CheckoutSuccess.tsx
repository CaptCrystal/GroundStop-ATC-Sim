import { Link } from "react-router-dom";

const DOWNLOAD_URL = "https://YOUR_DOWNLOAD_LINK_HERE";

export default function CheckoutSuccess() {
  return (
    <main className="min-h-screen bg-[#0b0c10] flex items-center justify-center px-6 py-16">
      <div className="max-w-md w-full bg-[#111318] border border-[#1e2030] rounded-2xl p-10 text-center shadow-2xl">

        <div className="w-16 h-16 rounded-full bg-[#4f8ef7]/10 border border-[#4f8ef7]/25 flex items-center justify-center mx-auto mb-6">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4f8ef7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>

        <div className="flex items-center justify-center gap-2 mb-5">
          <svg width="18" height="18" viewBox="0 0 22 22" fill="none" aria-hidden="true">
            <rect x="9.5" y="2" width="3" height="18" rx="1.5" fill="#4f8ef7" opacity="0.9"/>
            <rect x="4"   y="6" width="3" height="2" rx="1" fill="#4f8ef7" opacity="0.45"/>
            <rect x="15"  y="6" width="3" height="2" rx="1" fill="#4f8ef7" opacity="0.45"/>
            <rect x="4"   y="10" width="3" height="2" rx="1" fill="#4f8ef7" opacity="0.45"/>
            <rect x="15"  y="10" width="3" height="2" rx="1" fill="#4f8ef7" opacity="0.45"/>
          </svg>
          <span className="text-sm font-semibold text-white tracking-tight">GroundStop</span>
        </div>

        <h1 className="text-2xl font-bold text-white mb-2">You're cleared to taxi!</h1>
        <p className="text-[#6b7280] text-sm leading-relaxed mb-8">
          Your purchase is confirmed. Click below to download GroundStop and start controlling ground traffic.
        </p>

        <a
          href={DOWNLOAD_URL}
          download
          className="w-full inline-flex items-center justify-center gap-2 font-medium text-black bg-white hover:bg-[#e5e5e5] py-3 rounded-full text-sm transition-colors mb-3"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download GroundStop
        </a>

        <p className="text-xs text-[#333] mb-8">Windows · macOS · ~XX MB</p>

        <div className="text-left space-y-3 mb-8">
          {[
            "Run the downloaded installer",
            "Select KSGF and start your first session",
            "Press / to open the command bar",
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-[#4f8ef7]/10 border border-[#4f8ef7]/20 text-[#4f8ef7] text-xs font-bold flex items-center justify-center">
                {i + 1}
              </span>
              <span className="text-sm text-white/70">{step}</span>
            </div>
          ))}
        </div>

        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-[#6b7280] hover:text-white transition-colors"
        >
          ← Back to GroundStop
        </Link>
      </div>
    </main>
  );
}
