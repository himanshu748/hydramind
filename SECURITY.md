# Security policy

## Supported versions

HydraMind is pre-1.0. Security fixes land on `main` and in the latest release.

| Version | Supported |
|---|---|
| `main` / latest `0.x` release | ✅ |
| Older releases | ❌ |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public issues, pull requests,
or discussions.**

Instead, open an issue titled **"Security contact request"** that contains no
technical details, or message the maintainer, [@himanshu748](https://github.com/himanshu748),
directly. The maintainer will arrange a private channel for the full report.

Once a private channel is set up, please share:

- A description of the issue and its impact
- Steps to reproduce, or a proof of concept
- Affected version or commit, Python version, and HydraDB commit
- Any suggested fix or mitigation

You should get an acknowledgement within 7 days. We will keep you informed while we
work on a fix and credit you in the release notes unless you prefer otherwise. Please
give us a reasonable chance to release a fix before public disclosure.

## Deployment guidance

HydraMind is designed for **local, single-user** use by default. Keep these
boundaries in mind:

- **Scope is not authentication.** The `scope` parameter partitions data and guards
  queries, but it does not authenticate callers or enforce tenant authorization.
- **Bind to loopback.** The MCP HTTP server (`HYDRAMIND_MCP_HOST`) and dashboard
  (`HYDRAMIND_UI_HOST`) default to `127.0.0.1`. Expose them only behind an
  authenticated gateway.
- **Protect the token.** Supply `HYDRAMIND_TOKEN` through your host's secret
  management. Never commit it or a populated `.env` file.
- **Memory content is untrusted input.** Agents may store text that later reaches
  another agent's context. Treat recalled memories as data, not instructions.
