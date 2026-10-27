"use client";
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, CircularProgress, MenuItem, Paper,
  Select, Stack, Tab, Tabs, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from "@mui/material";
import Grid from "@mui/material/Grid2";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import FindingCard from "@/components/FindingCard";
import GraphView from "@/components/GraphView";
import { api, GraphData, Investigation } from "@/lib/api";
import { SEVERITY_COLOR, STATUS_COLOR, useReviewer } from "@/lib/reviewer";

const POLICY_LABEL: Record<string, [string, "success" | "warning" | "error" | "default"]> = {
  graphrag: ["Policy evidence via GraphRAG SDK", "success"],
  fallback: ["Policy evidence via direct document retrieval (GraphRAG unavailable)", "warning"],
  unavailable: ["Document evidence unavailable", "error"],
  not_requested: ["Policy evidence not requested", "default"],
};

export default function InvestigationPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useReviewer();
  const [inv, setInv] = useState<Investigation | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [compare, setCompare] = useState<any>(null);
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setInv(await api.investigation(id));
      setGraph(await api.graph(id));
      setCompare(await api.compare(id));
    } catch (e) { setError(String(e)); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!inv) return <CircularProgress />;
  const [policyText, policyColor] = POLICY_LABEL[inv.policy_status] || [inv.policy_status, "default"];

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {inv.investigation_id} · opened {new Date(inv.created_at).toLocaleString()} by {inv.created_by}
            </Typography>
            <Typography variant="h5">{inv.question}</Typography>
            <Typography color="text.secondary">
              Target {inv.target_label} <b>{inv.target_id}</b> · suppliers in scope: {inv.scope.suppliers.join(", ")}
            </Typography>
          </Box>
          <Stack alignItems="center">
            <Typography variant="h3" color={inv.score >= 50 ? "error.main" : inv.score >= 25 ? "warning.main" : "text.primary"}>{inv.score}</Typography>
            <Chip color={SEVERITY_COLOR[inv.severity]} label={`review priority: ${inv.severity}`} />
          </Stack>
          <Stack spacing={1}>
            <Typography variant="caption">Investigation status</Typography>
            <Select size="small" value={inv.status} disabled={!user}
              onChange={async (e) => setInv(await api.setStatus(inv.investigation_id, e.target.value))}>
              {["open", "in_review", "closed"].map((s) => <MenuItem key={s} value={s}>{s.replace("_", " ")}</MenuItem>)}
            </Select>
            <Chip size="small" color={STATUS_COLOR[inv.status]} label={inv.status} />
          </Stack>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
          <Typography variant="h6" sx={{ mr: 1 }}>Explanation</Typography>
          {inv.explanation_mode && <Chip size="small" label={inv.explanation_mode.replaceAll("_", " ")} />}
          {inv.grounding && (
            <Chip size="small" color={inv.grounding.supported ? "success" : "error"}
              label={inv.grounding.supported
                ? `grounded: ${inv.grounding.ids_checked} IDs and ${inv.grounding.numbers_checked} numbers verified`
                : "grounding failed"} />
          )}
          <Chip size="small" color={policyColor} variant="outlined" label={policyText} />
        </Stack>
        <Box sx={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.6 }}>{inv.explanation || "No explanation generated."}</Box>
        {!!inv.grounding?.rejected_attempts?.length && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            {inv.grounding.rejected_attempts.length} LLM draft(s) were rejected by the grounding validator and are kept in the audit trail.
          </Alert>
        )}
      </Paper>

      <Tabs value={tab} onChange={(_, v) => setTab(v)}>
        <Tab label={`Findings (${inv.findings.length})`} />
        <Tab label="Graph" />
        <Tab label="Ask the agent" />
        <Tab label="History & audit" />
      </Tabs>

      {tab === 0 && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, lg: 9 }}>
            <Stack spacing={1}>
              {inv.findings.length === 0 && <Alert severity="success">No rule produced a finding for this entity or its connected suppliers.</Alert>}
              {inv.findings.map((f, i) => (
                <FindingCard key={f.finding_id} finding={f} investigationId={inv.investigation_id} onChange={load} defaultExpanded={i === 0} />
              ))}
            </Stack>
          </Grid>
          <Grid size={{ xs: 12, lg: 3 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2">Score breakdown</Typography>
              <Table size="small"><TableBody>
                {inv.score_detail.breakdown.map((b) => (
                  <TableRow key={b.finding_id}><TableCell>{b.rule_id}</TableCell><TableCell align="right">{b.points}</TableCell></TableRow>
                ))}
                <TableRow><TableCell><b>Total{inv.score_detail.capped ? ` (capped from ${inv.score_detail.raw_points})` : ""}</b></TableCell>
                  <TableCell align="right"><b>{inv.score}</b></TableCell></TableRow>
              </TableBody></Table>
              <Typography variant="caption" color="text.secondary">
                Points are fixed per rule version and indicate review priority, not probability. Dismissed findings do not count.
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      )}

      {tab === 1 && <Paper sx={{ p: { xs: 1.5, md: 2 } }}>{graph ? <GraphView data={graph} targetId={inv.target_id} /> : <CircularProgress />}</Paper>}

      {tab === 2 && <Paper sx={{ p: 2 }}><ChatPanel investigationId={inv.investigation_id} /></Paper>}

      {tab === 3 && (
        <Stack spacing={2}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Related investigations (FOLLOWED_BY)</Typography>
            {[...inv.history.previous.map((h) => ({ ...h, rel: "earlier" })), ...inv.history.next.map((h) => ({ ...h, rel: "later" }))].map((h) => (
              <Typography key={h.investigation_id} variant="body2">
                {h.rel}: <Link href={`/investigations/${h.investigation_id}`}>{h.investigation_id}</Link> · {h.question} · score {h.score} · {h.status} · {new Date(h.created_at).toLocaleString()}
              </Typography>
            ))}
            {!inv.history.previous.length && !inv.history.next.length && <Typography color="text.secondary">None.</Typography>}
            {compare?.has_previous && (
              <Alert severity="info" sx={{ mt: 1 }}>
                Since {compare.previous_investigation.investigation_id}: {compare.new_findings.length} new finding(s)
                {compare.new_findings.length ? ` (${compare.new_findings.map((f: any) => f.finding_id).join(", ")})` : ""};
                {" "}{compare.no_longer_detected.length} no longer detected. Reviewer decisions on earlier findings:{" "}
                {compare.previous_findings.map((f: any) => `${f.finding_id}=${f.status}`).join(", ")}
              </Alert>
            )}
          </Paper>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Agent tool trace</Typography>
            <Table size="small">
              <TableHead><TableRow><TableCell>Actor</TableCell><TableCell>Tool</TableCell><TableCell>Arguments</TableCell><TableCell>Result</TableCell><TableCell align="right">ms</TableCell></TableRow></TableHead>
              <TableBody>
                {inv.tool_trace.map((s, i) => (
                  <TableRow key={i}>
                    <TableCell>{s.actor}</TableCell><TableCell><code>{s.tool}</code></TableCell>
                    <TableCell sx={{ fontSize: 12, maxWidth: 420 }}><code>{JSON.stringify(s.args)}</code></TableCell>
                    <TableCell>{s.ok ? <Chip size="small" color="success" label={s.status || "ok"} /> : <Chip size="small" color="error" label={s.error?.slice(0, 80)} />}</TableCell>
                    <TableCell align="right">{s.ms}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>Grounding report (raw)</AccordionSummary>
            <AccordionDetails><Box component="pre" sx={{ fontSize: 12, overflowX: "auto" }}>{JSON.stringify(inv.grounding, null, 2)}</Box></AccordionDetails>
          </Accordion>
        </Stack>
      )}
      <Box><Button component={Link} href="/">Back to dashboard</Button></Box>
    </Stack>
  );
}
