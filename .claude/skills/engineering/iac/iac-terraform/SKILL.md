---
name: iac-terraform
description: Use this skill for any Terraform or OpenTofu work — writing or refactoring HCL, designing modules, structuring state, picking a backend, managing variables, importing existing resources, handling drift, debugging plans, writing tests, or setting up Terraform in CI. Trigger on questions involving providers, state files, workspaces, `terraform_remote_state`, `for_each`/`count`, `dynamic` blocks, `moved`/`removed`/`import` blocks, lifecycle rules, the dependency graph, or "convert this CloudFormation/Bicep to Terraform." Also trigger when reviewing a Terraform repo for structure, drift risk, or blast-radius problems.
---

# Terraform / OpenTofu

Terraform's value proposition is simple — declare the desired state, let the tool figure out the diff. The complexity is in everything around that: state, modules, environments, secrets, blast radius, and the dance with drift. This skill is about getting those right. OpenTofu is the open-source fork; almost everything here applies to both, with notes where they diverge.

## Choosing Terraform vs alternatives

Terraform is the right default when:

- You're multi-cloud, or might be.
- You need a mature provider ecosystem (3rd-party SaaS providers — GitHub, Datadog, Cloudflare, etc.).
- The team already knows it.

It's the wrong tool when:

- You're 100% on Azure and the team is .NET-centric — **Bicep** is more pleasant for pure Azure.
- You want to use a real programming language for IaC — **Pulumi** or **CDK for Terraform**, depending on whether you want Terraform's state model under the hood.
- The platform is Kubernetes-centric and you're already in YAML/Helm — **Crossplane** or **Argo CD + Helm** may fit better than wrapping K8s in Terraform.

For everything else, default to Terraform.

**Terraform vs OpenTofu**: OpenTofu is a drop-in fork that's free of the BSL license issues since HashiCorp's relicense. Most providers work on both. OpenTofu added some features Terraform doesn't have (state encryption, early variable evaluation in `for_each`). For new green-field setups, OpenTofu is increasingly the default. For existing estates, you can switch later if needed — files are compatible.

## Project structure that scales

There's no one true layout, but a few rules separate the stable from the painful:

### Rule 1: One state file per blast-radius boundary

Every Terraform "configuration" (the directory you `terraform apply` from) gets its own state file. The state is what determines what gets destroyed if something goes wrong. So:

- **Don't** put prod and dev in the same state.
- **Don't** put networking and applications in the same state — networking changes rarely; apps deploy daily; mixing them slows the apps and adds risk to networking.
- **Do** split by lifecycle: foundation (org, accounts, identity), platform (network, IAM, shared services), workload (per app, per env).

Common layout:

```
infra/
├── modules/                    # Reusable modules (no state)
│   ├── vpc/
│   ├── ecs-service/
│   └── postgres/
├── live/                       # Root configurations (have state)
│   ├── platform/
│   │   ├── network/
│   │   │   ├── prod/
│   │   │   └── nonprod/
│   │   └── iam/
│   │       ├── prod/
│   │       └── nonprod/
│   └── apps/
│       ├── orders/
│       │   ├── prod/
│       │   └── staging/
│       └── inventory/
│           ├── prod/
│           └── staging/
└── README.md
```

Each leaf directory under `live/` is independently `apply`-able. Each has its own backend config and state.

### Rule 2: Workspaces are not environments

`terraform workspace` is a single state with multiple "names." It is **not** suitable for separating prod from dev. Use separate directories with separate backends. Workspaces are useful for ephemeral parallel deploys (e.g., per-PR preview environments) of the same configuration.

### Rule 3: Modules are functions

A module takes inputs (variables), produces outputs, and may have side effects (creating resources). Treat it like a function:

- One responsibility per module.
- Inputs are typed (`type = string`, `type = list(object({...}))`).
- Outputs are explicit and documented.
- No hardcoded environment names inside the module.
- README in every module: what it does, inputs, outputs, example usage.

A good module is small. If yours has 30 variables and 800 lines, it's probably two or three modules.

## Backends and state

The state file is **the truth** Terraform compares against. Lose it or corrupt it and you've inherited a hand-management problem.

### Use a remote backend, always

Local state is for one-person experiments. For anything real:

- **AWS** — S3 backend with state locking via S3 native locks (since Terraform 1.10) or DynamoDB table for older versions; versioning enabled on the bucket.
- **Azure** — `azurerm` backend with a storage account, blob container, and lease-based locking.
- **GCP** — `gcs` backend with object versioning.
- **Terraform Cloud / HCP Terraform** or **Spacelift / env0 / Scalr** — managed runners + state. Worth considering even for small teams; they remove a class of operational pain.

Whatever you pick:

- **Encrypt state at rest.** State contains sensitive values.
- **Restrict who can read state.** It's effectively a credentials cache.
- **Enable versioning** on the bucket. Recovery from "I just typed `terraform destroy` in the wrong directory" depends on it.
- **Backups are not optional.** Versioning gives you recovery from accidental writes.

### State locking

Concurrent `apply` from two people corrupts state. Locking is non-negotiable. Configure it. Test that it works (try a parallel apply in a sandbox; you should see one wait).

### Don't share state across configurations

Need values from one stack in another? Use **outputs + `terraform_remote_state`** (read-only) or, better, **store outputs in a service the consumer can read** (SSM Parameter Store, Azure App Configuration, a Vault path). The latter decouples lifecycles — you can refactor the producer's state without breaking the consumer.

## Variables, locals, outputs

- **Variables** — inputs from outside. Always typed. Always with a description. Defaults only when there's a sane default.
- **Locals** — derived values within a configuration. Use them to centralize naming patterns, tag maps, and computed values.
- **Outputs** — what this configuration exposes to other configurations or to humans. Document them. Mark sensitive ones `sensitive = true`.

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment (e.g., prod, staging, dev)."
  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "Environment must be one of: prod, staging, dev."
  }
}

locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "github.com/example/infra"
  }
}
```

### Where variable values come from

Layered, in increasing precedence:

1. Default in the variable declaration.
2. `terraform.tfvars` and `terraform.tfvars.json` (auto-loaded).
3. `*.auto.tfvars` (auto-loaded, alphabetical order).
4. `-var-file=` flag.
5. `-var=` flag.
6. `TF_VAR_<name>` environment variable.

Convention: per-environment values in `prod.tfvars`, `staging.tfvars`, etc., explicitly passed via `-var-file`. Don't rely on auto-loaded `terraform.tfvars` in a multi-env setup — it's too easy to apply the wrong values.

### Secrets in variables

Don't. Read them from a secret manager **at apply time**, not check them into tfvars:

```hcl
data "aws_secretsmanager_secret_version" "db" {
  secret_id = "prod/orders/db"
}

locals {
  db_password = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["password"]
}
```

Even then, the value lands in state. If your state is sensitive (it is), restrict access tightly. OpenTofu's state encryption is the cleanest answer.

## `count`, `for_each`, and the address-stability problem

The single biggest source of Terraform foot-guns: changing how a resource is addressed in state will cause it to be destroyed and recreated.

```hcl
# Bad: count, ordered list. Removing an element shifts indices.
resource "aws_iam_user" "this" {
  count = length(var.usernames)
  name  = var.usernames[count.index]
}
# Address: aws_iam_user.this[0], [1], [2]
# Remove "alice" from the middle and "bob" gets destroyed-and-recreated.

# Good: for_each over a set. Address is the key, not the index.
resource "aws_iam_user" "this" {
  for_each = toset(var.usernames)
  name     = each.value
}
# Address: aws_iam_user.this["alice"], ["bob"], ["charlie"]
# Removing alice doesn't move bob's address.
```

Use `for_each` over `count` whenever the collection might change. Use `count` only for the binary "create one or zero of this thing" pattern (`count = var.enabled ? 1 : 0`).

## `moved` and `removed` blocks

When you refactor — rename a resource, move it into a module, restructure — use a `moved` block instead of editing state by hand:

```hcl
moved {
  from = aws_instance.web
  to   = module.web.aws_instance.this
}
```

`moved` blocks are declarative state migrations. Plan shows the move, apply executes it, no `terraform state mv` lurking in someone's shell history.

Similarly, **`removed` blocks** (Terraform 1.7+) declaratively remove something from state without destroying it. Useful when transferring ownership of a resource to another configuration.

## `import` blocks

Importing existing resources used to be a CLI dance (`terraform import`) that left no audit trail. Modern Terraform uses **`import` blocks**:

```hcl
import {
  to = aws_s3_bucket.legacy
  id = "my-existing-bucket-name"
}

resource "aws_s3_bucket" "legacy" {
  bucket = "my-existing-bucket-name"
  # ... rest of config matching the existing resource
}
```

`terraform plan` shows what would be imported. `apply` does it. The import block can stay in the config (it's a no-op once imported) or be removed.

For bulk imports from existing infrastructure: **`terraform plan -generate-config-out=imported.tf`** generates HCL skeletons from the live state of the resources in `import` blocks. Saves enormous tedium when adopting Terraform on existing infra.

## `lifecycle`

Resource `lifecycle` blocks change how Terraform treats changes:

```hcl
lifecycle {
  create_before_destroy = true     # for resources that would otherwise have downtime on replace
  prevent_destroy       = true     # for "do not destroy this from Terraform, ever" — bypasses 'destroy'
  ignore_changes        = [tags["LastModified"]]  # tolerate drift on specific attributes
  replace_triggered_by  = [aws_launch_template.this.latest_version]  # force replace on dependency change
  precondition  { ... }            # validate inputs at plan time
  postcondition { ... }            # validate outputs after apply
}
```

`prevent_destroy` is a guardrail, not a security control. It stops `terraform destroy` from succeeding without an edit; it does not stop someone with cloud console access. Use it on stateful production resources (databases, prod KMS keys).

`ignore_changes` is for fields managed outside Terraform (auto-scaling group desired count, manually set tags). Don't use it as "I don't understand why this is drifting, ignore it" — investigate first.

## Providers, versions, lockfiles

Pin everything:

```hcl
terraform {
  required_version = "~> 1.10"  # 1.10+ for `ephemeral` values, native S3 state locking
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"  # AWS provider v6 since late 2025; v5 is in maintenance
    }
  }
}
```

Commit `.terraform.lock.hcl`. It pins exact provider versions and checksums per platform.

`terraform init -upgrade` updates the lockfile within version constraints. `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64` ensures the lock covers every platform your team and CI use; otherwise CI may discover a missing checksum at apply time.

When upgrading a major provider version, do it deliberately: read the upgrade guide, plan in a non-prod environment, watch for resources Terraform wants to recreate due to schema changes.

## Drift

Drift = the live state doesn't match the Terraform state. It happens because:

- Someone clicked in the console.
- Another tool changed something.
- The cloud provider auto-updated something (default tags, automatic backups, etc.).

Strategies:

- **Detect**: `terraform plan` shows drift. Run plan in CI on a schedule against `main`; alert on non-empty plans. Tools like **driftctl** are useful but the built-in plan covers most cases.
- **Tolerate**: `lifecycle { ignore_changes = [...] }` for fields you've decided are owned outside Terraform.
- **Reconcile**: `apply` to drag the world back to declared state. Only safe if the declared state is correct.
- **Adopt**: bring the new resource into Terraform via `import` block.

The deeper fix for drift is process: humans don't change prod cloud resources by hand. Console access in prod is read-only. Changes go through PRs.

## Testing Terraform

Three layers:

1. **Static checks** in CI on every PR:
   - `terraform fmt -check`
   - `terraform validate`
   - `tflint` for provider-aware linting
   - `tfsec` / `checkov` / `terrascan` for security policy
   - `terraform plan` with the change applied to a non-prod backend, posted as a PR comment (Atlantis, Terraform Cloud, Spacelift do this natively).

2. **Module tests** with `terraform test` (built-in, since 1.6) or **Terratest** (Go-based, runs real applies in a real account):
   ```hcl
   # tests/basic.tftest.hcl
   run "valid_inputs" {
     command = plan
     variables {
       name = "test"
     }
     assert {
       condition     = aws_s3_bucket.this.bucket == "test"
       error_message = "Bucket name was not propagated correctly"
     }
   }
   ```
   Use plan-only tests for fast feedback; apply-tests for things that need to actually exist (and then `destroy` after).

3. **Policy as code**:
   - **OPA / Conftest** — generic policy on plan JSON.
   - **Sentinel** — Terraform Cloud's policy language.
   - Common policies: no public S3 buckets, all RDS encrypted, only approved instance types in prod, mandatory tags.

## Multi-environment patterns

Several work; pick one and stick to it.

### Pattern A: Directory per environment

```
live/orders/
├── prod/
│   ├── main.tf
│   └── backend.tf
└── staging/
    ├── main.tf
    └── backend.tf
```

Each has its own backend. `main.tf` calls into shared modules.

- Pro: Crystal clear isolation. Different versions of modules per env if needed.
- Con: Some duplication.

### Pattern B: Shared root module + per-env tfvars

```
live/orders/
├── main.tf       # the actual configuration
├── backend.tf    # placeholder; backend configured at init
├── prod.tfvars
└── staging.tfvars
```

```bash
cd live/orders
terraform init -backend-config=../../backends/prod.hcl
terraform apply -var-file=prod.tfvars
```

- Pro: Less duplication.
- Con: Backend is configured on `init`; easy to point it at the wrong one. Use a wrapper script (or Terragrunt) to enforce the link.

### Pattern C: Terragrunt

Terragrunt wraps Terraform to handle the backend/inputs/dependencies wiring with less duplication. The DRY benefits are real; the cost is another layer of abstraction. For large estates with 10+ environments and shared modules, Terragrunt earns its keep. For smaller setups, plain Terraform plus discipline is enough.

## Terraform in CI/CD

A reasonable pipeline:

1. **PR opened** → `terraform fmt -check`, `validate`, security scan, `plan` against the target environment's state. Plan posted as PR comment.
2. **Reviewer** reads the plan. The plan is the most important review artifact in IaC.
3. **PR merged** → `apply` runs against `main`, against the same state.
4. **Post-apply** → notify channel; archive plan + apply logs.

Auth: use **OIDC** from CI to the cloud provider (no static keys). The CI principal needs a Terraform-deploy role, separate from any human role.

For multi-stage promotion (apply to staging first, then prod after a check), a tool like Atlantis, Terraform Cloud / HCP Terraform, Spacelift, or env0 makes this saner than DIY-ing in YAML. Or use environments + manual approval gates in your CI.

Never run `apply` from a developer laptop against shared environments. Read-only `plan` is fine; writes go through CI.

## Common patterns and idioms

### Standard tag block

```hcl
locals {
  tags = merge(
    var.extra_tags,
    {
      Environment = var.environment
      Service     = var.service_name
      ManagedBy   = "terraform"
      Repo        = "github.com/example/infra"
    }
  )
}
```

In AWS, set `provider "aws" { default_tags { tags = local.tags } }` so all resources inherit them.

### Deriving names

```hcl
locals {
  name_prefix = "${var.service_name}-${var.environment}"
}

resource "aws_s3_bucket" "this" {
  bucket = "${local.name_prefix}-data"
}
```

Don't hand-write each name. Don't include random suffixes unless you need uniqueness across deletes.

### Conditional creation

```hcl
resource "aws_kms_key" "this" {
  count       = var.create_kms_key ? 1 : 0
  description = "..."
}

# When referencing:
kms_key_arn = var.create_kms_key ? aws_kms_key.this[0].arn : var.existing_kms_key_arn
```

The `[0]` is the price of `count`. For more than two-state conditionals, use `for_each` with a set.

### Dynamic blocks

```hcl
resource "aws_security_group" "this" {
  # ...
  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

Keep them shallow. Two levels deep and the file becomes unreadable.

## Anti-patterns

- One state file for the whole company.
- Pinning provider to a major version with `>=` (`version = ">= 5.0.0"`) — eventually a breaking minor breaks you.
- Workspaces for environments.
- Editing state with `terraform state rm` / `terraform state mv` instead of `moved`/`removed` blocks.
- Hand-running `terraform destroy` against prod.
- "We'll add tests later." Tests, tflint, security scans on day one.
- Massive flat root modules (one `main.tf`, 5000 lines, every resource).
- Modules that take 40 variables — they're trying to be too generic.
- Hardcoded account IDs / subscription IDs / project IDs in module source.
- Reading secrets into state via `data` sources without thinking about who can read state.
- `local-exec` provisioners doing real work. Provisioners are the escape hatch of last resort; they aren't idempotent and don't run on subsequent applies.
- Using `null_resource` + `triggers` as a build system. If you need to build, build outside Terraform.
- Letting CI auto-apply with no human in the loop on prod. Even mature teams keep a manual approval gate.
- Apply outputs ignored — drift, errors, time-of-apply warnings unread until the next incident.
