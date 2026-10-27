"use client";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, FormControlLabel, Paper, Stack, Switch,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import Grid from "@mui/material/Grid2";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, InvestigationSummary } from "@/lib/api";
import { SEVERITY_COLOR, STATUS_COLOR, useReviewer } from "@/lib/reviewer";

const SUGGESTIONS = [
  { q: "Why should INV-1043 be investigated, and which procurement policy supports the recommendation?", id: "INV-1043" },
  { q: "Is supplier SUP-020 connected to other supplier records?", id: "SUP-020" },
  { q: "Does PO-5060 reconcile with its deliveries?", id: "PO-5060" },
  { q: "Check SUP-043 partial deliveries (expected clean)", id: "SUP-043" },
];

function HealthChip({ label, ok, detail }: { label: string; ok: boolean; detail?: string }) {
  return <Chip size="small" color={ok ? "success" : "default"} variant={ok ? "filled" : "outlined"} label={detail ? `${label}: ${detail}` : label} />;
}

export default function Dashboard() {
  const router = useRouter();
  const { user } = useReviewer();
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [stats, setStats] = useState<Record<string, any> | null>(null);
  const [invs, setInvs] = useState<InvestigationSummary[]>([]);
  const [question, setQuestion] = useState(SUGGESTIONS[0].q);
  const [entity, setEntity] = useState(SUGGESTIONS[0].id);
  const [useLlm, setUseLlm] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth(h);
      if (h.dataset_loaded) {
        setStats(await api.stats());
        setInvs(await api.investigations());
      }
    } catch (e) {
      setError(String(e));
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label); setError(null); setNotice(null);
    try { await fn(); } catch (e) { setError(String(e)); } finally { setBusy(null); refresh(); }
  };

  const investigate = () => run("investigate", async () => {
    const inv = await api.createInvestigation({
      question, entity_id: entity || undefined,
      use_llm: health?.llm_available ? useLlm : false,
    });
    router.push(`/investigations/${inv.investigation_id}`);
  });

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5">Procurement investigation workspace</Typography>
        <Typography color="text.secondary">
          FalkorDB traverses supplier, invoice, order and shipment relationships; deterministic rules score the signals;
          the agent assembles an evidence-backed case for human review.
        </Typography>
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}

      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
          <Typography variant="subtitle2" sx={{ mr: 1 }}>System</Typography>
          {health ? (
            <>
              <HealthChip label="FalkorDB" ok={!!health.falkordb} detail={health.falkordb_module_version ? `module ${health.falkordb_module_version}` : undefined} />
              <HealthChip label="Dataset" ok={!!health.dataset_loaded} detail={health.dataset_loaded ? "loaded" : "not loaded"} />
              <HealthChip label="LLM" ok={!!health.llm_available} detail={health.llm_available ? "available" : "deterministic mode"} />
              <HealthChip label="GraphRAG" ok={!!health.graphrag_available} detail={health.graphrag_available ? "ready" : "fallback retrieval"} />
            </>
          ) : <CircularProgress size={18} />}
          <Box sx={{ flex: 1 }} />
          <Button size="small" startIcon={<RefreshIcon />} disabled={!!busy || user?.role !== "admin"}
            onClick={() => run("load", async () => { const r = await api.loadDataset(false); setNotice(`Dataset loaded; integrity ${r.integrity.ok ? "OK" : "FAILED: " + r.integrity.problems.join("; ")}`); })}>
            {busy === "load" ? "Loading..." : "Load synthetic dataset"}
          </Button>
          <Button size="small" variant="outlined" startIcon={<PlayArrowIcon />} disabled={!!busy || !user || !health?.dataset_loaded}
            onClick={() => run("detect", async () => { const r = await api.runDetection(); setNotice(`Detection run ${r.run_id}: ${r.signals} signals, ${r.new_findings} new findings`); })}>
            {busy === "detect" ? "Running..." : "Run detection"}
          </Button>
        </Stack>
      </Paper>

      {stats && (
        <Grid container spacing={2}>
          {[["Suppliers", stats.entities.Supplier], ["Invoices", stats.entities.Invoice], ["Purchase orders", stats.entities.PurchaseOrder],
            ["Shipments", stats.entities.Shipment], ["Active findings", stats.findings], ["Investigations", stats.entities.Investigation || 0]].map(([k, v]) => (
            <Grid key={k as string} size={{ xs: 6, md: 2 }}>
              <Card variant="outlined"><CardContent>
                <Typography variant="body2" color="text.secondary">{k}</Typography>
                <Typography variant="h5">{v ?? 0}</Typography>
              </CardContent></Card>
            </Grid>
          ))}
        </Grid>
      )}

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>New investigation</Typography>
        <Stack spacing={2}>
          <TextField label="Question" value={question} onChange={(e) => setQuestion(e.target.value)} fullWidth multiline />
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="center">
            <TextField label="Target entity (SUP-/INV-/PO-/SHP-)" value={entity} onChange={(e) => setEntity(e.target.value.toUpperCase())} sx={{ width: 300 }} />
            <FormControlLabel control={<Switch checked={useLlm && !!health?.llm_available} disabled={!health?.llm_available} onChange={(e) => setUseLlm(e.target.checked)} />}
              label={health?.llm_available ? "Agent uses LLM (tool calling + grounded summary)" : "LLM unavailable: deterministic agent"} />
            <Box sx={{ flex: 1 }} />
            <Button variant="contained" size="large" startIcon={busy === "investigate" ? <CircularProgress size={18} color="inherit" /> : <SearchIcon />}
              disabled={!!busy || !health?.dataset_loaded || question.length < 3} onClick={investigate}>
              {busy === "investigate" ? "Investigating..." : "Investigate"}
            </Button>
          </Stack>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {SUGGESTIONS.map((s) => (
              <Chip key={s.id} label={s.q} variant="outlined" onClick={() => { setQuestion(s.q); setEntity(s.id); }} />
            ))}
          </Stack>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Investigations</Typography>
        {invs.length === 0 ? <Typography color="text.secondary">No investigations yet.</Typography> : (
          <Table size="small">
            <TableHead><TableRow>
              <TableCell>ID</TableCell><TableCell>Question</TableCell><TableCell>Target</TableCell><TableCell>Score</TableCell>
              <TableCell>Findings</TableCell><TableCell>Status</TableCell><TableCell>Created</TableCell>
            </TableRow></TableHead>
            <TableBody>
              {invs.map((i) => (
                <TableRow key={i.investigation_id} hover sx={{ cursor: "pointer" }} onClick={() => router.push(`/investigations/${i.investigation_id}`)}>
                  <TableCell><Link href={`/investigations/${i.investigation_id}`}>{i.investigation_id}</Link></TableCell>
                  <TableCell sx={{ maxWidth: 480 }}>{i.question}</TableCell>
                  <TableCell>{i.target_id}</TableCell>
                  <TableCell><Chip size="small" color={SEVERITY_COLOR[i.severity || "low"]} label={`${i.score} · ${i.severity}`} /></TableCell>
                  <TableCell>{i.finding_count}</TableCell>
                  <TableCell><Chip size="small" color={STATUS_COLOR[i.status]} label={i.status} /></TableCell>
                  <TableCell>{new Date(i.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Stack>
  );
}
