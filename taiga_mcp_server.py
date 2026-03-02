#!/usr/bin/env python3
"""
Taiga MCP Server

Provides access to Taiga project management instance through MCP tools.
Allows retrieval of projects and backlog items.
"""

import json
import logging
import os
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import CallToolResult, ServerCapabilities, TextContent, Tool
except ImportError:
    print("Error: MCP SDK not installed. Please install it with:", file=sys.stderr)
    print("  pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from taiga import TaigaAPI
    from taiga.exceptions import TaigaRestException
except ImportError:
    print("Error: python-taiga not installed. Please install it with:", file=sys.stderr)
    print("  pip install python-taiga", file=sys.stderr)
    sys.exit(1)

# Configure logging to file only (don't use stderr since MCP uses it for protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/taiga_mcp_server.log"),
    ],
)
logger = logging.getLogger(__name__)

# Environment variables for Taiga configuration
TAIGA_HOST = os.getenv("TAIGA_HOST", "https://taiga.example.com")
TAIGA_USERNAME = os.getenv("TAIGA_USERNAME", "")
TAIGA_PASSWORD = os.getenv("TAIGA_PASSWORD", "")
TAIGA_TOKEN = os.getenv("TAIGA_TOKEN", "")
DEFAULT_PROJECT_ID = int(os.getenv("DEFAULT_PROJECT_ID", "1"))


class TaigaMCPServer:
    """MCP Server for Taiga integration"""

    def __init__(self):
        self.server = Server("taiga-mcp-server")
        self.api = None
        self._api_initialized = False
        self.setup_handlers()

    def initialize_api(self) -> bool:
        """Initialize Taiga API connection"""
        try:
            if self._api_initialized and self.api is not None:
                return True

            self.api = TaigaAPI(host=TAIGA_HOST)

            # Authenticate with token or username/password
            if TAIGA_TOKEN:
                self.api.token = TAIGA_TOKEN
                self.api._init_resources()
                self._api_initialized = True
            elif TAIGA_USERNAME and TAIGA_PASSWORD:
                self.api.auth(TAIGA_USERNAME, TAIGA_PASSWORD)
                self._api_initialized = True
            else:
                logger.error("No authentication credentials provided")
                logger.error(
                    "Set TAIGA_TOKEN or both TAIGA_USERNAME and TAIGA_PASSWORD"
                )
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to initialize Taiga API: {str(e)}")
            self._api_initialized = False
            return False

    def setup_handlers(self):
        """Setup MCP request handlers"""

        @self.server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="get_current_project",
                    description="Get the current/first project from Taiga",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="get_user_stories",
                    description="Get user stories for a specific project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of items to return (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": ["project_id"],
                    },
                ),
                Tool(
                    name="get_issues",
                    description="Get issues for a specific project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of items to return (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": ["project_id"],
                    },
                ),
                Tool(
                    name="get_backlog",
                    description="Get the complete backlog (user stories + issues) for a specific project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of items to return (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": ["project_id"],
                    },
                ),
                Tool(
                    name="get_project_backlog",
                    description="(Deprecated: use get_user_stories or get_backlog) Get the backlog (user stories) for a specific project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of items to return (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": ["project_id"],
                    },
                ),
                Tool(
                    name="get_user_story_details",
                    description="Get full details about a specific user story",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "story_id": {
                                "type": "integer",
                                "description": "The ID of the user story",
                            },
                        },
                        "required": ["project_id", "story_id"],
                    },
                ),
                Tool(
                    name="get_issue_details",
                    description="Get full details about a specific issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "issue_id": {
                                "type": "integer",
                                "description": "The ID of the issue",
                            },
                        },
                        "required": ["project_id", "issue_id"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Handle tool calls"""
            try:
                if not self.initialize_api():
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text="Error: Failed to initialize Taiga API connection. Check configuration and logs.",
                            )
                        ],
                        isError=True,
                    )

                if name == "get_current_project":
                    return self.handle_get_current_project()
                elif name == "get_user_stories":
                    return self.handle_get_user_stories(arguments)
                elif name == "get_issues":
                    return self.handle_get_issues(arguments)
                elif name == "get_backlog":
                    return self.handle_get_backlog(arguments)
                elif name == "get_project_backlog":
                    # Deprecated: redirect to get_user_stories
                    return self.handle_get_user_stories(arguments)
                elif name == "get_user_story_details":
                    return self.handle_get_user_story_details(arguments)
                elif name == "get_issue_details":
                    return self.handle_get_issue_details(arguments)
                else:
                    return CallToolResult(
                        content=[
                            TextContent(type="text", text=f"Unknown tool: {name}")
                        ],
                        isError=True,
                    )
            except Exception as e:
                logger.error(f"Error calling tool {name}: {str(e)}", exc_info=True)
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")],
                    isError=True,
                )

    def handle_get_current_project(self) -> CallToolResult:
        """Get the default project from environment variable or first project"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            # Try to get the project by DEFAULT_PROJECT_ID
            try:
                project = self.api.projects.get(DEFAULT_PROJECT_ID)
            except TaigaRestException:
                # Fall back to first project if default doesn't exist
                projects = self.api.projects.list()
                if not projects:
                    return CallToolResult(
                        content=[TextContent(type="text", text="No projects found")],
                    )
                project = projects[0]

            project_info = {
                "id": project.id,
                "name": project.name,
                "slug": project.slug,
                "description": project.description or "",
                "created_date": (
                    str(project.created_date)
                    if hasattr(project, "created_date")
                    else None
                ),
                "members_count": (
                    len(project.members) if hasattr(project, "members") else 0
                ),
            }

            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Current Project:\n\n{self._format_project(project_info)}",
                    )
                ],
            )
        except TaigaRestException as e:
            logger.error(f"Taiga API error: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Taiga API Error: {str(e)}")],
                isError=True,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    def handle_get_user_stories(self, arguments: dict) -> CallToolResult:
        """Get user stories for a specific project"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            project_id = arguments.get("project_id")
            limit = arguments.get("limit", 100)

            if not project_id:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="Error: project_id is required")
                    ],
                    isError=True,
                )

            # Get user stories (backlog items)
            user_stories = self.api.user_stories.list(
                project=project_id, status__is_closed=False
            )

            # Limit results
            if limit and len(user_stories) > limit:
                user_stories = user_stories[:limit]

            if not user_stories:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No user stories found for project {project_id}",
                        )
                    ],
                )

            # Format user stories
            items = []
            for story in user_stories:
                assigned_to = None
                if (
                    hasattr(story, "assigned_to_extra_info")
                    and story.assigned_to_extra_info
                ):
                    assigned_to = story.assigned_to_extra_info.get("full_name")

                # Get status name from status_extra_info
                status_name = None
                if hasattr(story, "status_extra_info") and story.status_extra_info:
                    status_name = story.status_extra_info.get("name")

                item = {
                    "id": story.id,
                    "ref": story.ref,
                    "subject": story.subject,
                    "blocked_note": getattr(story, "blocked_note", "") or "",
                    "status": status_name or getattr(story, "status", None),
                    "assigned_to": assigned_to,
                    "tags": getattr(story, "tags", []),
                }
                items.append(item)

            # Format output
            output = f"User Stories for project {project_id}: {len(items)} items\n\n"
            for idx, item in enumerate(items, 1):
                output += f"{idx}. [#{item['ref']}] {item['subject']}\n"
                if item["blocked_note"]:
                    blocked_preview = item["blocked_note"][:100]
                    if len(item["blocked_note"]) > 100:
                        blocked_preview += "..."
                    output += f"   Blocked: {blocked_preview}\n"
                if item["assigned_to"]:
                    output += f"   Assigned to: {item['assigned_to']}\n"
                if item["status"]:
                    output += f"   Status: {item['status']}\n"
                if item["tags"]:
                    output += f"   Tags: {', '.join(item['tags'])}\n"
                output += "\n"

            return CallToolResult(
                content=[TextContent(type="text", text=output)],
            )
        except TaigaRestException as e:
            logger.error(f"Taiga API error: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Taiga API Error: {str(e)}")],
                isError=True,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    def handle_get_issues(self, arguments: dict) -> CallToolResult:
        """Get issues for a specific project"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            project_id = arguments.get("project_id")
            limit = arguments.get("limit", 100)

            if not project_id:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="Error: project_id is required")
                    ],
                    isError=True,
                )

            # Get issues
            issues = self.api.issues.list(project=project_id)

            # Limit results
            if limit and len(issues) > limit:
                issues = issues[:limit]

            if not issues:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No issues found for project {project_id}",
                        )
                    ],
                )

            # Format issues
            items = []
            for issue in issues:
                assigned_to = None
                if (
                    hasattr(issue, "assigned_to_extra_info")
                    and issue.assigned_to_extra_info
                ):
                    assigned_to = issue.assigned_to_extra_info.get("full_name")

                # Get status name from status_extra_info
                status_name = None
                if hasattr(issue, "status_extra_info") and issue.status_extra_info:
                    status_name = issue.status_extra_info.get("name")

                # Get priority name from priority_extra_info
                priority_name = None
                if hasattr(issue, "priority_extra_info") and issue.priority_extra_info:
                    priority_name = issue.priority_extra_info.get("name")

                item = {
                    "id": issue.id,
                    "ref": issue.ref,
                    "subject": issue.subject,
                    "description": getattr(issue, "description", "") or "",
                    "status": status_name or getattr(issue, "status", None),
                    "priority": priority_name or getattr(issue, "priority", None),
                    "assigned_to": assigned_to,
                    "tags": getattr(issue, "tags", []),
                }
                items.append(item)

            # Format output
            output = f"Issues for project {project_id}: {len(items)} items\n\n"
            for idx, item in enumerate(items, 1):
                output += f"{idx}. [#{item['ref']}] {item['subject']}\n"
                if item["assigned_to"]:
                    output += f"   Assigned to: {item['assigned_to']}\n"
                if item["status"]:
                    output += f"   Status: {item['status']}\n"
                if item["priority"]:
                    output += f"   Priority: {item['priority']}\n"
                if item["tags"]:
                    output += f"   Tags: {', '.join(item['tags'])}\n"
                output += "\n"

            return CallToolResult(
                content=[TextContent(type="text", text=output)],
            )
        except TaigaRestException as e:
            logger.error(f"Taiga API error: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Taiga API Error: {str(e)}")],
                isError=True,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    def handle_get_backlog(self, arguments: dict) -> CallToolResult:
        """Get complete backlog (user stories + issues) for a project"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            project_id = arguments.get("project_id")
            limit = arguments.get("limit", 100)

            if not project_id:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="Error: project_id is required")
                    ],
                    isError=True,
                )

            # Get user stories
            user_stories = self.api.user_stories.list(
                project=project_id, status__is_closed=False
            )

            # Get issues
            issues = self.api.issues.list(project=project_id)

            # Format items
            items = []

            # Add user stories
            for story in user_stories:
                assigned_to = None
                if (
                    hasattr(story, "assigned_to_extra_info")
                    and story.assigned_to_extra_info
                ):
                    assigned_to = story.assigned_to_extra_info.get("full_name")

                status_name = None
                if hasattr(story, "status_extra_info") and story.status_extra_info:
                    status_name = story.status_extra_info.get("name")

                items.append(
                    {
                        "type": "user_story",
                        "id": story.id,
                        "ref": story.ref,
                        "subject": story.subject,
                        "status": status_name or getattr(story, "status", None),
                        "assigned_to": assigned_to,
                        "tags": getattr(story, "tags", []),
                    }
                )

            # Add issues
            for issue in issues:
                assigned_to = None
                if (
                    hasattr(issue, "assigned_to_extra_info")
                    and issue.assigned_to_extra_info
                ):
                    assigned_to = issue.assigned_to_extra_info.get("full_name")

                status_name = None
                if hasattr(issue, "status_extra_info") and issue.status_extra_info:
                    status_name = issue.status_extra_info.get("name")

                priority_name = None
                if hasattr(issue, "priority_extra_info") and issue.priority_extra_info:
                    priority_name = issue.priority_extra_info.get("name")

                items.append(
                    {
                        "type": "issue",
                        "id": issue.id,
                        "ref": issue.ref,
                        "subject": issue.subject,
                        "status": status_name or getattr(issue, "status", None),
                        "priority": priority_name or getattr(issue, "priority", None),
                        "assigned_to": assigned_to,
                        "tags": getattr(issue, "tags", []),
                    }
                )

            # Limit results
            if limit and len(items) > limit:
                items = items[:limit]

            if not items:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No backlog items found for project {project_id}",
                        )
                    ],
                )

            # Format output
            output = f"Backlog for project {project_id}: {len(items)} items\n"
            output += (
                f"  {sum(1 for i in items if i['type'] == 'user_story')} user stories, "
            )
            output += f"{sum(1 for i in items if i['type'] == 'issue')} issues\n\n"

            for idx, item in enumerate(items, 1):
                item_type = "US" if item["type"] == "user_story" else "ISSUE"
                output += f"{idx}. [{item_type} #{item['ref']}] {item['subject']}\n"
                if item["assigned_to"]:
                    output += f"   Assigned to: {item['assigned_to']}\n"
                if item["status"]:
                    output += f"   Status: {item['status']}\n"
                if item.get("priority"):
                    output += f"   Priority: {item['priority']}\n"
                if item["tags"]:
                    tags_str = ", ".join(
                        tag if isinstance(tag, str) else str(tag)
                        for tag in item["tags"]
                    )
                    output += f"   Tags: {tags_str}\n"
                output += "\n"

            return CallToolResult(
                content=[TextContent(type="text", text=output)],
            )
        except TaigaRestException as e:
            logger.error(f"Taiga API error: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Taiga API Error: {str(e)}")],
                isError=True,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    def handle_get_project_backlog(self, arguments: dict) -> CallToolResult:
        """(Deprecated) Get backlog for a specific project - redirects to get_user_stories"""
        return self.handle_get_user_stories(arguments)

    def handle_get_user_story_details(self, arguments: dict) -> CallToolResult:
        """Get full details about a specific user story"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            project_id = arguments.get("project_id")
            story_id = arguments.get("story_id")

            if not project_id or not story_id:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="Error: project_id and story_id are required",
                        )
                    ],
                    isError=True,
                )

            # Get the specific user story
            story = self.api.user_stories.get(story_id)

            if not story:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"User story {story_id} not found in project {project_id}",
                        )
                    ],
                    isError=True,
                )

            # Format detailed information
            output = f"User Story Details - #{story.ref}\n"
            output += "=" * 60 + "\n\n"
            output += f"Subject: {story.subject}\n"

            if hasattr(story, "description") and story.description:
                output += f"\nDescription:\n{story.description}\n"

            # Status
            status_name = None
            if hasattr(story, "status_extra_info") and story.status_extra_info:
                status_name = story.status_extra_info.get("name")
            output += f"\nStatus: {status_name or getattr(story, 'status', 'N/A')}\n"

            # Assigned to
            assigned_to = None
            if (
                hasattr(story, "assigned_to_extra_info")
                and story.assigned_to_extra_info
            ):
                assigned_to = story.assigned_to_extra_info.get("full_name")
            if assigned_to:
                output += f"Assigned to: {assigned_to}\n"

            # Blocked
            if hasattr(story, "blocked_note") and story.blocked_note:
                output += f"\nBlocked: {story.blocked_note}\n"

            # Due date
            if hasattr(story, "due_date") and story.due_date:
                output += f"Due date: {story.due_date}\n"

            # Story points
            if hasattr(story, "points") and story.points:
                output += f"Story points: {story.points}\n"

            # Tags
            tags = getattr(story, "tags", [])
            if tags:
                tags_str = ", ".join(
                    tag if isinstance(tag, str) else str(tag) for tag in tags
                )
                output += f"Tags: {tags_str}\n"

            # Related user stories
            if hasattr(story, "related_user_stories") and story.related_user_stories:
                output += f"\nRelated user stories: {', '.join(map(str, story.related_user_stories))}\n"

            # Created/Modified
            if hasattr(story, "created_date") and story.created_date:
                output += f"\nCreated: {story.created_date}\n"
            if hasattr(story, "modified_date") and story.modified_date:
                output += f"Modified: {story.modified_date}\n"

            return CallToolResult(
                content=[TextContent(type="text", text=output)],
            )
        except TaigaRestException as e:
            logger.error(f"Taiga API error: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Taiga API Error: {str(e)}")],
                isError=True,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    def handle_get_issue_details(self, arguments: dict) -> CallToolResult:
        """Get full details about a specific issue"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            project_id = arguments.get("project_id")
            issue_id = arguments.get("issue_id")

            if not project_id or not issue_id:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="Error: project_id and issue_id are required",
                        )
                    ],
                    isError=True,
                )

            # Get the specific issue
            issue = self.api.issues.get(issue_id)

            if not issue:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Issue {issue_id} not found in project {project_id}",
                        )
                    ],
                    isError=True,
                )

            # Format detailed information
            output = f"Issue Details - #{issue.ref}\n"
            output += "=" * 60 + "\n\n"
            output += f"Subject: {issue.subject}\n"

            if hasattr(issue, "description") and issue.description:
                output += f"\nDescription:\n{issue.description}\n"

            # Status
            status_name = None
            if hasattr(issue, "status_extra_info") and issue.status_extra_info:
                status_name = issue.status_extra_info.get("name")
            output += f"\nStatus: {status_name or getattr(issue, 'status', 'N/A')}\n"

            # Priority
            priority_name = None
            if hasattr(issue, "priority_extra_info") and issue.priority_extra_info:
                priority_name = issue.priority_extra_info.get("name")
            if priority_name:
                output += f"Priority: {priority_name}\n"

            # Severity
            severity_name = None
            if hasattr(issue, "severity_extra_info") and issue.severity_extra_info:
                severity_name = issue.severity_extra_info.get("name")
            if severity_name:
                output += f"Severity: {severity_name}\n"

            # Type
            type_name = None
            if hasattr(issue, "type_extra_info") and issue.type_extra_info:
                type_name = issue.type_extra_info.get("name")
            if type_name:
                output += f"Type: {type_name}\n"

            # Assigned to
            assigned_to = None
            if (
                hasattr(issue, "assigned_to_extra_info")
                and issue.assigned_to_extra_info
            ):
                assigned_to = issue.assigned_to_extra_info.get("full_name")
            if assigned_to:
                output += f"Assigned to: {assigned_to}\n"

            # Due date
            if hasattr(issue, "due_date") and issue.due_date:
                output += f"Due date: {issue.due_date}\n"

            # Tags
            tags = getattr(issue, "tags", [])
            if tags:
                tags_str = ", ".join(
                    tag if isinstance(tag, str) else str(tag) for tag in tags
                )
                output += f"Tags: {tags_str}\n"

            # Related issues
            if hasattr(issue, "related_issues") and issue.related_issues:
                output += (
                    f"\nRelated issues: {', '.join(map(str, issue.related_issues))}\n"
                )

            # Created/Modified
            if hasattr(issue, "created_date") and issue.created_date:
                output += f"\nCreated: {issue.created_date}\n"
            if hasattr(issue, "modified_date") and issue.modified_date:
                output += f"Modified: {issue.modified_date}\n"

            return CallToolResult(
                content=[TextContent(type="text", text=output)],
            )
        except TaigaRestException as e:
            logger.error(f"Taiga API error: {str(e)}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Taiga API Error: {str(e)}")],
                isError=True,
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    def _format_project(self, project: dict) -> str:
        """Format project information for display"""
        lines = [
            f"ID: {project['id']}",
            f"Name: {project['name']}",
            f"Slug: {project['slug']}",
        ]
        if project["description"]:
            lines.append(f"Description: {project['description']}")
        if project["created_date"]:
            lines.append(f"Created: {project['created_date']}")
        if project["members_count"]:
            lines.append(f"Members: {project['members_count']}")
        return "\n".join(lines)

    async def run(self):
        """Run the MCP server using stdio transport"""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Taiga MCP Server started and listening on stdio")
            logger.info(f"Connected to Taiga at {TAIGA_HOST}")

            # Create server capabilities
            capabilities = ServerCapabilities(tools={})

            # Create initialization options
            init_options = InitializationOptions(
                server_name="taiga-mcp-server",
                server_version="1.0.0",
                capabilities=capabilities,
            )

            # Run the server with the stdio streams
            await self.server.run(read_stream, write_stream, init_options)


def main():
    """Main entry point"""
    import asyncio

    server = TaigaMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
