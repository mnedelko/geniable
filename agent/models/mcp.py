"""MCP (Model Context Protocol) data models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """MCP tool definition from discovery endpoint."""

    name: str = Field(..., description="Tool identifier")
    description: str = Field(..., description="Human-readable description")
    version: str = Field(default="1.0.0", description="Tool version")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for input")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema for output")


class MCPMetadata(BaseModel):
    """Metadata from MCP discovery response."""

    total_tools: int = 0
    last_updated: Optional[str] = None


class MCPDiscoveryResponse(BaseModel):
    """Response from MCP tool discovery endpoint."""

    schema_version: str = "1.0"
    service: str
    tools: List[MCPToolDefinition] = Field(default_factory=list)
    metadata: MCPMetadata = Field(default_factory=MCPMetadata)
