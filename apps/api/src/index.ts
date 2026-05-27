import { serve } from "@hono/node-server";
import app from "./app.js";

const port = Number(process.env["PORT"] ?? 3000);

serve({ fetch: app.fetch, port }, () => {
  process.stdout.write(`Score API listening on http://localhost:${port}\n`);
  process.stdout.write(`POST /score  — submit a chat for scoring\n`);
  process.stdout.write(`GET  /health — liveness check\n`);
});
