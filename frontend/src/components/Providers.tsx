"use client";
import { AppBar, Box, Button, Container, CssBaseline, TextField, Toolbar, Typography } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import Link from "next/link";
import theme from "@/theme";
import { ReviewerProvider, useReviewer } from "@/lib/reviewer";

function ReviewerField() {
  const [reviewer, setReviewer] = useReviewer();
  return (
    <TextField size="small" label="Reviewer" value={reviewer} onChange={(e) => setReviewer(e.target.value)} sx={{ width: 180 }} />
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
