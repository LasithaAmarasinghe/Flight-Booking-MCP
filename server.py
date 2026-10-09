"""Flight Booking Model Context Protocol (MCP) Server.

Demonstrates:
- Resources (Exposing static reference and per-flight files)
- Tools (Searching and booking flights)
- Prompts (Reusable prompt templates for user interaction)
"""

from pathlib import Path
import json
import uuid
from mcp import types
from mcp.server.fastmcp import FastMCP, Context

# Initialize FastMCP Server
mcp = FastMCP("FlightBookingService")

DATA_DIR = Path(__file__).parent / "data"
FLIGHTS_FILE = DATA_DIR / "flights.txt"
POLICY_FILE = DATA_DIR / "policy.txt"
BOOKINGS_FILE = DATA_DIR / "bookings.json"


# ---------------------------------------------------------------------------
# Helper Utilities
# ---------------------------------------------------------------------------
def _load_flights() -> list[dict[str, str]]:
    """Parse pipe-delimited flights.txt into structured dictionaries."""
    if not FLIGHTS_FILE.exists():
        return []
    
    flights = []
    lines = FLIGHTS_FILE.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return []
    
    headers = [h.strip() for h in lines[0].split("|")]
    for line in lines[1:]:
        if not line.strip():
            continue
        values = [v.strip() for v in line.split("|")]
        flights.append(dict(zip(headers, values)))
    return flights


def _update_flight_seats(flight_id: str, delta: int) -> bool:
    """Increment/decrement seat count for a flight in flights.txt."""
    flights = _load_flights()
    found = False
    for f in flights:
        if f["FLIGHT_ID"].upper() == flight_id.upper():
            seats = int(f["SEATS_LEFT"]) + delta
            if seats < 0:
                return False
            f["SEATS_LEFT"] = str(seats)
            found = True
            break
            
    if not found:
        return False

    headers = ["FLIGHT_ID", "ORIGIN", "DESTINATION", "DEPARTURE", "ARRIVAL", "PRICE_USD", "SEATS_LEFT"]
    output_lines = [" | ".join(headers)]
    for f in flights:
        row = [
            f["FLIGHT_ID"].ljust(9),
            f["ORIGIN"].ljust(6),
            f["DESTINATION"].ljust(11),
            f["DEPARTURE"].ljust(9),
            f["ARRIVAL"].ljust(7),
            f["PRICE_USD"].ljust(9),
            f["SEATS_LEFT"]
        ]
        output_lines.append(" | ".join(row))
        
    FLIGHTS_FILE.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# 1. MCP RESOURCES
# ---------------------------------------------------------------------------
@mcp.resource("flight://policies")
def get_airline_policies() -> str:
    """Return general airline cancellation, baggage, and booking policies."""
    if not POLICY_FILE.exists():
        return "No policy documents found."
    return POLICY_FILE.read_text(encoding="utf-8")


@mcp.resource("flight://details/{flight_id}")
def get_flight_details(flight_id: str) -> str:
    """Retrieve full raw record for a specific flight identifier."""
    flights = _load_flights()
    for flight in flights:
        if flight["FLIGHT_ID"].upper() == flight_id.upper():
            return json.dumps(flight, indent=2)
    return f"Flight '{flight_id}' not found."


# ---------------------------------------------------------------------------
# 2. MCP TOOLS
# ---------------------------------------------------------------------------
@mcp.tool()
def search_flights(origin: str, destination: str, min_seats: int = 1) -> str:
    """Search for available flights between two 3-letter IATA airport codes.

    Args:
        origin: 3-letter airport code (e.g., 'SIN', 'CMB').
        destination: 3-letter airport code (e.g., 'LHR', 'SIN').
        min_seats: Minimum number of remaining seats required (default: 1).
    """
    flights = _load_flights()
    results = [
        f for f in flights
        if f["ORIGIN"].upper() == origin.upper()
        and f["DESTINATION"].upper() == destination.upper()
        and int(f["SEATS_LEFT"]) >= min_seats
    ]

    if not results:
        return f"No available flights found from {origin.upper()} to {destination.upper()}."

    return json.dumps(results, indent=2)


@mcp.tool()
def book_flight(flight_id: str, passenger_name: str, seats: int = 1) -> str:
    """Book seats on an available flight and reduce inventory.

    Args:
        flight_id: Flight code (e.g., 'SQ308').
        passenger_name: Full legal passenger name.
        seats: Number of seats to reserve (default: 1).
    """
    flights = _load_flights()
    target_flight = next((f for f in flights if f["FLIGHT_ID"].upper() == flight_id.upper()), None)

    if not target_flight:
        return f"Error: Flight '{flight_id}' does not exist."

    current_seats = int(target_flight["SEATS_LEFT"])
    if current_seats < seats:
        return f"Booking failed: Only {current_seats} seats remaining on {flight_id}."

    # Update seats in flights.txt
    success = _update_flight_seats(flight_id, -seats)
    if not success:
        return "Internal error updating seat manifest."

    # Record booking
    booking_id = f"BK-{uuid.uuid4().hex[:6].upper()}"
    booking_record = {
        "booking_id": booking_id,
        "flight_id": target_flight["FLIGHT_ID"],
        "passenger_name": passenger_name,
        "seats": seats,
        "total_cost_usd": int(target_flight["PRICE_USD"]) * seats,
        "status": "CONFIRMED"
    }

    existing_bookings = []
    if BOOKINGS_FILE.exists():
        try:
            existing_bookings = json.loads(BOOKINGS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_bookings = []

    existing_bookings.append(booking_record)
    BOOKINGS_FILE.write_text(json.dumps(existing_bookings, indent=2), encoding="utf-8")

    return json.dumps(booking_record, indent=2)


# ---------------------------------------------------------------------------
# 3. MCP PROMPTS
# ---------------------------------------------------------------------------
@mcp.prompt()
def flight_booking_assistant(traveler_name: str, origin: str, destination: str) -> str:
    """Standardized prompt guiding an LLM to assist with booking flights.

    Args:
        traveler_name: Name of the traveler.
        origin: Departure airport code.
        destination: Arrival airport code.
    """
    return f"""You are a professional travel booking agent.
Passenger: {traveler_name}
Origin: {origin}
Destination: {destination}

Instructions:
1. Use the `search_flights` tool to check for active flight routes between {origin} and {destination}.
2. Check `flight://policies` resource if the user has questions about luggage or cancellations.
3. Present the best flight options clearly with departure times and prices.
4. When the passenger picks a flight, use the `book_flight` tool to confirm their reservation.
"""

# MCP COMPLETIONS -----------------------------------------------------------

@mcp.completion()
async def complete_airport(
    ref: types.PromptReference | types.ResourceTemplateReference,
    argument: types.CompletionArgument,
    context: types.CompletionContext | None,
) -> types.Completion | None:
    if not isinstance(ref, types.PromptReference) or ref.name != "flight_booking_assistant":
        return None
    if argument.name not in {"origin", "destination"}:
        return None

    airports = ["SIN", "CMB", "LHR", "DXB", "SYD"]
    values = [a for a in airports if a.startswith(argument.value.upper())]
    return types.Completion(values=values, total=len(values))

if __name__ == "__main__":
    mcp.run()
