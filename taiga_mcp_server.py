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
from pathlib import Path
from typing import Any

import requests

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
TMP_DIR_MAX_SIZE_MB = int(os.getenv("TMP_DIR_MAX_SIZE_MB", "500"))


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
                            "get_assigned": {
                                "type": "boolean",
                                "description": "If true, only return stories assigned to the current user (default: true)",
                                "default": True,
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
                            "get_assigned": {
                                "type": "boolean",
                                "description": "If true, only return issues assigned to the current user (default: true)",
                                "default": True,
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
                                "description": "Issue identifier (global issue ID, or project ref like #27 / 27)",
                            },
                        },
                        "required": ["project_id", "issue_id"],
                    },
                ),
                Tool(
                    name="add_issue_comment_and_reassign",
                    description="Add a comment to an issue and reassign it back to the previous assignee. Use when something is fixed or when you need to ask for more information.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "integer",
                                "description": "The ID of the project",
                            },
                            "issue_id": {
                                "type": "integer",
                                "description": "Issue identifier (global issue ID, or project ref like #27 / 27)",
                            },
                            "comment_text": {
                                "type": "string",
                                "description": "The comment to add to the issue",
                            },
                            "is_fixed": {
                                "type": "boolean",
                                "description": "If true, append 'Everything is fixed and should be tested'. If false, the comment is treated as a question/request for more info.",
                                "default": True,
                            },
                        },
                        "required": ["project_id", "issue_id", "comment_text"],
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
                elif name == "get_project_backlog":
                    # Deprecated: redirect to get_user_stories
                    return self.handle_get_user_stories(arguments)
                elif name == "get_user_story_details":
                    return self.handle_get_user_story_details(arguments)
                elif name == "get_issue_details":
                    return self.handle_get_issue_details(arguments)
                elif name == "add_issue_comment_and_reassign":
                    return self.handle_add_issue_comment_and_reassign(arguments)
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
        """Get the project specified by DEFAULT_PROJECT_ID environment variable"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            # Get the project by DEFAULT_PROJECT_ID
            project = self.api.projects.get(DEFAULT_PROJECT_ID)

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
            get_assigned = arguments.get("get_assigned", True)

            if not project_id:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="Error: project_id is required")
                    ],
                    isError=True,
                )

            # Get current user if filtering by assigned
            current_user_id = None
            if get_assigned:
                try:
                    current_user = self.api.me()
                    current_user_id = current_user.id
                except Exception as e:
                    logger.warning(f"Could not get current user: {str(e)}")

            # Get user stories (backlog items)
            user_stories = self.api.user_stories.list(
                project=project_id, status__is_closed=False
            )

            # Filter by assigned user if requested
            if get_assigned and current_user_id:
                user_stories = [
                    story
                    for story in user_stories
                    if story.assigned_to == current_user_id
                ]

            # Limit results
            if limit and len(user_stories) > limit:
                user_stories = user_stories[:limit]

            if not user_stories:
                filter_text = " assigned to you" if get_assigned else ""
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No user stories found for project {project_id}{filter_text}",
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
            filter_text = " (assigned to you)" if get_assigned else ""
            output = f"User Stories for project {project_id}{filter_text}: {len(items)} items\n\n"
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
                    output += (
                        f"   Tags: {', '.join(self._normalize_tags(item['tags']))}\n"
                    )
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
            get_assigned = arguments.get("get_assigned", True)

            if not project_id:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="Error: project_id is required")
                    ],
                    isError=True,
                )

            # Get current user if filtering by assigned
            current_user_id = None
            if get_assigned:
                try:
                    current_user = self.api.me()
                    current_user_id = current_user.id
                except Exception as e:
                    logger.warning(f"Could not get current user: {str(e)}")

            # Get issues
            issues = self.api.issues.list(project=project_id)

            # Filter by assigned user if requested
            if get_assigned and current_user_id:
                issues = [
                    issue for issue in issues if issue.assigned_to == current_user_id
                ]

            # Limit results
            if limit and len(issues) > limit:
                issues = issues[:limit]

            if not issues:
                filter_text = " assigned to you" if get_assigned else ""
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"No issues found for project {project_id}{filter_text}",
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
            filter_text = " (assigned to you)" if get_assigned else ""
            output = (
                f"Issues for project {project_id}{filter_text}: {len(items)} items\n\n"
            )
            for idx, item in enumerate(items, 1):
                output += f"{idx}. [#{item['ref']}] {item['subject']}\n"
                output += f"   Global ID: {item['id']}\n"
                if item["assigned_to"]:
                    output += f"   Assigned to: {item['assigned_to']}\n"
                if item["status"]:
                    output += f"   Status: {item['status']}\n"
                if item["priority"]:
                    output += f"   Priority: {item['priority']}\n"
                if item["tags"]:
                    output += (
                        f"   Tags: {', '.join(self._normalize_tags(item['tags']))}\n"
                    )
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

            # Get the specific issue by global ID or by project reference
            issue = self._resolve_issue_for_project(project_id, issue_id)

            if not issue:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                f"Issue identifier '{issue_id}' not found in project {project_id}. "
                                "Use either the issue Global ID or project ref (e.g. #27)."
                            ),
                        )
                    ],
                    isError=True,
                )

            # Format detailed information
            output = f"Issue Details - #{issue.ref}\n"
            output += "=" * 60 + "\n\n"
            output += f"Global ID: {issue.id}\n"
            output += f"Project Ref: #{issue.ref}\n"
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
                tags_str = ", ".join(self._normalize_tags(tags))
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

            download_result = self._download_issue_attachments(
                issue=issue,
                project_id=project_id,
            )
            if download_result:
                output += "\n\nAttachments (downloaded to local tmp):\n"
                output += (
                    f"Downloaded: {download_result['downloaded_count']}, "
                    f"Skipped (non-AI-readable): {download_result['skipped_count']}, "
                    f"Failed: {download_result['failed_count']}\n"
                )
                output += f"Directory: {download_result['issue_dir']}\n"
                if download_result["downloaded_files"]:
                    output += "Files:\n"
                    for file_name in download_result["downloaded_files"]:
                        output += f"- {file_name}\n"
                if download_result["warning"]:
                    output += f"\nWARNING: {download_result['warning']}\n"

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

    def handle_add_issue_comment_and_reassign(self, arguments: dict) -> CallToolResult:
        """Add a comment to an issue, change status, and reassign it back to the previous assignee"""
        try:
            if not self.api:
                raise RuntimeError("API not initialized")

            project_id = arguments.get("project_id")
            issue_id = arguments.get("issue_id")
            comment_text = arguments.get("comment_text", "")
            is_fixed = arguments.get("is_fixed", True)

            if not project_id or not issue_id or not comment_text:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="Error: project_id, issue_id, and comment_text are required",
                        )
                    ],
                    isError=True,
                )

            # Get current user
            try:
                current_user = self.api.me()
                current_user_id = current_user.id
                current_user_name = current_user.full_name_display
            except Exception as e:
                logger.error(f"Failed to get current user: {str(e)}")
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error: Failed to get current user: {str(e)}",
                        )
                    ],
                    isError=True,
                )

            # Get the issue by global ID or by project reference
            issue = self._resolve_issue_for_project(project_id, issue_id)

            if not issue:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                f"Issue identifier '{issue_id}' not found in project {project_id}. "
                                "Use either the issue Global ID or project ref (e.g. #27)."
                            ),
                        )
                    ],
                    isError=True,
                )

            requester = issue.requester

            # Get the history to find the previous assignee
            response = requester.get(f"/history/issue/{issue.id}")
            history = response.json()

            # Parse history to find who had it before the current user
            previous_assignee_id = None
            previous_assignee_name = None

            # Look through history to find assignment changes
            # diff["assigned_to"] contains [old_id, new_id] where values are user IDs
            assignment_changes = []
            for item in history:
                if item.get("diff") and "assigned_to" in item["diff"]:
                    diff = item["diff"]["assigned_to"]
                    if isinstance(diff, list) and len(diff) >= 2:
                        assignment_changes.append(
                            {"old_id": diff[0], "new_id": diff[1], "item": item}
                        )

            # Get the previous assignee from the changes
            if assignment_changes:
                most_recent = assignment_changes[0]

                # If most recent is unassigned → assigned, look for the person before unassignment
                if most_recent["old_id"] is None and len(assignment_changes) > 1:
                    for change in assignment_changes[1:]:
                        if change["old_id"] is not None:
                            previous_assignee_id = change["old_id"]
                            item = change["item"]
                            if item.get("values") and item["values"].get("users"):
                                users = item["values"]["users"]
                                previous_assignee_name = users.get(
                                    str(previous_assignee_id)
                                )
                            break
                else:
                    # Most recent change already shows who had it before
                    if most_recent["old_id"] is not None:
                        previous_assignee_id = most_recent["old_id"]
                        item = most_recent["item"]
                        if item.get("values") and item["values"].get("users"):
                            users = item["values"]["users"]
                            previous_assignee_name = users.get(
                                str(previous_assignee_id)
                            )

            # Prepare the comment
            final_comment = comment_text
            if is_fixed:
                final_comment += "\n\nEverything is fixed and should be tested."

            # Get the project to fetch status options
            try:
                status_list = self.api.issue_statuses.list(project=project_id)

                # Find the status IDs by name
                status_id = None
                target_status_name = "Ready for test" if is_fixed else "Needs Info"

                for status in status_list:
                    if status.name.lower() == target_status_name.lower():
                        status_id = status.id
                        break

                if not status_id:
                    # If exact match not found, try partial match
                    for status in status_list:
                        if (
                            target_status_name.lower() in status.name.lower()
                            or status.name.lower() in target_status_name.lower()
                        ):
                            status_id = status.id
                            break

                if not status_id:
                    available_statuses = [s.name for s in status_list]
                    logger.error(
                        f"Status '{target_status_name}' not found for project {project_id}. "
                        f"Available: {available_statuses}"
                    )
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text=(
                                    f"Error: Status '{target_status_name}' not found in project {project_id}. "
                                    f"Available statuses: {', '.join(available_statuses)}"
                                ),
                            )
                        ],
                        isError=True,
                    )

            except Exception as e:
                logger.error(f"Failed to get status options: {str(e)}")
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error: Failed to resolve issue status options: {str(e)}",
                        )
                    ],
                    isError=True,
                )

            # Determine reassignment target: previous assignee if available, otherwise issue owner (creator)
            reassignment_id = None
            reassignment_name = None
            reassignment_source = None

            if previous_assignee_id and previous_assignee_id != current_user_id:
                reassignment_id = previous_assignee_id
                reassignment_name = previous_assignee_name
                reassignment_source = "previous assignee"
            else:
                owner_id = issue.owner.id if hasattr(issue.owner, "id") else issue.owner
                if owner_id:
                    reassignment_id = owner_id
                    if (
                        hasattr(issue, "owner_extra_info")
                        and issue.owner_extra_info
                        and isinstance(issue.owner_extra_info, dict)
                    ):
                        reassignment_name = issue.owner_extra_info.get(
                            "full_name_display"
                        )
                    reassignment_source = "issue owner"

            # Prepare partial update payload
            patch_fields = ["version", "comment", "status"]
            patch_kwargs = {
                "comment": final_comment,
                "status": status_id,
                "version": issue.version,
            }

            # Reassign to target user (previous assignee or issue owner fallback)
            if reassignment_id:
                patch_fields.append("assigned_to")
                patch_kwargs["assigned_to"] = reassignment_id

            # Update the issue via model patch (partial update)
            issue.patch(patch_fields, **patch_kwargs)

            # Format output
            status_text = "Ready for test" if is_fixed else "Needs Info"
            assignee_info = ""
            if reassignment_id:
                assignee_label = reassignment_name or f"user id {reassignment_id}"
                assignee_info = (
                    f" and reassigned to {assignee_label}" f" ({reassignment_source})"
                )

            output = f"✓ Updated issue #{issue.ref}\n"
            output += f"\n  Comment added\n"
            output += f"  Status changed to: {status_text}{assignee_info}\n"
            output += f"\n  Comment:\n  {final_comment}"

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

    def _normalize_tags(self, tags: list[Any]) -> list[str]:
        """Normalize Taiga tags to a list of displayable strings."""
        normalized = []
        for tag in tags:
            if isinstance(tag, str):
                normalized.append(tag)
            elif isinstance(tag, (list, tuple)) and tag:
                normalized.append(str(tag[0]))
            else:
                normalized.append(str(tag))
        return normalized

    def _to_int_or_none(self, value: Any) -> int | None:
        """Convert a value to int when possible (supports '#27' style references)."""
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value

        text = str(value).strip()
        if text.startswith("#"):
            text = text[1:].strip()
        if not text:
            return None

        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    def _issue_belongs_to_project(self, issue: Any, project_id: int) -> bool:
        """Check if an issue belongs to a given project."""
        issue_project = getattr(issue, "project", None)
        issue_project_id = self._to_int_or_none(issue_project)
        if issue_project_id is not None:
            return issue_project_id == project_id

        project_extra_info = getattr(issue, "project_extra_info", None)
        if isinstance(project_extra_info, dict):
            issue_project_id = self._to_int_or_none(project_extra_info.get("id"))
            if issue_project_id is not None:
                return issue_project_id == project_id

        return False

    def _resolve_issue_for_project(self, project_id: int, issue_identifier: Any) -> Any:
        """Resolve issue by global issue ID or project ref within the given project."""
        issue_number = self._to_int_or_none(issue_identifier)
        if issue_number is None:
            return None

        # First, try as global issue ID.
        try:
            candidate = self.api.issues.get(issue_number)
            if candidate and self._issue_belongs_to_project(candidate, project_id):
                return candidate
        except Exception:
            pass

        # Fallback: treat the number as project reference and resolve from project issues.
        try:
            issues = self.api.issues.list(project=project_id)
            for issue in issues:
                issue_ref = self._to_int_or_none(getattr(issue, "ref", None))
                if issue_ref == issue_number:
                    return issue
        except Exception:
            pass

        return None

    def _download_issue_attachments(
        self, issue: Any, project_id: int
    ) -> dict[str, Any]:
        """Download AI-readable issue attachments to local tmp directory."""
        base_tmp_dir = Path(__file__).resolve().parent / "tmp"
        issue_dir = base_tmp_dir / f"issue-{issue.ref}-{issue.id}"
        issue_dir.mkdir(parents=True, exist_ok=True)

        attachments = self.api.issue_attachments.list(
            project=project_id, object_id=issue.id
        )

        downloaded_files: list[str] = []
        downloaded_count = 0
        skipped_count = 0
        failed_count = 0

        for attachment in attachments:
            attachment_data = (
                attachment.to_dict() if hasattr(attachment, "to_dict") else attachment
            )
            if not isinstance(attachment_data, dict):
                skipped_count += 1
                continue

            file_name = self._attachment_file_name(attachment_data)
            if not self._is_ai_readable_file(file_name):
                skipped_count += 1
                continue

            download_url = self._attachment_download_url(attachment_data)
            if not download_url:
                failed_count += 1
                continue

            destination = self._unique_destination_path(
                issue_dir,
                self._sanitize_filename(file_name),
            )
            ok = self._download_file(download_url, destination, issue.requester)
            if ok:
                downloaded_count += 1
                downloaded_files.append(destination.name)
            else:
                failed_count += 1

        total_size_bytes = self._directory_size_bytes(base_tmp_dir)
        threshold_bytes = TMP_DIR_MAX_SIZE_MB * 1024 * 1024
        warning = ""
        if total_size_bytes > threshold_bytes:
            warning = (
                f"tmp directory size is {self._format_size(total_size_bytes)}, "
                f"which exceeds TMP_DIR_MAX_SIZE_MB ({TMP_DIR_MAX_SIZE_MB} MB)."
            )

        return {
            "downloaded_count": downloaded_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "downloaded_files": downloaded_files,
            "issue_dir": str(issue_dir),
            "warning": warning,
        }

    def _attachment_file_name(self, attachment: dict[str, Any]) -> str:
        """Extract a usable filename from Taiga attachment payload."""
        name = attachment.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

        attached_file = attachment.get("attached_file")
        if isinstance(attached_file, str) and attached_file.strip():
            return Path(attached_file).name

        url = attachment.get("url")
        if isinstance(url, str) and url.strip():
            clean_url = url.split("#", 1)[0].split("?", 1)[0]
            return Path(clean_url).name

        return "attachment.bin"

    def _attachment_download_url(self, attachment: dict[str, Any]) -> str:
        """Build or extract download URL for a Taiga attachment."""
        url = attachment.get("url")
        if isinstance(url, str) and url.strip():
            return url

        attached_file = attachment.get("attached_file")
        if isinstance(attached_file, str) and attached_file.strip():
            relative_path = attached_file.lstrip("/")
            return f"{TAIGA_HOST.rstrip('/')}/media/{relative_path}"

        return ""

    def _is_ai_readable_file(self, file_name: str) -> bool:
        """Allow only image and text-based attachments suitable for AI processing."""
        extension = Path(file_name).suffix.lower()
        ai_readable_extensions = {
            ".txt",
            ".md",
            ".markdown",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".htm",
            ".css",
            ".js",
            ".mjs",
            ".ts",
            ".tsx",
            ".jsx",
            ".csv",
            ".tsv",
            ".log",
            ".sql",
            ".ini",
            ".cfg",
            ".conf",
            ".toml",
            ".rst",
            ".py",
            ".php",
            ".sh",
            ".bash",
            ".zsh",
            ".java",
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".go",
            ".rb",
            ".kt",
            ".swift",
            ".scala",
            ".dart",
            ".env",
            ".gitignore",
            ".dockerfile",
            ".svg",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".bmp",
            ".tif",
            ".tiff",
        }
        return extension in ai_readable_extensions

    def _sanitize_filename(self, file_name: str) -> str:
        """Create a safe local filename."""
        cleaned = file_name.replace("/", "_").replace("\\", "_").strip()
        return cleaned or "attachment.bin"

    def _unique_destination_path(self, directory: Path, file_name: str) -> Path:
        """Ensure attachment file names do not overwrite existing files."""
        candidate = directory / file_name
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        counter = 1
        while True:
            candidate = directory / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _download_file(self, url: str, destination: Path, requester: Any) -> bool:
        """Download a file using Taiga authentication headers when needed."""
        try:
            headers = {}
            if hasattr(requester, "headers"):
                headers = requester.headers(paginate=False)

            response = requests.get(url, headers=headers, timeout=60, stream=True)
            if response.status_code >= 400:
                logger.warning(
                    f"Failed to download attachment from {url}. "
                    f"Status: {response.status_code}"
                )
                return False

            with destination.open("wb") as out_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        out_file.write(chunk)
            return True
        except Exception as exc:
            logger.warning(f"Attachment download failed for {url}: {str(exc)}")
            return False

    def _directory_size_bytes(self, directory: Path) -> int:
        """Get total size in bytes for a directory tree."""
        if not directory.exists():
            return 0
        total = 0
        for path in directory.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes as human-readable string."""
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f} {units[unit_index]}"

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
