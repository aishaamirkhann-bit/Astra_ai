/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async redirects() {
    return [{ source: "/my-goals", destination: "/goals", permanent: true }];
  },
  webpack: (config, { dev }) => {
    if (!dev) config.cache = false;
    return config;
  },
};

module.exports = nextConfig;
