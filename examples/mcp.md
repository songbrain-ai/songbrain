# Songbrain MCP server

Songbrain runs a remote [Model Context Protocol](https://modelcontextprotocol.io) server:

```
https://api.songbrain.ai/mcp
```

- Transport: streamable HTTP (stateless JSON-RPC over `POST`).
- Without a key you get the example tools. That is enough to see what the API returns.
- With a key (`Authorization: Bearer sb_live_…` or `X-API-Key: sb_live_…`) you can analyse your own songs.
- Get a key at https://app.songbrain.ai/developers. 5 songs a month are free.

## Tools

| Tool | Key | What it does |
|---|---|---|
| `list_example_songs` | no | Example analyses you can open |
| `get_example_analysis` | no | An example document (summary view by default) |
| `get_example_shot_plan` | no | An example story and shot plan, with prompts |
| `get_pricing` | no | Prices and limits |
| `analyze_song` | yes | Start an analysis from a public audio URL |
| `get_song` | yes | Status, then the document |
| `get_account` | yes | Free songs left, credits |

Over MCP, songs come from a public URL (`analyze_song`). To upload local files, use the API or an SDK.

## Claude Code

Without a key:

```bash
claude mcp add --transport http songbrain https://api.songbrain.ai/mcp
```

With a key:

```bash
claude mcp add --transport http songbrain https://api.songbrain.ai/mcp \
  --header "Authorization: Bearer sb_live_…"
```

Add `--scope user` to use it in every project. Check it with `claude mcp list`, or `/mcp` inside a session.

## Claude Desktop

Without a key: open **Settings → Connectors → Add custom connector**, name it `Songbrain` and paste `https://api.songbrain.ai/mcp`.

With a key: custom connectors can't send your own headers, so use the [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge (needs Node.js). Edit `claude_desktop_config.json` (**Settings → Developer → Edit Config**):

```json
{
  "mcpServers": {
    "songbrain": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://api.songbrain.ai/mcp",
        "--header",
        "Authorization:${SONGBRAIN_AUTH}"
      ],
      "env": {
        "SONGBRAIN_AUTH": "Bearer sb_live_…"
      }
    }
  }
}
```

The header value sits in `env` because some systems split arguments that contain spaces. Restart Claude Desktop afterwards.

## Cursor

Edit `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

Without a key:

```json
{
  "mcpServers": {
    "songbrain": {
      "url": "https://api.songbrain.ai/mcp"
    }
  }
}
```

With a key:

```json
{
  "mcpServers": {
    "songbrain": {
      "url": "https://api.songbrain.ai/mcp",
      "headers": {
        "Authorization": "Bearer sb_live_…"
      }
    }
  }
}
```

Don't commit a project file that contains your key.

## Any other client

Point the client at `https://api.songbrain.ai/mcp` with the streamable HTTP transport. Send the key as a header if the client supports headers. If it only speaks stdio, use `npx -y mcp-remote https://api.songbrain.ai/mcp` as the command.

Test the server from a shell:

```bash
curl -s https://api.songbrain.ai/mcp \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Things to ask

- "Show me the shot plan of the Songbrain example old-truck-home."
- "Analyse https://example.com/my-song.mp3 and list the scenes with their prompts."
- "Which part of this song is the best 15 seconds for a short video, and why?"
