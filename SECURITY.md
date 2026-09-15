# Security policy

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, customer data, raw
prompts, model output, or exploitation details in a public GitHub issue.

Report vulnerabilities through the repository's private security advisory
channel:

<https://github.com/vnatee/NexoraAI/security/advisories/new>

Include only the information needed to reproduce and assess the issue:

- affected version, branch, or commit;
- affected component and deployment mode;
- prerequisites and reproduction steps;
- expected and observed behavior;
- impact and suggested mitigation, if known; and
- a minimal proof of concept with all secrets and personal data removed.

The maintainers will acknowledge the report, assess severity, coordinate a fix,
and agree on disclosure timing. Do not test against systems or data for which
you do not have explicit authorization.

## Deployment responsibility

NexoraAI supports multiple deployment modes and external providers. Operators
remain responsible for HTTPS, network controls, identity-provider policy,
secret management, backup protection, dependency patching, and least-privilege
access appropriate to their environment. Review the production-readiness and
security guidance before exposing a deployment to users.
