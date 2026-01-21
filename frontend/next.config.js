/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return {
      afterFiles: [
        {
          source: "/api/:path*",
          destination: "http://quilr-backend:8000/api/:path*"
        },
        {
          source: "/auth/:path*",
          destination: "http://quilr-backend:8000/auth/:path*"
        }
      ]
    };
  }
};

module.exports = nextConfig;
