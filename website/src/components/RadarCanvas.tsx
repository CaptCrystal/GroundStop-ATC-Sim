import { useEffect, useRef } from "react";

const BLIPS = [
  { callsign: "ENY3639", type: "CRJ9", state: "TAXI",   angle: 0.52, r: 0.28 },
  { callsign: "EDV5456", type: "CRJ7", state: "LND",    angle: 2.15, r: 0.41 },
  { callsign: "SKW0610", type: "CRJ7", state: "PUSHBK", angle: 3.84, r: 0.19 },
  { callsign: "EDV85",   type: "CRJ9", state: "APCH",   angle: 4.71, r: 0.52 },
  { callsign: "AAL1492", type: "B738", state: "RAMP",   angle: 1.18, r: 0.23 },
  { callsign: "UAL890",  type: "A320", state: "TAXI",   angle: 5.50, r: 0.34 },
  { callsign: "DAL342",  type: "B737", state: "GATE",   angle: 0.95, r: 0.15 },
  { callsign: "SWA2210", type: "B738", state: "RWY",    angle: 3.20, r: 0.38 },
];

export default function RadarCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const blips = BLIPS.map(b => ({
      ...b,
      brightness: 0,
      driftAngle: Math.random() * 0.001,
      driftR: Math.random() * 0.0002,
    }));
    let sweepAngle = 0;
    let animFrame: number;

    function resize() {
      canvas!.width  = canvas!.offsetWidth;
      canvas!.height = canvas!.offsetHeight;
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    function draw(ts: number) {
      const W = canvas!.width, H = canvas!.height;
      const cx = W / 2, cy = H / 2;
      const maxR = Math.min(cx, cy) * 0.88;

      ctx!.fillStyle = "#010801";
      ctx!.fillRect(0, 0, W, H);

      ctx!.strokeStyle = "rgba(0,255,65,0.07)";
      ctx!.lineWidth = 1;
      for (let i = 1; i <= 5; i++) {
        ctx!.beginPath();
        ctx!.arc(cx, cy, (maxR / 5) * i, 0, Math.PI * 2);
        ctx!.stroke();
      }

      ctx!.strokeStyle = "rgba(0,255,65,0.05)";
      for (let i = 0; i < 16; i++) {
        const a = (i / 16) * Math.PI * 2;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.lineTo(cx + Math.cos(a) * maxR, cy + Math.sin(a) * maxR);
        ctx!.stroke();
      }

      ctx!.strokeStyle = "rgba(0,255,65,0.22)";
      ctx!.lineWidth = 1.5;
      ctx!.beginPath();
      ctx!.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx!.stroke();

      const TRAIL = Math.PI * 0.45;
      for (let i = 0; i < 80; i++) {
        const t = i / 80;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.arc(cx, cy, maxR, sweepAngle - TRAIL * (t + 1 / 80), sweepAngle - TRAIL * t);
        ctx!.closePath();
        ctx!.fillStyle = `rgba(0,255,65,${(1 - t) * 0.18})`;
        ctx!.fill();
      }

      ctx!.save();
      ctx!.shadowBlur = 12;
      ctx!.shadowColor = "rgba(0,255,65,0.7)";
      ctx!.strokeStyle = "rgba(0,255,65,0.95)";
      ctx!.lineWidth = 2;
      ctx!.beginPath();
      ctx!.moveTo(cx, cy);
      ctx!.lineTo(cx + Math.cos(sweepAngle) * maxR, cy + Math.sin(sweepAngle) * maxR);
      ctx!.stroke();
      ctx!.restore();

      blips.forEach(b => {
        b.angle += b.driftAngle;
        b.r = Math.max(0.08, Math.min(0.58, b.r + b.driftR * Math.sin(ts * 0.0003)));
        const bx = cx + Math.cos(b.angle) * (b.r * maxR);
        const by = cy + Math.sin(b.angle) * (b.r * maxR);
        const diff = ((sweepAngle - b.angle) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
        if (diff < 0.08) b.brightness = 1.0;
        else b.brightness *= 0.992;
        if (b.brightness < 0.03) return;

        ctx!.save();
        ctx!.shadowBlur = 14;
        ctx!.shadowColor = `rgba(0,255,65,${b.brightness * 0.8})`;
        ctx!.fillStyle = `rgba(0,255,65,${b.brightness})`;
        ctx!.beginPath();
        ctx!.arc(bx, by, 4, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();

        const a = b.brightness * 0.9;
        ctx!.fillStyle = `rgba(0,255,65,${a})`;
        ctx!.font = '10px "Courier New", monospace';
        ctx!.fillText(b.callsign, bx + 9, by - 5);
        ctx!.fillStyle = `rgba(0,255,65,${a * 0.55})`;
        ctx!.font = '9px "Courier New", monospace';
        ctx!.fillText(`${b.type} · ${b.state}`, bx + 9, by + 6);
      });

      ctx!.strokeStyle = "rgba(0,255,65,0.25)";
      ctx!.lineWidth = 1;
      ctx!.beginPath();
      ctx!.moveTo(cx - 12, cy); ctx!.lineTo(cx + 12, cy);
      ctx!.moveTo(cx, cy - 12); ctx!.lineTo(cx, cy + 12);
      ctx!.stroke();
      ctx!.beginPath();
      ctx!.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx!.strokeStyle = "rgba(0,255,65,0.4)";
      ctx!.stroke();

      ctx!.fillStyle = "rgba(0,255,65,0.25)";
      ctx!.font = '10px "Courier New", monospace';
      ctx!.textAlign = "center";
      const labelR = maxR + 16;
      ([["N", 270], ["E", 0], ["S", 90], ["W", 180]] as [string, number][]).forEach(([lbl, deg]) => {
        const rad = (deg - 90) * Math.PI / 180;
        ctx!.fillText(lbl, cx + Math.cos(rad) * labelR, cy + Math.sin(rad) * labelR + 4);
      });
      ctx!.textAlign = "left";

      sweepAngle = (sweepAngle + 0.022) % (Math.PI * 2);
      animFrame = requestAnimationFrame(draw);
    }

    animFrame = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(animFrame); ro.disconnect(); };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      aria-hidden="true"
    />
  );
}
