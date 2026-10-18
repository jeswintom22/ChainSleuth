"use client";
import {
  Box, Chip, Divider, FormControlLabel, IconButton, Paper, Stack, Switch, Tooltip, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import CloseFullscreenIcon from "@mui/icons-material/CloseFullscreen";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import RemoveIcon from "@mui/icons-material/Remove";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import { PointerEvent, WheelEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GraphData } from "@/lib/api";

const COLORS: Record<string, string> = {
  Finding: "#dc2626", Supplier: "#2563eb", BankAccount: "#7c3aed", Owner: "#a21caf", Invoice: "#0f766e",
  PurchaseOrder: "#d97706", Shipment: "#ea580c", Product: "#475569", Warehouse: "#0891b2",
};
const COLUMN: Record<string, number> = {
  Owner: 90, BankAccount: 90, Supplier: 285, Invoice: 490, Product: 680, PurchaseOrder: 710, Shipment: 920, Warehouse: 1080,
};
const W = 1180;
const H = 620;
const NODE_W = 132;
const NODE_H = 50;

type Node = GraphData["nodes"][number];
type Edge = GraphData["edges"][number];
type Point = { x: number; y: number };
type Transform = { x: number; y: number; scale: number };

function adjacency(nodes: Node[], edges: Edge[]) {
  const out = new Map(nodes.map((node) => [node.id, [] as { id: string; edge: number }[]]));
  edges.forEach((edge, index) => {
    out.get(edge.source)?.push({ id: edge.target, edge: index });
    out.get(edge.target)?.push({ id: edge.source, edge: index });
  });
  return out;
}

function shortestPath(start: string, target: string, graph: ReturnType<typeof adjacency>) {
  if (start === target) return { nodes: [start], edges: [] as number[] };
  const queue = [start];
  const previous = new Map<string, { id: string; edge: number }>();
  const visited = new Set(queue);
  while (queue.length) {
    const current = queue.shift()!;
    for (const next of graph.get(current) || []) {
      if (visited.has(next.id)) continue;
      visited.add(next.id);
      previous.set(next.id, { id: current, edge: next.edge });
      if (next.id === target) {
        const nodes = [target];
        const edges: number[] = [];
        let cursor = target;
        while (cursor !== start) {
          const step = previous.get(cursor)!;
          nodes.push(step.id);
          edges.push(step.edge);
          cursor = step.id;
        }
        return { nodes: nodes.reverse(), edges: edges.reverse() };
      }
      queue.push(next.id);
    }
  }
  return null;
}

function highlightedPath(nodes: Node[], edges: Edge[], targetId: string) {
  const graph = adjacency(nodes, edges);
  const start = nodes.some((node) => node.id === targetId) ? targetId : nodes.find((node) => node.label === "Invoice")?.id || nodes[0]?.id;
  const highlightedNodes = new Set(start ? [start] : []);
  const highlightedEdges = new Set<number>();
  if (!start) return { nodes: highlightedNodes, edges: highlightedEdges };
  const relevantLabels = new Set(["Supplier", "BankAccount", "Invoice", "PurchaseOrder", "Shipment"]);
  for (const node of nodes) {
    if (!relevantLabels.has(node.label)) continue;
    const path = shortestPath(start, node.id, graph);
    path?.nodes.forEach((id) => highlightedNodes.add(id));
    path?.edges.forEach((index) => highlightedEdges.add(index));
  }
  return { nodes: highlightedNodes, edges: highlightedEdges };
}

/** Small deterministic force layout (no extra dependency): fine for the tens of nodes in one investigation. */
function layout(nodes: Node[], showFindings: boolean) {
  const groups = new Map<string, Node[]>();
  for (const node of nodes) {
    if (!groups.has(node.label)) groups.set(node.label, []);
    groups.get(node.label)!.push(node);
  }
  const pos = new Map<string, Point>();
  for (const [label, group] of groups) {
    group.sort((a, b) => a.id.localeCompare(b.id));
    if (label === "Finding") {
      group.forEach((node, index) => pos.set(node.id, { x: 190 + index * Math.min(150, 800 / Math.max(group.length - 1, 1)), y: 65 }));
      continue;
    }
    const x = COLUMN[label] ?? 590;
    const top = showFindings ? 185 : 120;
    const bottom = 540;
    group.forEach((node, index) => {
      const y = group.length === 1 ? (top + bottom) / 2 : top + index * ((bottom - top) / (group.length - 1));
      pos.set(node.id, { x, y });
    });
  }
  return pos;
}

function edgeEndpoints(a: Point, b: Point) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const distance = Math.max(Math.hypot(dx, dy), 1);
  const inset = Math.min(NODE_W / 2, 34);
  return {
    x1: a.x + (dx / distance) * inset,
    y1: a.y + (dy / distance) * inset,
    x2: b.x - (dx / distance) * inset,
    y2: b.y - (dy / distance) * inset,
  };
}

function fitTransform(pos: Map<string, Point>, ids: Set<string>) {
  const points = [...ids].map((id) => pos.get(id)).filter(Boolean) as Point[];
  const source = points.length ? points : [...pos.values()];
  if (!source.length) return { x: 0, y: 0, scale: 1 };
  const minX = Math.min(...source.map((p) => p.x)) - 100;
  const maxX = Math.max(...source.map((p) => p.x)) + 100;
  const minY = Math.min(...source.map((p) => p.y)) - 85;
  const maxY = Math.max(...source.map((p) => p.y)) + 85;
  const scale = Math.min(1.35, Math.max(0.65, Math.min(W / (maxX - minX), H / (maxY - minY)) * 0.88));
  return { x: W / 2 - ((minX + maxX) / 2) * scale, y: H / 2 - ((minY + maxY) / 2) * scale, scale };
}

export default function GraphView({ data, targetId }: { data: GraphData; targetId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ x: number; y: number; transform: Transform } | null>(null);
  const [showFindings, setShowFindings] = useState(false);
  const [focusPath, setFocusPath] = useState(true);
  const [selected, setSelected] = useState<string | null>(targetId);
  const [fullscreen, setFullscreen] = useState(false);
  const operationalNodes = useMemo(() => data.nodes.filter((node) => node.label !== "Finding"), [data.nodes]);
  const operationalEdges = useMemo(() => data.edges.filter((edge) => edge.type !== "INVOLVES"), [data.edges]);
  const path = useMemo(() => highlightedPath(operationalNodes, operationalEdges, targetId), [operationalNodes, operationalEdges, targetId]);
  const visibleNodes = useMemo(() => data.nodes.filter((node) => showFindings || node.label !== "Finding"), [data.nodes, showFindings]);
  const visibleEdges = useMemo(() => data.edges.filter((edge) => showFindings || edge.type !== "INVOLVES"), [data.edges, showFindings]);
  const positions = useMemo(() => layout(visibleNodes, showFindings), [visibleNodes, showFindings]);
  const initialTransform = useMemo(() => fitTransform(positions, path.nodes), [positions, path.nodes]);
  const [transform, setTransform] = useState<Transform>(initialTransform);

  useEffect(() => setTransform(initialTransform), [initialTransform]);
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === containerRef.current);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  const zoom = useCallback((factor: number, center = { x: W / 2, y: H / 2 }) => {
    setTransform((current) => {
      const scale = Math.min(3, Math.max(0.45, current.scale * factor));
      return {
        scale,
        x: center.x - (center.x - current.x) * (scale / current.scale),
        y: center.y - (center.y - current.y) * (scale / current.scale),
      };
    });
  }, []);

  const onWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const center = { x: ((event.clientX - rect.left) / rect.width) * W, y: ((event.clientY - rect.top) / rect.height) * H };
    zoom(event.deltaY < 0 ? 1.12 : 0.89, center);
  };
  const onPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    if ((event.target as Element).closest("[data-node]")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, transform };
  };
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!dragRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setTransform({
      ...dragRef.current.transform,
      x: dragRef.current.transform.x + (event.clientX - dragRef.current.x) * W / rect.width,
      y: dragRef.current.transform.y + (event.clientY - dragRef.current.y) * H / rect.height,
    });
  };
  const stopDragging = () => { dragRef.current = null; };
  const toggleFullscreen = async () => {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await containerRef.current?.requestFullscreen();
  };

  const selectedNode = visibleNodes.find((node) => node.id === selected);
  const selectedEdges = selected ? data.edges.filter((edge) => edge.source === selected || edge.target === selected) : [];
  const labels = Array.from(new Set(operationalNodes.map((node) => node.label)));
  if (!data.nodes.length) return <Typography color="text.secondary">No findings to visualise.</Typography>;

  return (
    <Box ref={containerRef} sx={{ bgcolor: fullscreen ? "background.default" : "transparent", p: fullscreen ? 2 : 0, height: fullscreen ? "100vh" : "auto", boxSizing: "border-box" }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} justifyContent="space-between" alignItems={{ md: "center" }} sx={{ mb: 1 }}>
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Investigation relationship path</Typography>
          <Typography variant="caption" color="text.secondary">Scroll to zoom, drag the canvas to pan, and select a record for details.</Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <FormControlLabel control={<Switch size="small" checked={focusPath} onChange={(event) => setFocusPath(event.target.checked)} />} label={<Typography variant="caption">Focus path</Typography>} />
          <FormControlLabel control={<Switch size="small" checked={showFindings} onChange={(event) => setShowFindings(event.target.checked)} />} label={<Typography variant="caption">Show findings</Typography>} />
          <Tooltip title="Zoom in"><IconButton size="small" onClick={() => zoom(1.2)}><AddIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Zoom out"><IconButton size="small" onClick={() => zoom(0.8)}><RemoveIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Fit highlighted path"><IconButton size="small" onClick={() => setTransform(fitTransform(positions, path.nodes))}><CenterFocusStrongIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Reset view"><IconButton size="small" onClick={() => setTransform(initialTransform)}><RestartAltIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title={fullscreen ? "Exit fullscreen" : "Fullscreen"}><IconButton size="small" onClick={toggleFullscreen}>{fullscreen ? <CloseFullscreenIcon fontSize="small" /> : <FullscreenIcon fontSize="small" />}</IconButton></Tooltip>
        </Stack>
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={1.5} sx={{ height: fullscreen ? "calc(100vh - 112px)" : "auto" }}>
        <Box sx={{ minWidth: 0, flex: 1, height: fullscreen ? "100%" : { xs: 460, md: 590 }, borderRadius: 2, border: 1, borderColor: "divider", overflow: "hidden", bgcolor: "#f8fafc", position: "relative" }}>
          <Box component="svg" ref={svgRef} viewBox={`0 0 ${W} ${H}`} onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={stopDragging} onPointerCancel={stopDragging}
            sx={{ width: "100%", height: "100%", display: "block", cursor: dragRef.current ? "grabbing" : "grab", touchAction: "none", userSelect: "none" }}>
            <defs>
              <marker id="graph-arrow-path" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#0f766e" /></marker>
              <marker id="graph-arrow-muted" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" /></marker>
              <filter id="target-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#0f766e" floodOpacity="0.24" /></filter>
            </defs>
            <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
              {visibleEdges.map((edge, index) => {
                const a = positions.get(edge.source), b = positions.get(edge.target);
                if (!a || !b) return null;
                const operationalIndex = operationalEdges.findIndex((item) => item.source === edge.source && item.target === edge.target && item.type === edge.type);
                const highlighted = operationalIndex >= 0 && path.edges.has(operationalIndex);
                const involves = edge.type === "INVOLVES";
                const muted = focusPath && !highlighted && !involves;
                const line = edgeEndpoints(a, b);
                return (
                  <g key={`${edge.source}-${edge.type}-${edge.target}-${index}`} opacity={muted ? 0.18 : involves ? 0.35 : 1}>
                    <line {...line} stroke={highlighted ? "#0f766e" : involves ? "#ef4444" : "#94a3b8"} strokeWidth={highlighted ? 3.5 : 1.4} strokeDasharray={involves ? "5 5" : undefined} markerEnd={highlighted ? "url(#graph-arrow-path)" : "url(#graph-arrow-muted)"} />
                    {(!muted || highlighted) && (
                      <g transform={`translate(${(a.x + b.x) / 2} ${(a.y + b.y) / 2})`}>
                        <rect x={-Math.max(30, edge.type.length * 3.8)} y={-10} width={Math.max(60, edge.type.length * 7.6)} height={20} rx={10} fill="#ffffff" stroke={highlighted ? "#99f6e4" : "#e2e8f0"} />
                        <text y={3.5} fontSize="9" fontWeight={highlighted ? 700 : 500} fill={highlighted ? "#0f766e" : "#64748b"} textAnchor="middle">{edge.type.replaceAll("_", " ")}</text>
                      </g>
                    )}
                  </g>
                );
              })}
              {visibleNodes.map((node) => {
                const point = positions.get(node.id)!;
                const isTarget = node.id === targetId;
                const inPath = path.nodes.has(node.id);
                const muted = focusPath && node.label !== "Finding" && !inPath;
                const isSelected = node.id === selected;
                return (
                  <g key={node.id} data-node="true" transform={`translate(${point.x} ${point.y})`} onClick={(event) => { event.stopPropagation(); setSelected(node.id); }} opacity={muted ? 0.28 : 1} style={{ cursor: "pointer" }}>
                    {isTarget && <rect x={-NODE_W / 2 - 7} y={-NODE_H / 2 - 7} width={NODE_W + 14} height={NODE_H + 14} rx={15} fill="none" stroke="#0f766e" strokeWidth="3" filter="url(#target-shadow)" />}
                    <rect x={-NODE_W / 2} y={-NODE_H / 2} width={NODE_W} height={NODE_H} rx={11} fill="#ffffff" stroke={isSelected ? COLORS[node.label] || "#475569" : inPath ? "#cbd5e1" : "#e2e8f0"} strokeWidth={isSelected ? 3 : 1.5} />
                    <rect x={-NODE_W / 2} y={-NODE_H / 2} width={8} height={NODE_H} rx={4} fill={COLORS[node.label] || "#64748b"} />
                    <text x={-NODE_W / 2 + 18} y={-5} fontSize="9" fontWeight="700" fill={COLORS[node.label] || "#64748b"}>{node.label === "BankAccount" ? "BANK ACCOUNT" : node.label.replace(/([a-z])([A-Z])/g, "$1 $2").toUpperCase()}</text>
                    <text x={-NODE_W / 2 + 18} y={13} fontSize="12" fontWeight="700" fill="#0f172a">{node.label === "Finding" ? node.name : node.id}</text>
                    <title>{`${node.label} ${node.id}${node.name ? ` · ${node.name}` : ""}`}</title>
                    {isTarget && <g transform={`translate(0 ${-NODE_H / 2 - 18})`}><rect x="-53" y="-10" width="106" height="20" rx="10" fill="#0f766e" /><text y="4" textAnchor="middle" fontSize="9" fontWeight="700" fill="#ffffff">INVESTIGATION TARGET</text></g>}
                  </g>
                );
              })}
            </g>
          </Box>
        </Box>

        <Paper variant="outlined" sx={{ p: 1.5, width: { xs: "100%", lg: 270 }, flexShrink: 0, overflow: "auto" }}>
          <Typography variant="overline" color="text.secondary">Selected record</Typography>
          {selectedNode ? (
            <Stack spacing={1}>
              <Stack direction="row" spacing={1} alignItems="center"><Box sx={{ width: 10, height: 34, borderRadius: 1, bgcolor: COLORS[selectedNode.label] || "#64748b" }} /><Box><Typography fontWeight={700}>{selectedNode.id}</Typography><Typography variant="caption" color="text.secondary">{selectedNode.label.replace(/([a-z])([A-Z])/g, "$1 $2")}</Typography></Box></Stack>
              {selectedNode.name && <Typography variant="body2">{selectedNode.name}</Typography>}
              {selectedNode.id === targetId && <Chip size="small" color="success" label="Investigation target" sx={{ alignSelf: "flex-start" }} />}
              <Divider />
              <Typography variant="caption" fontWeight={700}>Relationships ({selectedEdges.length})</Typography>
              {selectedEdges.map((edge, index) => {
                const outgoing = edge.source === selectedNode.id;
                return <Typography key={index} variant="caption" color="text.secondary"><b>{edge.type.replaceAll("_", " ")}</b> {outgoing ? "→" : "←"} {outgoing ? edge.target : edge.source}</Typography>;
              })}
              {!selectedEdges.length && <Typography variant="caption" color="text.secondary">No relationships in this investigation view.</Typography>}
            </Stack>
          ) : <Typography variant="body2" color="text.secondary">Select a node to inspect its relationships.</Typography>}
        </Paper>
      </Stack>

      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ mt: 1, alignItems: "center" }}>
        {labels.map((label) => <Stack key={label} direction="row" spacing={0.5} alignItems="center"><Box sx={{ width: 9, height: 9, borderRadius: 0.75, bgcolor: COLORS[label] || "#64748b" }} /><Typography variant="caption">{label.replace(/([a-z])([A-Z])/g, "$1 $2")}</Typography></Stack>)}
        <Divider orientation="vertical" flexItem />
        <Stack direction="row" spacing={0.5} alignItems="center"><Box sx={{ width: 22, borderTop: "3px solid #0f766e" }} /><Typography variant="caption">Relevant path</Typography></Stack>
        <Stack direction="row" spacing={0.5} alignItems="center"><Box sx={{ width: 22, borderTop: "1px solid #94a3b8" }} /><Typography variant="caption">Context</Typography></Stack>
        <Typography variant="caption" color="text.secondary">Finding evidence is hidden by default to keep the procurement path readable.</Typography>
      </Stack>
    </Box>
  );
}
