# Azure infrastructure (placeholder)

Infrastructure-as-code (Bicep/Terraform) for the Azure deployment lands in
**Sprint 12** (see `docs/architecture/09-devops-deployment.md §18.4`).

Target region: **UAE North** (DR paired to UAE Central), subject to per-service
availability — in particular Azure AI Document Intelligence (open question OQ4 in
`observations/02-clarifications.md`).

Planned resources:
- Azure Container Apps (web, api, worker) — same images as local
- Azure Database for PostgreSQL Flexible Server (zone-redundant HA, PITR)
- Azure Blob Storage (private, soft-delete + versioning)
- Azure Key Vault (+ managed identities)
- Azure Cache for Redis or Azure Service Bus
- Azure AI Document Intelligence (region per OQ4)
- Azure Communication Services Email (or SendGrid)
- Azure Front Door + WAF
- Application Insights + Log Analytics
