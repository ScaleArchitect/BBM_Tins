/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces a minimal standalone server for the Docker image.
  output: "standalone",
  reactStrictMode: true,
};

module.exports = nextConfig;
