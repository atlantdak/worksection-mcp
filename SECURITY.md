# Security policy

## What this is

`worksection-mcp` is a local Model Context Protocol server. It speaks stdio
to a single client running on the same machine — it is not a network
service and exposes no HTTP endpoint of its own. The one exception is a
short-lived, loopback-only listener used during interactive OAuth login
(see below).

This document describes the threat model the server was designed against
and the mitigations built into the code. It is based on design review and
the project's own test suite, not on a formal security audit or any
real-world attack. The server has not been run against live production
credentials or a production Worksection account.

## Trust boundary

The MCP client — and therefore any content it feeds to the model driving
it — is treated as **untrusted input**. Tool arguments can be influenced by
prompt injection: text pulled from a task, comment, or file could contain
instructions trying to make the model call a tool it shouldn't, with
arguments it shouldn't use. Every mitigation below follows from that
assumption; nothing here relies on the client or the model behaving well.

## Credentials

- **Admin key mode** keeps the API key in the process environment and
  never places it in a URL query string; it is only used to sign each
  request. Signed values are passed to `httpx` as parameters, so they are
  percent-encoded rather than concatenated into a URL.
- **OAuth mode** stores tokens Fernet-encrypted at rest. The token file is
  written `0600` inside a `0700` directory, using a restrictive umask for
  every intermediate write so no partial state is ever world- or
  group-readable.
- Secrets are never intentionally logged. Logging goes to stderr through a
  filter that redacts known secret values as a backstop, not as the
  primary control — call sites are expected not to log settings objects or
  raw credentials in the first place.

## Destructive operations

Tools that permanently delete data (for example, deleting a task, a
comment, or a cost entry) are:

- **off by default** — gated behind `ALLOW_DESTRUCTIVE_OPERATIONS=true`;
- **hidden from `list_tools`** when disabled, so a client never even sees
  them as an option;
- **re-checked at call time**, not just at startup, so the flag can't be
  bypassed by a stale tool list; and
- **individually confirmed** — each destructive call still requires an
  explicit `confirm: true` argument even when the flag is on.

This is the primary defense against a prompt-injection attempt that tries
to talk the model into deleting data: by default the tool doesn't exist,
and even when enabled it takes a second, explicit signal to act.

## Filesystem

No tool accepts an arbitrary path. File access is limited to two shapes:

- **Uploads** are either inline base64 content, or a name resolved
  strictly inside `FILE_WORKSPACE_DIR`. Resolution rejects absolute paths,
  any `..` segment, symlinks, and anything that isn't a regular file
  inside that directory.
- **Downloads** return file content inline as bytes, capped at a fixed
  size limit, and never write to disk on the caller's behalf.

There is no code path that lets a tool argument name a file outside the
configured workspace.

## Network

- Every request value passed to the Worksection API goes through `httpx`'s
  own parameter encoding; no query string is ever built by string
  concatenation.
- The OAuth callback listener — the only network socket this server opens
  — binds to `127.0.0.1` only, for the duration of a single login attempt,
  using a locally generated self-signed certificate. It is not reachable
  from outside the machine and is not left running once the login
  completes or times out.

## Known limitations

- The server is single-user per process: whatever the configured
  credentials can see, any tool call can see. Scope the API key or OAuth
  grant accordingly — this server does not add its own authorization on
  top of the Worksection account's own permissions.
- The self-signed certificate used by the OAuth callback listener will
  produce a browser warning during login. This is expected: the
  certificate exists only to satisfy a redirect URI that requires HTTPS,
  not to be trusted by anything else.
- There is no sandboxing of the MCP client itself. This server defends its
  own boundaries (filesystem, network, destructive operations) but assumes
  the operating system is otherwise trusted.

## Design history

Part of the motivation for these boundaries came from reviewing other
publicly available Worksection MCP server implementations while planning
this one. That review turned up, in various combinations: search or
report parameters built into request URLs by string concatenation instead
of proper encoding; file-download tools that accepted a caller-supplied
path with no containment check; access tokens written to disk in plain
text; and a local callback server bound to all interfaces rather than the
loopback address. None of that code is reused here — it's mentioned only
because it shaped which mitigations above were treated as mandatory rather
than optional.

## Reporting a vulnerability

If you find a security issue, please report it privately using
[GitHub's security advisory form](https://github.com/atlantdak/worksection-mcp/security/advisories/new)
on this repository rather than opening a public issue. Include enough
detail to reproduce the problem. This is a small, unfunded open-source
project maintained on a best-effort basis; there is no guaranteed response
time, but reports will be acknowledged and addressed as soon as
reasonably possible.
