const fs = require("fs");
const https = require("https");
const next = require("next");

const port = parseInt(process.env.PORT || "3000", 10);
const certPath = process.env.TLS_CERT_PATH;
const keyPath = process.env.TLS_KEY_PATH;
const hostname = "0.0.0.0";

const app = next({ dev: false, hostname, port });
const handle = app.getRequestHandler();

app
  .prepare()
  .then(() => {
    if (certPath && keyPath) {
      const options = {
        cert: fs.readFileSync(certPath),
        key: fs.readFileSync(keyPath)
      };
      https
        .createServer(options, (req, res) => handle(req, res))
        .listen(port, hostname, () => {
          console.log(`HTTPS frontend running on https://${hostname}:${port}`);
        });
    } else {
      app.listen(port, hostname, () => {
        console.log(`HTTP frontend running on http://${hostname}:${port}`);
      });
    }
  })
  .catch((err) => {
    console.error("Failed to start Next.js server:", err);
    process.exit(1);
  });
