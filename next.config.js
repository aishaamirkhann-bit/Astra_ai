/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async redirects() {
    return [{ source: "/goals", destination: "/my-goals", permanent: true }];
  },
  webpack: (config, { dev }) => {
    if (!dev) config.cache = false;
    return config;
  },
};

module.exports = nextConfig;
