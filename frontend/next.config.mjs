const API = process.env.CHAINSLEUTH_API_URL || "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API calls to the FastAPI backend so the browser talks to one origin.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
  // Investigations with live LLM calls can take a while.
  experimental: { proxyTimeout: 180_000 },
};

export default nextConfig;
