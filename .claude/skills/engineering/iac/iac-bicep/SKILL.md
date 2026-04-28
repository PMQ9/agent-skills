---
name: iac-bicep
description: Use this skill for any Azure-native IaC work using Bicep or ARM templates. Trigger on writing or refactoring `.bicep` files, designing Bicep modules, working with deployment scopes (resource group / subscription / management group / tenant), running what-if previews, using the Bicep registry, deploying via `az deployment` or `New-AzDeployment`, converting ARM JSON to Bicep, or choosing Bicep vs Terraform on Azure. Use alongside the azure skill for Azure service knowledge.
---

# Bicep / ARM

Bicep is Azure's first-party IaC language. It compiles to ARM JSON, which is what Azure Resource Manager actually deploys. If your stack is Azure-only, Bicep is usually the better choice than Terraform: same-day support for new resource types, no state file to manage, native `what-if`, and tighter integration with Azure Policy and deployment stacks.

When **not** to choose Bicep:

- Multi-cloud — Bicep only does Azure.
- You need 3rd-party providers (GitHub, Datadog, Cloudflare, etc.) — Terraform's ecosystem is much richer.
- The team is already heavy on Terraform and the Azure-only sub-portion isn't worth a second tool.

## How Bicep relates to ARM

ARM is the underlying API and template format. Bicep is a transpiler that produces ARM JSON. There's no runtime Bicep engine in Azure — just a more pleasant authoring experience that compiles down. This means:

- Anything you can do in ARM, you can do in Bicep (and almost everything is more concise).
- Bicep has no state file. ARM tracks deployments per scope (RG/sub/MG); the "state" is the live state of resources in Azure.
- You can decompile existing ARM to Bicep (`bicep decompile`) — useful but the output usually needs cleanup.

## Deployment scopes

A Bicep file is deployed at a scope. Pick deliberately:

| Scope | When | `targetScope` |
|---|---|---|
| **Resource group** | The default. Resources within one RG. | `'resourceGroup'` (default) |
| **Subscription** | Creating RGs, subscription-level RBAC, policies. | `'subscription'` |
| **Management group** | Cross-subscription policy / RBAC, MG hierarchy. | `'managementGroup'` |
| **Tenant** | Rare — root-level tenant config. | `'tenant'` |

```bicep
targetScope = 'subscription'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-orders-prod'
  location: 'westeurope'
  tags: tags
}

module orders 'modules/orders.bicep' = {
  scope: rg
  name: 'orders-deployment'
  params: { ... }
}
```

A subscription-scoped deployment can have RG-scoped modules; that's the canonical pattern for "create the RG and everything in it."

## File structure

```
infra/
├── main.bicep                  # entry point per environment / per stack
├── prod.bicepparam
├── staging.bicepparam
└── modules/
    ├── network.bicep
    ├── app-service.bicep
    ├── sql.bicep
    └── monitoring.bicep
```

The `main.bicep` file orchestrates modules and accepts environment-specific parameters. `*.bicepparam` files (a real, typed parameter file format — much better than the ARM JSON parameter file) feed values per environment.

## Modules

```bicep
// modules/storage.bicep
@description('Storage account name. 3-24 lowercase alphanumeric.')
@minLength(3)
@maxLength(24)
param name string

@description('Azure region.')
param location string

@allowed(['Standard_LRS', 'Standard_ZRS', 'Standard_GZRS'])
param skuName string = 'Standard_ZRS'

param tags object = {}

resource storage 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: name
  location: location
  sku: { name: skuName }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
  }
  tags: tags
}

output id string = storage.id
output name string = storage.name
```

Module conventions:

- One responsibility per file.
- `@description`, `@allowed`, `@minLength`, etc., on parameters — they appear in `what-if` and surface in documentation.
- Type parameters (`string`, `int`, `bool`, `object`, `array`, plus user-defined types).
- Outputs only what consumers actually need.
- Sensible defaults so the simple call stays simple.

### User-defined types (Bicep 0.12+)

```bicep
type subnetConfig = {
  name: string
  addressPrefix: string
  delegations: string[]?
  privateEndpoint: bool
}

param subnets subnetConfig[]
```

Use these instead of typeless `object` whenever you have a structured input. Tooling and `what-if` benefit.

## The Bicep registry

Reusable modules can be published to a Bicep registry (an Azure Container Registry):

```bicep
module net 'br:myacr.azurecr.io/bicep/network:v1.2.0' = {
  scope: rg
  name: 'network'
  params: { ... }
}
```

For public reuse, **Azure Verified Modules** (AVM) are Microsoft-published, supported, opinionated modules covering every common service. They're a strong default — well-tested, well-documented, conform to Azure best practices. Prefer AVM over rolling your own for standard resources unless you have specific reasons.

```bicep
module sa 'br/public:avm/res/storage/storage-account:0.14.0' = {
  scope: rg
  name: 'sa'
  params: {
    name: 'sapayments${uniqueString(rg.id)}'
    location: location
    skuName: 'Standard_ZRS'
    publicNetworkAccess: 'Disabled'
  }
}
```

## Parameter files (`.bicepparam`)

```bicep
// prod.bicepparam
using './main.bicep'

param environment = 'prod'
param location = 'westeurope'
param sqlAdminPassword = readEnvironmentVariable('SQL_ADMIN_PW')
```

Note: `readEnvironmentVariable` and `getSecret` (for Key Vault references) are runtime-resolved at deploy time, so secrets never sit in the file. This is the *only* sensible way to handle secrets in Bicep parameters.

## Existing resources

To reference a resource that already exists (without managing it), use `existing`:

```bicep
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: 'kv-shared-prod'
  scope: resourceGroup('rg-shared-prod')
}

// then use kv.properties.vaultUri, kv.id, etc.
```

This is how you stitch a workload deployment to a platform deployment without duplicating ownership.

## What-if

Always run `what-if` before applying anything that matters:

```bash
az deployment group what-if \
  --resource-group rg-orders-prod \
  --template-file main.bicep \
  --parameters prod.bicepparam
```

`what-if` shows what would change: creates, modifies, deletes, no-ops. It's not perfect (some resource types report inaccurate diffs; "ignore" lists exist for noisy properties), but it's close enough that you should never deploy to prod without it.

In CI, post the `what-if` output as a PR comment for review — same role as a Terraform plan in review.

## Deployment stacks

A relatively new feature that gives Bicep an answer to one of Terraform's strengths: **deletion of resources removed from the template**.

Without deployment stacks, ARM/Bicep deployments are *additive* — if you remove a resource from your template, it stays in Azure (orphaned). Stacks track which resources belong to a deployment and can clean them up when removed:

```bash
az stack group create \
  --name orders-prod \
  --resource-group rg-orders-prod \
  --template-file main.bicep \
  --parameters prod.bicepparam \
  --action-on-unmanage deleteAll \
  --deny-settings-mode denyDelete
```

`--action-on-unmanage` controls what happens to resources removed from the template: `deleteAll`, `deleteResources`, or `detachAll`.

`--deny-settings-mode denyDelete` adds a guard so non-stack operations can't delete the resources, similar to `prevent_destroy` in Terraform.

For new Bicep work, **use deployment stacks**. They close the most-common "we removed it from Bicep but it's still in Azure" gap.

## Conditions and loops

```bicep
// Conditional resource
resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (enableAppInsights) {
  name: 'ai-${appName}'
  location: location
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logAnalytics.id }
}

// Loop over array
resource subnets 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' = [for s in subnetConfigs: {
  parent: vnet
  name: s.name
  properties: {
    addressPrefix: s.addressPrefix
  }
}]

// Loop with index
resource ips 'Microsoft.Network/publicIPAddresses@2024-01-01' = [for (region, i) in regions: {
  name: 'pip-${i}-${region}'
  location: region
  // ...
}]
```

Bicep loops are the equivalent of Terraform's `for_each`. They're indexed by position in the input array, so reordering inputs causes resources to be recreated. Use stable, deterministic ordering — alphabetically, or by a sort key in the input — to avoid surprise replacements.

## Outputs and chaining

Modules expose outputs; consumers chain them:

```bicep
module net './modules/network.bicep' = {
  name: 'net'
  params: { ... }
}

module app './modules/app.bicep' = {
  name: 'app'
  params: {
    subnetId: net.outputs.appSubnetId
  }
}
```

The deployment engine figures out the dependency order — no `dependsOn` needed.

`output` should not be used to "return" sensitive values. Outputs are stored in the deployment history; secrets there are leaked. Use Key Vault references or pass secrets via secure parameters (`@secure()`), and don't echo them back as outputs.

## ARM-isms still useful in Bicep

- **`copy` loops** in ARM JSON map to Bicep's `for` loops.
- **Linked / nested templates** map to Bicep modules.
- **`reference()`, `resourceId()`, `subscriptionResourceId()`** — usually unnecessary in Bicep (you reference resources by symbolic name), but appear when interacting with raw ARM expressions.
- **`uniqueString()`** for deterministic suffixes — `${uniqueString(rg.id)}` is the idiomatic way to get a stable suffix per RG.

## Linting and validation

- `bicep build main.bicep` — compiles to ARM JSON; fails on errors.
- `bicep lint` — surfaces best-practice issues; configurable in `bicepconfig.json`.
- `az deployment validate` — server-side validation against Azure (catches things the linter can't, like quota and policy issues).
- `az deployment what-if` — preview changes.
- **PSRule for Azure** — policy-as-code rules for Bicep / ARM templates. The Azure equivalent of `tfsec` / `checkov` for Terraform.

`bicepconfig.json` lets you tune linter rules:

```json
{
  "analyzers": {
    "core": {
      "rules": {
        "no-hardcoded-env-urls": { "level": "error" },
        "secure-parameter-default": { "level": "error" },
        "use-recent-api-versions": { "level": "warning" }
      }
    }
  }
}
```

## CI/CD

A workable pipeline:

1. PR opened → `bicep build`, `bicep lint`, PSRule, `az deployment what-if` against the target subscription. What-if posted as a comment.
2. PR reviewed and merged.
3. `main` build → `az stack group create` (or `az deployment group create`) against the environment.
4. Deploy from CI using **OIDC federated identity** (GitHub Actions / Azure DevOps → Entra ID workload identity → no client secret).
5. Promote the same template + different parameter file to higher environments.

Use **environments + approval gates** for prod.

## Common pitfalls

- **API versions matter.** `Microsoft.Storage/storageAccounts@2019-06-01` and `@2024-01-01` have different schemas. Pin recent versions; review Azure release notes when bumping.
- **Diff is approximate.** `what-if` sometimes reports false positives (especially on properties Azure mutates server-side). Read the diff carefully; don't rubber-stamp.
- **Removing a resource doesn't delete it** unless you're using deployment stacks. With plain deployments, a resource you stop managing becomes orphaned.
- **Two deployments at the same scope racing** can cause one to fail. Serialize CI deployments to a given scope.
- **Soft-delete on Key Vault, App Service, Recovery Services Vault** — recreating "the same" resource may collide with the soft-deleted predecessor. Plan deletes carefully.
- **Hardcoded subscription IDs** in cross-scope references — use parameters.
- **Deep nesting of modules** — three levels deep and debugging gets painful.
- **Outputs of secrets** — they get logged; use Key Vault references.
- **Template too large** — there's a 4MB limit on the rendered ARM JSON; very large flat templates hit this. Modularize.
- **Skipping `what-if`** because "it's a tiny change" — that's the change that drops a database.

## Bicep vs Terraform for Azure: the honest take

Pick Bicep when:

- 100% Azure.
- You want first-day support for new Azure resources (Bicep gets them on release; Terraform's `azurerm` provider often lags days to weeks).
- You like having no state file to manage.
- You want native `what-if` and deployment stacks.
- The team has Microsoft-stack DNA and the syntax is friendlier.
- You want PSRule + Azure Policy + Defender for Cloud integration — these speak ARM natively.

Pick Terraform when:

- Multi-cloud or any chance of becoming so.
- You need third-party providers alongside Azure (the AVM ecosystem is good but doesn't replace, e.g., the Datadog provider).
- You're already deep on Terraform and the Azure portion is small.
- You prefer Terraform's state model (some teams do, for the explicit "what is managed" boundary).

You can also mix: **Terraform for the platform** (network, identity, policy) and **Bicep for individual workloads**. It's not unusual.
