# Taiga MCP Server

This MCP (Model Context Protocol) server provides AI assistants with access to your Taiga project management instance.

## Features

- **Get Current Project**: Retrieve the first/current project from your Taiga instance
- **Get Project Backlog**: Get all backlog items (user stories) for a specific project

## Installation

### Prerequisites

- Python 3.8+
- Taiga instance running

### Setup

```bash
cd /home/rebelloa/mcp-taiga
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## Configuration

The server uses these environment variables:

- `TAIGA_HOST` (default: https://taiga.example.com) - URL of your Taiga instance
- `TAIGA_USERNAME` - Username for authentication
- `TAIGA_PASSWORD` - Password for authentication
- `TAIGA_TOKEN` - Authentication token (used instead of username/password if provided)

## Usage with Claude Desktop

Add this to your Claude Desktop config file:

**On MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**On Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
	"mcpServers": {
		"taiga": {
			"command": "python3",
			"args": ["-m", "taiga_mcp_server"],
			"env": {
				"TAIGA_HOST": "https://taiga.example.com",
				"TAIGA_USERNAME": "your_username",
				"TAIGA_PASSWORD": "your_password"
			}
		}
	}
}
```

Or with a token:

```json
{
	"mcpServers": {
		"taiga": {
			"command": "python3",
			"args": ["-m", "taiga_mcp_server"],
			"env": {
				"TAIGA_HOST": "https://taiga.example.com",
				"TAIGA_TOKEN": "your_auth_token"
			}
		}
	}
}
```

## Usage with GitHub Copilot in VS Code

Add this to your VS Code settings (`.vscode/settings.json` or user settings):

```json
{
	"github.copilot.chat.mcp.servers": {
		"taiga": {
			"command": "python3",
			"args": ["-m", "taiga_mcp_server"],
			"env": {
				"TAIGA_HOST": "https://taiga.example.com",
				"TAIGA_USERNAME": "your_username",
				"TAIGA_PASSWORD": "your_password"
			}
		}
	}
}
```

## Available Tools

### get_current_project

Get the current/first project from your Taiga instance. No parameters required.

Returns:

- Project ID
- Project name
- Project slug
- Description
- Creation date
- Number of members

### get_project_backlog

Get all backlog items (user stories) for a specific project.

Parameters:

- `project_id` (required): The ID of the project
- `limit` (optional, default: 100): Maximum number of items to return

Returns for each backlog item:

- Item reference (e.g., #123)
- Subject/title
- Description
- Status
- Assigned to (if assigned)
- Priority

## Development

### Running the server directly

```bash
TAIGA_HOST=https://taiga.example.com \
TAIGA_USERNAME=user \
TAIGA_PASSWORD=password \
python3 taiga_mcp_server.py
```

### Running tests

```bash
python3 -m pytest
```

## Troubleshooting

### Connection Issues

- Verify `TAIGA_HOST` is correct and accessible
- Check that your credentials (or token) are valid
- Ensure your Taiga instance is running and reachable

### Authentication Errors

- If using token authentication, ensure the token is valid and not expired
- If using username/password, verify both are correct
- Check that your user has appropriate permissions in Taiga

## References

- [Python-Taiga Library](https://github.com/nephila/python-taiga)
- [Taiga API Documentation](https://docs.taiga.io/api/)
- [MCP Specification](https://modelcontextprotocol.io/)
