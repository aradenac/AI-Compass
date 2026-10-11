# AI Compass — Development and LAN operational profiles

**Engineering reference:** development and local/LAN installation operate on the same Django/PostgreSQL/Caddy application with explicit origin, cookie, permission, audit, and recovery safeguards. Public ingress must not use development defaults.

## Environment boundaries

| Environment | Network exposure | Security contract |
| --- | --- | --- |
| Development | Loopback / disposable fixture | HTTP only on loopback; isolated credentials; Server remains separate from offline Demo. |
| Private LAN | Controlled private network | Explicit allowed hosts/origins, authenticated operation, private backup controls, HTTPS/private ingress and appropriate cookie security for deployed environment. |

Use [local installation](local-installation.md), [release readiness](release-readiness.md), and [platform architecture](platform-architecture-and-data-governance.md) for executable configuration, authentication, data recovery and operational acceptance.