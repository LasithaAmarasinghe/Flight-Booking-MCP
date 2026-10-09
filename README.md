# Flight Booking MCP Server

This repository accompanies the Medium article **“The Agent Integration
Nightmare: How MCP Changes Everything.”** It provides a hands-on example of
building and inspecting an MCP server.

A reference implementation demonstrating the core primitives of the **Model
Context Protocol (MCP)**, an open protocol originally introduced by Anthropic,
using Python and `FastMCP`.

## Project Structure

```
flight-booking-mcp/
├── data/
│   ├── flights.txt        # Plaintext flight schedule
│   └── policy.txt         # Plaintext travel & baggage policy
├── server.py              # MCP server (Tools, Resources, Prompts)
├── requirements.txt       # Dependencies
├── .gitignore              # Git ignore rules
└── README.md              # Documentation & setup
```

## Features Demonstrated

1. **Resources**:
   - `flight://policies`: Static text resource exposing airline policies.
   - `flight://details/{flight_id}`: Parameterized resource fetching individual flight metadata.
2. **Tools**:
   - `search_flights`: Query flights by origin, destination, and seat count.
   - `book_flight`: Mutates inventory and records booking state.
3. **Prompts**:
   - `flight_booking_assistant`: Reusable prompt template guiding client LLMs through an end-to-end booking flow.

## Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The project uses the MCP 1.x `FastMCP` API.

### 2. Run with MCP Inspector

Run the Inspector from the project directory:

```bash
npx @modelcontextprotocol/inspector /opt/anaconda3/bin/python server.py
```
