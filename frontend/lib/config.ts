// Base path for the REST API. In local/Azure deployments the reverse proxy
// routes `/api` to the FastAPI backend (docs/architecture/01, 09).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";
