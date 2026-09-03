/** PATH: next.config.js (repo root — REPLACE existing file with this)
 * Only change vs. your current file: webpack.watchOptions.ignored, so the
 * dev server's file watcher never recurses into heavy non-frontend
 * directories (Python venvs, git internals, the backend's own node stuff).
 * This is a safety net — the real fix is removing venv/ from the repo
 * entirely (see FIX_venv_oom.txt) — but this protects against the same
 * class of crash if something similar happens again.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async redirects() {
    return [{ source: "/my-goals", destination: "/goals", permanent: true }];
  },
  webpack: (config, { dev }) => {
    if (!dev) config.cache = false;
    config.watchOptions = {
      ...config.watchOptions,
      ignored: [
        "**/node_modules/**",
        "**/.git/**",
        "**/.next/**",
        "**/venv/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/astra-backend/**",
      ],
    };
    return config;
  },
};

module.exports = nextConfig;