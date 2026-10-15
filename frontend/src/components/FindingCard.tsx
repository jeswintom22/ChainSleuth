"use client";
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, ButtonGroup, Chip, Stack, Table, TableBody,
  TableCell, TableRow, TextField, Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useState } from "react";
import { api, Finding } from "@/lib/api";
import { SEVERITY_COLOR, STATUS_COLOR, useReviewer } from "@/lib/reviewer";

const RULE_TITLES: Record<string, string> = {
  R1_SHARED_ACCOUNT: "Shared payout account",
  R2_DUPLICATE_INVOICE: "Exact duplicate invoice",
  R3_RECONCILIATION: "Invoice / order / delivery reconciliation",
  R4_ROUTE_ANOMALY: "Unapproved warehouse transition",
};

function fmt(v: unknown): string {
  if (Array.isArray(v)) return v.join(", ") || "none";
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function FindingCard({ finding, investigationId, onChange, defaultExpanded }: {
  finding: Finding; investigationId?: string; onChange?: () => void; defaultExpanded?: boolean;
}) {
  const [reviewer] = useReviewer();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (decision: string) => {
    setBusy(true); setError(null);
    try {
      await api.review(finding.finding_id, { decision, reviewer, note, investigation_id: investigationId });
      setNote("");
      onChange?.();
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  return (
    <Accordion defaultExpanded={defaultExpanded} disableGutters variant="outlined">
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack spacing={0.5} sx={{ width: "100%" }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography fontWeight={600}>{RULE_TITLES[finding.rule_id] || finding.rule_id}</Typography>
            <Chip size="small" label={finding.category.replaceAll("_", " ")} variant="outlined" />
            <Chip size="small" color={SEVERITY_COLOR[finding.severity]} label={`${finding.score} pts`} />
            <Chip size="small" color={STATUS_COLOR[finding.status]} label={finding.status.replace("_", " ")} />
            <Typography variant="caption" color="text.secondary">{finding.finding_id} · {finding.rule_id} v{finding.rule_version}</Typography>
          </Stack>
          <Typography variant="body2">{finding.evidence_summary}</Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={2}>
          <Box>
            <Typography variant="subtitle2">Values (from graph records and deterministic arithmetic)</Typography>
            <Table size="small"><TableBody>
              {Object.entries(finding.values).map(([k, v]) => (
                <TableRow key={k}><TableCell sx={{ width: 240, color: "text.secondary" }}>{k}</TableCell><TableCell>{fmt(v)}</TableCell></TableRow>
              ))}
            </TableBody></Table>
          </Box>
          <Box>
            <Typography variant="subtitle2">Evidence paths</Typography>
            <Box component="pre" sx={{ m: 0, p: 1.5, bgcolor: "grey.100", borderRadius: 1, fontSize: 12, overflowX: "auto" }}>
              {finding.evidence_paths.join("\n")}
            </Box>
            <Typography variant="caption" color="text.secondary">
              Reproduce with named query <code>{finding.query?.name}</code> and params <code>{JSON.stringify(finding.query?.params)}</code>
            </Typography>
          </Box>
          {!!finding.policy_evidence?.length && (
            <Box>
              <Typography variant="subtitle2">Supporting policy passages</Typography>
              <Stack spacing={1}>
                {finding.policy_evidence.map((c) => (
                  <Alert key={c.chunk_id} severity="info" icon={false}>
                    <Typography variant="caption" fontWeight={600}>
                      {c.document_id} · {c.section} <Chip size="small" label={c.retrieval_method} sx={{ ml: 1 }} />
                    </Typography>
                    <Typography variant="body2">{c.text}</Typography>
                  </Alert>
                ))}
              </Stack>
            </Box>
          )}
          {!!finding.reviews?.length && (
            <Box>
              <Typography variant="subtitle2">Review history</Typography>
              {finding.reviews.map((r) => (
                <Typography key={r.action_id} variant="body2">
                  {new Date(r.created_at).toLocaleString()} · <b>{r.reviewer}</b>: {r.previous_status} → <b>{r.decision}</b>{r.note ? ` — ${r.note}` : ""}
                </Typography>
              ))}
            </Box>
          )}
          <Box>
            <Typography variant="subtitle2" gutterBottom>Reviewer decision</Typography>
            {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
            <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems="center">
              <TextField size="small" label="Note / justification" value={note} onChange={(e) => setNote(e.target.value)} sx={{ flex: 1 }} />
              <ButtonGroup disabled={busy || !reviewer}>
                <Button onClick={() => decide("needs_review")}>Needs review</Button>
                <Button color="error" onClick={() => decide("confirmed")}>Confirm signal</Button>
                <Button color="success" onClick={() => decide("dismissed")}>Dismiss</Button>
                <Button color="inherit" onClick={() => decide("open")}>Reopen</Button>
              </ButtonGroup>
            </Stack>
          </Box>
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}
