# worksection-mcp

A Model Context Protocol (MCP) server for the [Worksection](https://worksection.com)
project-management API. It speaks MCP over stdio, so any MCP-capable client can drive
Worksection projects, tasks, subtasks, comments, tags, people, time tracking, files,
search and reporting through a consistent set of tools.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- A Worksection account, with either an admin API key or an OAuth2 application

## Install

```bash
git clone https://github.com/atlantdak/worksection-mcp.git
cd worksection-mcp
uv sync
uv run worksection-mcp
```

## Configuration

All settings are read from environment variables (or a local `.env` file — see
`.env.example`). None have a prefix.

| Variable | Default | Purpose |
|---|---|---|
| `AUTH_MODE` | `admin_key` | `admin_key` (no browser flow) or `oauth` (per-user browser login) |
| `WORKSECTION_ACCOUNT` | _(empty)_ | Bare account slug from `https://<slug>.worksection.com` (admin_key mode) |
| `WORKSECTION_API_KEY` | _(empty)_ | Admin API key (admin_key mode) |
| `OAUTH_CLIENT_ID` | _(unset)_ | OAuth2 application client id (oauth mode) |
| `OAUTH_CLIENT_SECRET` | _(unset)_ | OAuth2 application client secret (oauth mode) |
| `OAUTH_REDIRECT_PORT` | `18030` | Loopback port the login listener binds to; `0` picks a free ephemeral port |
| `FERNET_KEY` | _(unset)_ | Key used to encrypt stored OAuth tokens (oauth mode) |
| `ALLOW_DESTRUCTIVE_OPERATIONS` | `false` | Registers `delete_task`, `delete_comment` and `delete_costs` when `true` |
| `FILE_WORKSPACE_DIR` | _(unset)_ | Absolute path to the only directory `upload_file` may read from |
| `STATE_DIR` | `~/.worksection-mcp` | Where tokens, certificates, cache and offloaded responses are stored |
| `REQUEST_TIMEOUT_SECONDS` | `30` | HTTP request timeout |
| `MAX_RETRIES` | `3` | Retry attempts for retryable HTTP failures |
| `RATE_LIMIT_RPS` | `3` | Outbound request rate limit |
| `CACHE_ENABLED` | `true` | Enables the in-process response cache |
| `CACHE_TTL_SECONDS` | `60` | Cache entry lifetime |
| `OFFLOAD_THRESHOLD_BYTES` | `50000` | Responses larger than this are written to disk instead of returned inline |
| `LOG_LEVEL` | `INFO` | Standard Python logging level |

## Authentication — two modes

### Admin API key (recommended for a single user)

Find your admin API key in Worksection under account settings, then set:

```bash
AUTH_MODE=admin_key
WORKSECTION_ACCOUNT=your-account
WORKSECTION_API_KEY=your-key
```

There is no browser step at all in this mode. The server authenticates every request
directly with the key.

### OAuth2 (per-user)

Register an OAuth2 application in Worksection, then set:

```bash
AUTH_MODE=oauth
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
FERNET_KEY=your-generated-key
```

Generate the Fernet key with:

```bash
uv run python -m worksection_mcp.auth.token_store
```

Then call the `worksection_login` tool from your MCP client to complete the one-time
login. A short-lived HTTPS listener starts on `127.0.0.1:18030` (configurable via
`OAUTH_REDIRECT_PORT`) to receive the OAuth2 redirect. Its certificate is self-signed,
so your browser will show a one-time warning before you can continue. Once
authenticated, tokens are stored Fernet-encrypted with `0600` permissions under
`~/.worksection-mcp/` (or `STATE_DIR`), and refreshed automatically as needed —
no further browser interaction is required.

**Two-factor authentication:** if your Worksection account has two-factor
authentication enabled, it affects only the one-time browser login step of OAuth2
mode — you complete the 2FA prompt in the browser exactly as you normally would.
Nothing in this server touches, stores or bypasses your second factor. For a fully
non-interactive setup, use admin API key mode, which needs no browser login at all.

## Safety: destructive operations

`ALLOW_DESTRUCTIVE_OPERATIONS` defaults to `false`. While it is `false`, the
destructive tools — `delete_task`, `delete_comment` and `delete_costs` — are not even
listed to the connected client; they simply don't exist as far as the client can see.
When it is set to `true`, they become available, and each additionally requires the
caller to pass `confirm: true` before it will run. This two-layer guard exists
specifically to protect against prompt-injection-driven data loss: a client has to be
deliberately configured to allow destructive actions, and every individual call has to
opt in explicitly.

## Safety: file access

No tool accepts an arbitrary filesystem path. `upload_file` takes either inline
base64 content or the name of a file inside the configured `FILE_WORKSPACE_DIR` —
any path outside that directory, including via traversal or symlinks, is rejected.
`download_file` returns attachment content inline as base64, capped at a maximum
size, and never writes anything to disk.

## Large responses

Responses larger than `OFFLOAD_THRESHOLD_BYTES` are written to disk instead of
returned inline. The tool call instead gets back a summary containing a
`worksection://offload/...` resource URI. The full content can be read back in
bounded chunks with the `read_offloaded_response` tool, or fetched directly as an
MCP resource.

## Client configuration

Example configuration for an MCP client, using admin API key mode:

```json
{
  "mcpServers": {
    "worksection": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/worksection-mcp", "run", "worksection-mcp"],
      "env": {
        "AUTH_MODE": "admin_key",
        "WORKSECTION_ACCOUNT": "your-account",
        "WORKSECTION_API_KEY": "your-key"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|---|---|
| `activate_project` | Restore an archived project to active status. |
| `add_costs` | Log time (and optionally money) against a task. |
| `add_task_tags` | Add tags to a task, keeping the tags it already has. |
| `archive_project` | Close a project and move it to the archive. Reversible with activate_project. |
| `auth_status` | Report the active authentication mode and, in oauth mode, whether the server has stored login credentials. This reflects whether credentials are on file, not whether the access token happens to be fresh right now - an expired token is refreshed automatically as long as a refresh token is stored. Never returns token values. |
| `complete_task` | Mark a task as done, closing it in Worksection. |
| `create_project` | Create a project, optionally with a manager, description and dates. |
| `create_subtask` | Create a subtask under an existing task. |
| `create_task` | Create a task in a project, optionally assigned, dated and prioritised. |
| `delete_comment` (destructive) | Permanently delete a comment. Only available when ALLOW_DESTRUCTIVE_OPERATIONS=true, and requires confirm=true. |
| `delete_costs` (destructive) | Permanently delete a time entry. Only available when ALLOW_DESTRUCTIVE_OPERATIONS=true, and requires confirm=true. |
| `delete_task` (destructive) | Permanently delete a task. Only available when ALLOW_DESTRUCTIVE_OPERATIONS=true, and requires confirm=true. |
| `download_file` | Fetch one attachment and return it inline as base64. Refuses files larger than max_bytes instead of writing anywhere on disk. |
| `get_activity_log` | List recent account or project activity events over a date range. |
| `get_all_tasks` | List tasks across every project the account can see. Status and assignee filters are re-applied locally because the API's own filtering is unreliable for some combinations. |
| `get_comments` | List the comments on a task, oldest first. |
| `get_contacts` | List external contacts (clients) registered in the account. |
| `get_costs` | List logged time and cost entries, optionally scoped to a project or task, a date range, or one person. |
| `get_member` | Find one account member by email or id. |
| `get_member_groups` | List the member groups (teams) configured for the account. |
| `get_members` | List the people in the account with their ids, emails and roles. |
| `get_overdue_tasks` | List open tasks whose due date has passed, most overdue first. |
| `get_project` | Fetch a single project by id, including its status and dates. |
| `get_project_groups` | List the task groups (folders) configured inside a project. |
| `get_project_members` | List the people who have access to one project. |
| `get_project_stats` | Count a project's tasks by status and priority bucket. |
| `get_projects` | List projects visible to the authenticated account. |
| `get_running_timers` | List every timer currently running in the account. |
| `get_subtasks` | List the subtasks of a task. |
| `get_tags` | List the tag groups and tags configured for the account. |
| `get_task` | Fetch one task, optionally with its description text, files and subtasks. |
| `get_task_files` | List the files attached to a task, with their ids, names and sizes. |
| `get_task_tags` | List the tag names currently applied to a task. |
| `get_tasks` | List tasks inside one project, with local status and assignee filtering. |
| `get_tasks_by_priority` | Group tasks into high, normal and low priority buckets. |
| `get_tasks_by_status` | Group tasks by status, with counts and the tasks in each group. |
| `get_team_workload` | Group open and completed tasks by assignee across the account or one project. |
| `get_time_report` | Summarise logged time and money for an account, project or task over a date range, totalled per person. |
| `health_check` | Verify that the configured credentials can reach the Worksection API. Returns a status report instead of raising when the call fails. |
| `list_workspace_files` | List the files available in the configured workspace directory. Returns an empty list when FILE_WORKSPACE_DIR is not set. |
| `post_comment` | Add a comment to a task. |
| `read_offloaded_response` | Read one bounded chunk of a response that was too large to return inline. Use the resource_uri and total_chunks from the offload summary. |
| `reopen_task` | Reopen a previously completed task. |
| `search_tasks` | Search tasks by text, status, assignee, priority and due date, across the account or inside one project. Filtering is applied locally for reliability. |
| `set_task_tags` | Replace every tag on a task with the given list. |
| `start_timer` | Start a running timer on a task. |
| `stop_timer` | Stop the running timer on a task and store the elapsed time. |
| `update_comment` | Replace the text of an existing comment. |
| `update_costs` | Change the hours, comment, date or amount of an existing time entry. |
| `update_project` | Change a project's title, description, manager or dates. |
| `update_subtask` | Change the title, description, assignee, due date or priority of a subtask. |
| `update_task` | Change the title, description, assignee, dates or priority of a task. |
| `upload_file` | Attach a file to a task. Provide the content inline as base64, or name a file inside the configured workspace directory. Arbitrary filesystem paths are rejected. |
| `validate_configuration` | Report the server's effective configuration and the result of every local startup check. Contacts no external service and never returns secret values. |
| `worksection_login` | Start the OAuth2 browser login. Opens the authorization page, waits for the loopback redirect, and stores the resulting tokens encrypted on disk. Has nothing to do in admin_key mode and reports that instead of failing. |
| `worksection_logout` | Delete the stored OAuth tokens from disk. Only local credentials are removed; nothing in Worksection itself is affected. |

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
uv run python scripts/import_sweep.py
uv run python scripts/preflight.py
```

## API limitations

Known quirks and undocumented behaviour of the upstream Worksection API, and how
each was verified, are tracked in [`docs/API-LIMITATIONS.md`](docs/API-LIMITATIONS.md).

## Security

See [`SECURITY.md`](SECURITY.md) for the project's security posture and how to
report a vulnerability.

## Acknowledgments

This project's design was informed by ideas from a few existing community
Worksection MCP servers, including
[novgorodskii/worksection-mcp-server](https://github.com/novgorodskii/worksection-mcp-server),
[PavloPopravkin/worksection-mcp](https://github.com/PavloPopravkin/worksection-mcp), and
[pbv7/worksection-mcp](https://github.com/pbv7/worksection-mcp). Thanks to their authors
for publishing their work. This codebase is an independent, from-scratch
implementation, not a fork of any of them.

## Licence

MIT
