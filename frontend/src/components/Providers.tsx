"use client";
import { AppBar, Box, Button, Chip, Container, CssBaseline, TextField, Toolbar, Tooltip, Typography } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import Link from "next/link";
import { useState } from "react";
import theme from "@/theme";
import { ReviewerProvider, useReviewer } from "@/lib/reviewer";

function ReviewerField() {
  const { user, error, signIn, signOut } = useReviewer();
  const [token, setTokenInput] = useState("");
  if (user) {
    return (
      <>
        <Chip label={`${user.name} (${user.role})`} />
        <Button size="small" onClick={signOut}>Sign out</Button>
      </>
    );
  }
  return (
    <Box component="form" sx={{ display: "flex", gap: 1 }}
      onSubmit={(e) => { e.preventDefault(); signIn(token).finally(() => setTokenInput("")); }}>
      <Tooltip title={error || "Token from CHAINSLEUTH_API_USERS in backend/.env"}>
        <TextField size="small" type="password" label="API token" value={token} error={!!error}
          onChange={(e) => setTokenInput(e.target.value)} sx={{ width: 200 }} />
      </Tooltip>
      <Button size="small" type="submit" disabled={!token.trim()}>Sign in</Button>
    </Box>
  );
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <ReviewerProvider>
        <CssBaseline />
        <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
          <Toolbar sx={{ gap: 2 }}>
            <TravelExploreIcon color="primary" />
            <Typography variant="h6" component={Link} href="/" sx={{ color: "inherit", textDecoration: "none" }}>
              ChainSleuth
            </Typography>
            <Button component={Link} href="/">Dashboard</Button>
            <Button component={Link} href="/findings">Findings</Button>
            <Box sx={{ flex: 1 }} />
            <ReviewerField />
          </Toolbar>
        </AppBar>
        <Container maxWidth="xl" sx={{ py: 3 }}>
          {children}
        </Container>
        <Box component="footer" sx={{ textAlign: "center", color: "text.secondary", fontSize: 12, pb: 3 }}>
          Synthetic data only. Findings are risk signals for human review, not determinations of wrongdoing.
        </Box>
      </ReviewerProvider>
    </ThemeProvider>
  );
}
