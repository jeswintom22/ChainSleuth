"use client";
import { Alert, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import FindingCard from "@/components/FindingCard";
import { api, Finding } from "@/lib/api";

const RULES = ["", "R1_SHARED_ACCOUNT", "R2_DUPLICATE_INVOICE", "R3_RECONCILIATION", "R4_ROUTE_ANOMALY"];
const STATUSES = ["", "open", "needs_review", "confirmed", "dismissed"];

export default function FindingsPage() {
  const [rule, setRule] = useState("");
  const [status, setStatus] = useState("");
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.findings({ rule_id: rule, status });
      setFindings(await Promise.all(list.map((f) => api.finding(f.finding_id))));
    } catch (e) { setError(String(e)); }
  }, [rule, status]);
  useEffect(() => { load(); }, [load]);

  return (
    <Stack spacing={2}>
      <Typography variant="h5">Persisted findings</Typography>
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={2}>
          <TextField select size="small" label="Rule" value={rule} onChange={(e) => setRule(e.target.value)} sx={{ width: 260 }}>
            {RULES.map((r) => <MenuItem key={r} value={r}>{r || "All rules"}</MenuItem>)}
          </TextField>
          <TextField select size="small" label="Status" value={status} onChange={(e) => setStatus(e.target.value)} sx={{ width: 200 }}>
            {STATUSES.map((s) => <MenuItem key={s} value={s}>{s || "All statuses"}</MenuItem>)}
          </TextField>
        </Stack>
      </Paper>
      {error && <Alert severity="error">{error}</Alert>}
      {findings?.length === 0 && <Alert severity="info">No findings match. Run detection from the dashboard.</Alert>}
      {findings?.map((f) => <FindingCard key={f.finding_id} finding={f} onChange={load} />)}
    </Stack>
  );
}
