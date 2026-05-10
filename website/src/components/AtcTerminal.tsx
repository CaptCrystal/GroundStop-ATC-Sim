import { useEffect, useRef, useState } from "react";

const buildExchanges = (atis: string) => [
  { role: "pilot", text: "Ground, ENY3639, Gate 1, request pushback" },
  { role: "atc",   text: `ENY3639, push and start approved, face east, Runway 20, ATIS ${atis}` },
  { role: "pilot", text: `Push and start, face east, Runway 20, ATIS ${atis}, ENY3639` },
  { role: "atc",   text: "ENY3639, taxi to Runway 20 via Uniform, Alpha, hold short" },
  { role: "pilot", text: "Runway 20 via Uniform Alpha, hold short, ENY3639" },
  { role: "pilot", text: "Ground, EDV5456, clear of Runway 02, turning off Alpha" },
  { role: "atc",   text: "EDV5456, taxi to Gate 4 via Alpha" },
  { role: "pilot", text: "Gate 4 via Alpha, EDV5456" },
  { role: "atc",   text: "ENY3639, contact tower 118.1, good day" },
  { role: "pilot", text: "Tower 118.1, ENY3639, good day" },
];

export default function AtcTerminal() {
  const bodyRef   = useRef<HTMLDivElement>(null);
  const typingRef = useRef<HTMLSpanElement>(null);
  const idxRef    = useRef(0);
  const timerRef  = useRef<ReturnType<typeof setTimeout>>();
  const [atis, setAtis] = useState("Bravo");

  useEffect(() => {
    fetch("https://datis.clowd.io/api/KSGF")
      .then(r => r.json())
      .then((data: Array<{ datis: string }>) => {
        const match = data[0]?.datis?.match(/ATIS INFO ([A-Z]+)/);
        if (match) {
          const word = match[1];
          setAtis(word.charAt(0) + word.slice(1).toLowerCase());
        }
      })
      .catch(() => {/* keep default */});
  }, []);

  useEffect(() => {
    const EXCHANGES = buildExchanges(atis);
    idxRef.current = 0;
    let charIdx = 0;
    let mounted = true;

    function addLine(role: string, text: string) {
      if (!bodyRef.current || !mounted) return;
      const div = document.createElement("div");
      div.className = "flex gap-3 text-[0.8rem] font-mono leading-6";
      const label = role === "pilot"
        ? '<span style="color:#444;flex-shrink:0;width:3rem">PILOT</span>'
        : '<span style="color:#888;flex-shrink:0;width:3rem">GND</span>';
      const textColor = role === "pilot" ? "color:#888" : "color:#e0e0e0";
      div.innerHTML = `${label}<span style="${textColor}">${text}</span>`;
      bodyRef.current.appendChild(div);
      const lines = bodyRef.current.querySelectorAll("div:not(.sys)");
      if (lines.length > 12) lines[0].remove();
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }

    function type() {
      if (!mounted || !typingRef.current) return;
      const ex = EXCHANGES[idxRef.current];
      if (charIdx <= ex.text.length) {
        typingRef.current.textContent = ex.text.slice(0, charIdx);
        charIdx++;
        timerRef.current = setTimeout(type, 40 + Math.random() * 20);
      } else {
        timerRef.current = setTimeout(() => {
          if (!mounted) return;
          addLine(ex.role, ex.text);
          if (typingRef.current) typingRef.current.textContent = "";
          charIdx = 0;
          idxRef.current = (idxRef.current + 1) % EXCHANGES.length;
          timerRef.current = setTimeout(type, 1000 + Math.random() * 800);
        }, 500);
      }
    }

    timerRef.current = setTimeout(type, 1200);
    return () => { mounted = false; clearTimeout(timerRef.current); };
  }, [atis]);

  return (
    <div className="max-w-xl border border-[#1f1f1f] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1f1f1f]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="text-[0.7rem] font-mono text-[#333] ml-2">KSGF Ground — 121.9</span>
      </div>

      <div ref={bodyRef} className="px-4 pt-4 pb-2 min-h-[160px] max-h-[200px] overflow-hidden flex flex-col gap-0.5 bg-[#080808]">
        <div className="sys text-[0.75rem] font-mono text-[#2a2a2a] mb-2">
          Ground Control active — ENY3639, SKW0610, EDV5456 on frequency
        </div>
      </div>

      <div className="flex items-center gap-3 px-4 py-2.5 border-t border-[#1f1f1f] bg-[#080808]">
        <span className="text-[#444] text-[0.8rem] font-mono flex-shrink-0">GND ›</span>
        <span ref={typingRef} className="text-[#e0e0e0] text-[0.8rem] font-mono" />
        <span className="term-cursor text-[#555] text-[0.8rem] font-mono">▋</span>
      </div>
    </div>
  );
}
