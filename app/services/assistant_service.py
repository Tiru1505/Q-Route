"""LLM orchestration for the route assistant.

The model decides which navigation tool to call. Tools are the only way it can
change or inspect routing state; it never receives database access.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.assistant_models import AssistantAction, AssistantChatRequest, AssistantChatResponse
from app.models.route_models import Coordinate, RouteConstraints, RouteRequest
from app.services.route_service import RouteService
from app.services.traffic_service import TrafficService

_logger = get_logger("services.assistant")

TOOLS = [
    {"type": "function", "function": {"name": "search_places", "description": "Find routable Hyderabad places matching natural language. Call this before setting a location when its coordinates are unknown.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "set_start_location", "description": "Resolve and set the trip start location. Use a place name, not coordinates.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "set_destination", "description": "Resolve and set the trip destination. Use a place name, not coordinates.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "calculate_route", "description": "Calculate a route after both locations are available. Supports combined preferences and constraints.", "parameters": {"type": "object", "properties": {"preference": {"type": "string", "enum": ["fastest", "shortest", "avoid_congestion", "balanced"]}, "avoid_tolls": {"type": "boolean"}, "avoid_highways": {"type": "boolean"}}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "find_alternative_route", "description": "Find a genuinely different route for the current trip.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_current_route", "description": "Inspect the route currently shown to the user.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_route_eta", "description": "Read the actual ETA from the current route.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_route_distance", "description": "Read the actual distance from the current route.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_traffic_status", "description": "Inspect current traffic records and congestion levels.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_live_incidents", "description": "Inspect incidents currently available in the traffic feed.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
]

SYSTEM_PROMPT = """You are the navigation assistant for Q Route. Understand any natural-language request, maintain context across the supplied conversation, and use tools for every route action or factual lookup. Never invent routes, ETAs, distances, traffic, incidents, or capabilities. If a location is ambiguous, search it and ask a concise clarification. When a user asks for a route, extract every compatible preference and constraint before calculating it. After tool calls, answer concisely using the returned data. Quick actions are not relevant to your reasoning: treat every user message as open-ended."""


class AssistantNotConfiguredError(RuntimeError):
    """Raised when the server has no LLM credentials."""


class AssistantService:
    def __init__(self, route_service: RouteService | None = None, traffic_service: TrafficService | None = None):
        settings = get_settings()
        self.api_key = settings.ai_api_key
        self.base_url = settings.ai_base_url.rstrip("/")
        self.model = settings.ai_model
        self.route_service = route_service or RouteService()
        self.traffic_service = traffic_service or TrafficService()

    async def chat(self, request: AssistantChatRequest) -> AssistantChatResponse:
        if not self.api_key:
            raise AssistantNotConfiguredError("AI_API_KEY is not configured on the backend")

        working_context = request.context.model_dump(mode="json")
        actions: list[AssistantAction] = []
        conversation: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        conversation.extend(message.model_dump() for message in request.messages)

        async with httpx.AsyncClient(timeout=45) as client:
            for _ in range(8):
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": conversation, "tools": TOOLS, "tool_choice": "auto", "temperature": 0.2},
                )
                response.raise_for_status()
                assistant_message = response.json()["choices"][0]["message"]
                tool_calls = assistant_message.get("tool_calls") or []
                conversation.append(assistant_message)
                if not tool_calls:
                    return AssistantChatResponse(message=assistant_message.get("content") or "I could not formulate a response.", actions=actions, provider="openai-compatible", model=self.model)

                for call in tool_calls:
                    result, new_actions = self._run_tool(call["function"]["name"], json.loads(call["function"].get("arguments") or "{}"), working_context)
                    actions.extend(new_actions)
                    conversation.append({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": json.dumps(result, default=str)})

        raise RuntimeError("Assistant exceeded its tool-call limit")

    def _run_tool(self, name: str, args: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], list[AssistantAction]]:
        actions: list[AssistantAction] = []
        if name == "search_places":
            from app.api.places import search_places
            return search_places(q=args["query"], limit=5), actions

        if name in {"set_start_location", "set_destination"}:
            from app.api.places import search_places
            results = search_places(q=args["location"], limit=5)["results"]
            if not results:
                return {"error": f"No routable place found for {args['location']}."}, actions
            if len(results) > 1 and results[0]["name"].lower() != args["location"].lower():
                return {"matches": results, "needs_clarification": True}, actions
            place = results[0]
            key = "start" if name == "set_start_location" else "destination"
            context[key] = place
            action_type = "set_start" if key == "start" else "set_destination"
            actions.append(AssistantAction(type=action_type, payload=place))
            return {"selected": place}, actions

        if name == "calculate_route":
            start, destination = context.get("start"), context.get("destination")
            if not start or not destination:
                return {"error": "Both start and destination are required before calculating a route."}, actions
            preference = args.get("preference", "balanced")
            algorithm = "dijkstra" if preference in {"fastest", "shortest"} else "qpso"
            route_request = RouteRequest(
                source=Coordinate(lat=start["lat"], lon=start["lon"]),
                destination=Coordinate(lat=destination["lat"], lon=destination["lon"]),
                algorithm=algorithm,
                constraints=RouteConstraints(avoid_tolls=args.get("avoid_tolls", False), avoid_highways=args.get("avoid_highways", False)),
                source_name=start.get("name"), destination_name=destination.get("name"),
            )
            result = self.route_service.optimize(route_request).model_dump(mode="json")
            context["current_route"] = result
            actions.append(AssistantAction(type="route_result", payload={"primary": result, "alternatives": []}))
            return result, actions

        if name == "find_alternative_route":
            start, destination = context.get("start"), context.get("destination")
            if not start or not destination:
                return {"error": "There is no complete trip to find an alternative for."}, actions
            route_request = RouteRequest(source=Coordinate(lat=start["lat"], lon=start["lon"]), destination=Coordinate(lat=destination["lat"], lon=destination["lon"]), source_name=start.get("name"), destination_name=destination.get("name"))
            results = [result.model_dump(mode="json") for result in self.route_service.get_alternatives(route_request)]
            actions.append(AssistantAction(type="alternatives", payload={"routes": results}))
            return {"routes": results}, actions

        current = context.get("selected_route") or context.get("current_route")
        if name == "get_current_route":
            return current or {"error": "No route is currently displayed."}, actions
        if name == "get_route_eta":
            return {"eta_minutes": self._route_value(current, "travel_time_minutes", "etaMin")}, actions
        if name == "get_route_distance":
            return {"distance_km": self._route_value(current, "distance_km", "distanceKm")}, actions
        if name == "get_traffic_status":
            snapshot = self.traffic_service.get_current().model_dump(mode="json")
            return snapshot, actions
        if name == "get_live_incidents":
            snapshot = self.traffic_service.get_current().model_dump(mode="json")
            return {"incidents": [record for record in snapshot.get("records", []) if record.get("road_name") or record.get("segment_id")]}, actions
        return {"error": f"Unknown tool: {name}"}, actions

    @staticmethod
    def _route_value(route: dict[str, Any] | None, backend_key: str, frontend_key: str) -> Any:
        if not route:
            return None
        return route.get(frontend_key) or route.get("route", {}).get(backend_key)
