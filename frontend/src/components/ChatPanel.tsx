"use client";
import { Alert, Box, Button, Chip, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import { useEffect, useState } from "react";
import { api, Turn } from "@/lib/api";

export default function ChatPanel({ investigationId }: { investigationId: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.turns(investigationId).then(setTurns).catch((e) => setError(String(e))); }, [investigationId]);

  const send = async () => {
    setBusy(true); setError(null);
    try {
      const t = await api.ask(investigationId, q);
      setTurns((prev) => [...prev, t]);
      setQ("");
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  return (
    <Stack spacing={1.5}>
      <Typography variant="body2" color="text.secondary">
        Follow-up questions are answered only from this investigation&apos;s evidence and read-only graph tools. Answers that cite
        IDs or numbers not in the evidence are rejected. The conversation is stored in FalkorDB.
      </Typography>
      {turns.map((t) => (
        <Box key={t.turn_id}>
          <Typography variant="body2" fontWeight={600}>Q: {t.question}</Typography>
          <Box sx={{ whiteSpace: "pre-wrap", fontSize: 14, p: 1.5, bgcolor: "grey.50", borderRadius: 1, border: 1, borderColor: "divider" }}>
            {t.answer}
          </Box>
          <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
            <Chip size="small" label={t.mode} />
            <Chip size="small" color={t.grounded ? "success" : "warning"} label={t.grounded ? "grounded" : "ungrounded"} />
            <Typography variant="caption" color="text.secondary">{new Date(t.created_at).toLocaleString()}</Typography>
          </Stack>
        </Box>
      ))}
      {error && <Alert severity="error">{error}</Alert>}
      <Stack direction="row" spacing={1}>
        <TextField size="small" fullWidth placeholder="e.g. How many units were not delivered for INV-1043?" value={q}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && q.length > 1 && !busy) send(); }} />
        <Button variant="contained" onClick={send} disabled={busy || q.length < 2} startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}>
          Ask
        </Button>
      </Stack>
    </Stack>
  );
}
