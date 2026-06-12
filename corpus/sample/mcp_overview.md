# Model Context Protocol (MCP)

The Model Context Protocol (MCP) is an open standard that enables seamless integration between LLM applications and external data sources and tools. Whether you're building an AI-powered IDE, enhancing a chat interface, or creating custom AI workflows, MCP provides a standardised way to connect LLMs with the context they need.

## Why MCP?

Today, AI applications are constrained by their isolation from data. Every new data source requires its own custom implementation. MCP addresses this challenge by providing a universal, open protocol for connecting AI systems with data sources.

## How MCP Works

At its core, MCP follows a client-server architecture where a host application can connect to multiple servers:

- **MCP Hosts**: Programs like Claude Desktop, IDEs, or AI tools that want to access data through MCP.
- **MCP Clients**: Protocol clients that maintain 1:1 connections with servers.
- **MCP Servers**: Lightweight programs that each expose specific capabilities through the standardised Model Context Protocol.

## Key Features

MCP servers can provide three main types of features:

1. **Resources**: File-like data that can be read by clients (like file contents or API responses)
2. **Tools**: Functions that can be called by the LLM (with user approval)
3. **Prompts**: Pre-written templates that help users accomplish specific tasks
