"use client";
import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1d4ed8" },
    secondary: { main: "#0f766e" },
    background: { default: "#f5f7fb" },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: "Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
  components: {
    MuiPaper: { defaultProps: { variant: "outlined" } },
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { textTransform: "none" } } },
  },
});

export default theme;
