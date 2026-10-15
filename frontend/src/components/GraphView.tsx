"use client";
import { Box, Stack, Typography } from "@mui/material";
import { useMemo } from "react";
import { GraphData } from "@/lib/api";

const COLORS: Record<string, string> = {
  Finding: "#dc2626", Supplier: "#1d4ed8", BankAccount: "#7c3aed", Owner: "#a21caf", Invoice: "#0f766e",
  PurchaseOrder: "#ca8a04", Shipment: "#ea580c", Product: "#475569", Warehouse: "#0891b2",
};

/** Small deterministic force layout (no extra dependency): fine for the tens of nodes in one investigation. */
function layout(data: GraphData, w: number, h: number) {
  const n = data.nodes.length;
  const pos = data.nodes.map((_, i) => ({
    x: w / 2 + (w / 3) * Math.cos((2 * Math.PI * i) / Math.max(n, 1)),
    y: h / 2 + (h / 3) * Math.sin((2 * Math.PI * i) / Math.max(n, 1)),
  }));
  const idx = new Map(data.nodes.map((d, i) => [d.id, i]));
  const edges = data.edges.map((e) => [idx.get(e.source), idx.get(e.target)]).filter(([a, b]) => a !== undefined && b !== undefined) as [number, number][];
  for (let it = 0; it < 300; it++) {
    const disp = pos.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y;
      const d2 = Math.max(dx * dx + dy * dy, 25), f = 4000 / d2;
      disp[i].x += dx * f / Math.sqrt(d2); disp[i].y += dy * f / Math.sqrt(d2);
      disp[j].x -= dx * f / Math.sqrt(d2); disp[j].y -= dy * f / Math.sqrt(d2);
    }
    for (const [a, b] of edges) {
      const dx = pos[a].x - pos[b].x, dy = pos[a].y - pos[b].y, d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const f = (d - 90) * 0.05;
      disp[a].x -= dx / d * f; disp[a].y -= dy / d * f; disp[b].x += dx / d * f; disp[b].y += dy / d * f;
    }
    const t = 10 * (1 - it / 300) + 0.5;
    pos.forEach((p, i) => {
      const d = Math.max(Math.hypot(disp[i].x, disp[i].y), 0.01);
      p.x = Math.min(w - 40, Math.max(40, p.x + disp[i].x / d * Math.min(d, t) + (w / 2 - p.x) * 0.01));
      p.y = Math.min(h - 25, Math.max(25, p.y + disp[i].y / d * Math.min(d, t) + (h / 2 - p.y) * 0.01));
    });
  }
  return { pos, edges, idx };
}

export default function GraphView({ data }: { data: GraphData }) {
  const W = 900, H = 520;
  const { pos, idx } = useMemo(() => layout(data, W, H), [data]);
  const labels = Array.from(new Set(data.nodes.map((n) => n.label)));
  if (!data.nodes.length) return <Typography color="text.secondary">No findings to visualise.</Typography>;
  return (
    <Box>
      <Box component="svg" viewBox={`0 0 ${W} ${H}`} sx={{ width: "100%", height: "auto", bgcolor: "#fbfcfe", borderRadius: 1, border: 1, borderColor: "divider" }}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>
        {data.edges.map((e, i) => {
          const a = pos[idx.get(e.source)!], b = pos[idx.get(e.target)!];
          if (!a || !b) return null;
          const involves = e.type === "INVOLVES";
          return (
            <g key={i}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={involves ? "#fca5a5" : "#94a3b8"} strokeDasharray={involves ? "4 3" : undefined} markerEnd="url(#arrow)" />
              {!involves && <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 3} fontSize="8" fill="#64748b" textAnchor="middle">{e.type}</text>}
            </g>
          );
        })}
        {data.nodes.map((n, i) => (
          <g key={n.id}>
            <circle cx={pos[i].x} cy={pos[i].y} r={n.label === "Finding" ? 9 : 12} fill={COLORS[n.label] || "#64748b"} opacity={0.9}>
              <title>{`${n.label} ${n.id}${n.name ? " · " + n.name : ""}`}</title>
            </circle>
            <text x={pos[i].x} y={pos[i].y + 24} fontSize="10" textAnchor="middle" fill="#0f172a">{n.label === "Finding" ? n.name : n.id}</text>
          </g>
        ))}
      </Box>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
        {labels.map((l) => (
          <Stack key={l} direction="row" spacing={0.5} alignItems="center">
            <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: COLORS[l] || "#64748b" }} />
            <Typography variant="caption">{l}</Typography>
          </Stack>
        ))}
        <Typography variant="caption" color="text.secondary">Dashed red = Finding INVOLVES; grey = real graph relationships between involved records</Typography>
      </Stack>
    </Box>
  );
}
