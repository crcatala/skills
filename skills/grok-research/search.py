#!/usr/bin/env python3
"""
Grok Search — agentic web + X search via xAI's API.

Uses Grok 4.6 with server-side web_search and x_search tools.
The model autonomously decides how many searches to perform, follows links,
and synthesizes a final answer with citations.
"""

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import os
import sys
import time
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


MIN_XAI_SDK_VERSION = "1.19.0"

PROFILE_PROMPTS = {
    "general": """Conduct a rigorous, decision-useful web research task. Verify named products, releases, people, organizations, and events before describing them. Prefer primary sources for factual claims, cross-check consequential facts, and distinguish confirmed facts from inference or disagreement. If the premise is unsupported, state precisely what was checked, what was not found, the search scope/date, and what would change the conclusion. Never treat an absence of search results alone as proof of nonexistence.""",
    "factual": """Prioritize primary and authoritative sources. Verify dates, names, versions, and quantities independently where practical. Give a concise answer and explicitly label uncertainty or unresolved conflicts.""",
    "comparison": """Compare options using consistent criteria. Prefer official documentation for features and pricing, identify version/date context, and clearly separate verified capabilities from evaluative judgment.""",
    "news": """Prioritize recent, reputable reporting and primary statements. State event dates, distinguish reports from confirmed facts, and explain material uncertainty in developing stories.""",
    "social": """Use web and X evidence to describe sentiment, but do not present anecdotes as representative. Separate observed themes, notable dissent, and factual claims verified by authoritative sources.""",
    "literature": """Prioritize original papers, preprints, official datasets, and institutional sources. Separate findings from limitations, report publication dates, and avoid treating abstracts or secondary summaries as conclusive evidence.""",
}

CLAIMS_SCHEMA_PROMPT = """Return ONLY valid JSON, with no Markdown fences or prose, matching this shape:
{
  "claims": [
    {
      "claim": "A precise, independently meaningful claim.",
      "confidence": "high|medium|low",
      "evidence": [
        {
          "url": "https://source.example/path",
          "support": "How this specific source supports or qualifies the claim.",
          "source_type": "primary|official|reporting|analysis|social"
        }
      ]
    }
  ],
  "limitations": ["Important uncertainty, gap, or conflicting evidence."]
}
Use at least one enabled search tool before answering. Return at least one evidence-backed claim; never return a placeholder, a "research not complete" response, or an empty claims array. Do not invent URLs, evidence, or certainty."""


class Evidence(BaseModel):
    url: HttpUrl = Field(description="Direct HTTP(S) URL that supports the claim")
    support: str = Field(min_length=1, description="How this source supports or qualifies the claim")
    source_type: Literal["primary", "official", "reporting", "analysis", "social"]


class Claim(BaseModel):
    claim: str = Field(min_length=1, description="A precise, independently meaningful claim")
    confidence: Literal["high", "medium", "low"]
    evidence: list[Evidence] = Field(min_length=1)


class ClaimsResponse(BaseModel):
    claims: list[Claim] = Field(min_length=1)
    limitations: list[str] = Field(description="Important uncertainty, gap, or conflicting evidence")


def parse_claims(content):
    """Parse and validate the xAI-constrained claims-and-evidence object."""
    return ClaimsResponse.model_validate_json(content).model_dump(mode="json")


def final_content(response, content_chunks, output_format):
    """Return final text without duplicating progressively accumulated structured chunks."""
    if output_format == "claims":
        response_content = getattr(response, "content", None)
        if isinstance(response_content, str) and response_content:
            return response_content
        return content_chunks[-1] if content_chunks else ""
    return "".join(content_chunks)


def version_at_least(installed_version, minimum_version):
    """Compare package versions according to PEP 440."""
    try:
        from packaging.version import InvalidVersion, Version
    except ImportError:
        # xai-sdk depends on packaging; an unavailable parser means pip should
        # upgrade the SDK and install its dependencies.
        return False

    try:
        return Version(installed_version) >= Version(minimum_version)
    except InvalidVersion:
        return False


def validate_reasoning_effort(parser, model, reasoning_effort):
    """Reject known model/effort combinations that xAI does not support."""
    if model in {"grok-4.3", "grok-4.3-latest"} and reasoning_effort == "xhigh":
        parser.error(
            "--reasoning-effort xhigh is unavailable for grok-4.3; "
            "use low, medium, or high, or select grok-4.6."
        )


def ensure_sdk():
    try:
        installed_version = version("xai-sdk")
    except PackageNotFoundError:
        installed_version = None

    if installed_version and version_at_least(installed_version, MIN_XAI_SDK_VERSION):
        import xai_sdk
        return xai_sdk

    action = "Installing" if installed_version is None else "Upgrading"
    print(
        f"[grok-research] {action} xai-sdk>={MIN_XAI_SDK_VERSION}...",
        file=sys.stderr,
    )
    import subprocess
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                f"xai-sdk>={MIN_XAI_SDK_VERSION}",
            ],
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print(
            f"Error: Failed to install xai-sdk (exit code {e.returncode}).",
            file=sys.stderr,
        )
        print(
            f"Try manually: pip install --upgrade 'xai-sdk>={MIN_XAI_SDK_VERSION}'",
            file=sys.stderr,
        )
        sys.exit(1)
    import xai_sdk
    return xai_sdk


def main():
    parser = argparse.ArgumentParser(
        description="Agentic research using Grok 4.6 via xAI API (web + X search)"
    )
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument(
        "--tools",
        choices=["web", "x", "both"],
        default="both",
        help="Which search tools to enable (default: both)",
    )
    parser.add_argument(
        "--model",
        default="grok-4.6",
        help="Model to use (default: grok-4.6)",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default="high",
        help="Reasoning effort (default: high). xhigh requires Grok 4.6 or a newer compatible model.",
    )
    parser.add_argument(
        "--no-reasoning",
        action="store_true",
        help="Deprecated: use --reasoning-effort low. Current Grok 4.6 API cannot disable reasoning.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Max agentic turns (limits search depth)",
    )
    parser.add_argument(
        "--profile",
        choices=PROFILE_PROMPTS.keys(),
        default="general",
        help="Research profile (default: general)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["prose", "claims"],
        default="prose",
        help="Output prose or a claims-and-evidence JSON object (default: prose)",
    )
    parser.add_argument(
        "--system",
        type=str,
        default=None,
        help="Optional system prompt appended to the selected research profile",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show tool calls on stderr; reasoning totals remain in the footer",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured JSON (content, citations, usage, tool_calls)",
    )

    args = parser.parse_args()
    query = " ".join(args.query)

    if not args.no_reasoning:
        validate_reasoning_effort(parser, args.model, args.reasoning_effort)

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("Error: XAI_API_KEY environment variable is required.", file=sys.stderr)
        print("Get your API key at: https://console.x.ai/", file=sys.stderr)
        sys.exit(1)

    xai_sdk = ensure_sdk()
    from xai_sdk import Client
    from xai_sdk.chat import user, system
    from xai_sdk.tools import web_search, x_search

    # Build tool list
    tools = []
    if args.tools in ("web", "both"):
        tools.append(web_search())
    if args.tools in ("x", "both"):
        tools.append(x_search())

    # Select model and reasoning effort. Older Grok models used separate
    # "-non-reasoning" slugs; current models use reasoning_effort instead.
    model = args.model
    reasoning_effort = args.reasoning_effort
    if args.no_reasoning:
        print(
            "Warning: --no-reasoning is deprecated and Grok 4.6 cannot disable reasoning; "
            "using --reasoning-effort low instead.",
            file=sys.stderr,
        )
        reasoning_effort = "low"

    # Build chat kwargs
    chat_kwargs = {
        "model": model,
        "tools": tools,
        "include": ["inline_citations", "verbose_streaming"],
        "reasoning_effort": reasoning_effort,
    }
    if args.max_turns is not None:
        chat_kwargs["max_turns"] = args.max_turns
    if args.output_format == "claims":
        # The SDK converts this Pydantic model to xAI's constrained JSON schema.
        chat_kwargs["response_format"] = ClaimsResponse

    client = Client(api_key=api_key, timeout=3600)
    chat = client.chat.create(**chat_kwargs)

    # Apply premise verification and calibrated negative findings to every profile.
    chat.append(system(PROFILE_PROMPTS["general"]))
    if args.profile != "general":
        chat.append(system(PROFILE_PROMPTS[args.profile]))
    if args.output_format == "claims":
        chat.append(system(CLAIMS_SCHEMA_PROMPT))
    if args.system:
        chat.append(system(args.system))

    chat.append(user(query))

    # Stream the response
    start_time = time.time()
    content_parts = []
    tool_calls_log = []

    try:
        for response, chunk in chat.stream():
            # Log tool calls
            for tool_call in chunk.tool_calls:
                tc_info = {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                }
                tool_calls_log.append(tc_info)
                if args.verbose:
                    print(
                        f"\n  🔧 {tc_info['name']}: {tc_info['arguments']}",
                        file=sys.stderr,
                    )

            # Collect content. Reasoning-token progress is intentionally not streamed:
            # terminal redraws can become persistent context noise in agent harnesses.
            if chunk.content:
                content_parts.append(chunk.content)
                if not args.json_output and args.output_format == "prose":
                    print(chunk.content, end="", flush=True)
    except Exception as e:
        print(f"\nError: xAI API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time
    content = final_content(response, content_parts, args.output_format)

    claims = None
    if args.output_format == "claims":
        if not content.strip():
            turn_hint = (
                f" The run was capped at --max-turns {args.max_turns}; retry with a higher limit or omit the flag."
                if args.max_turns is not None
                else " Retry the request; no final structured content was returned."
            )
            print(
                f"\nError: research returned no final claims response after {len(tool_calls_log)} tool calls.{turn_hint}",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            claims = parse_claims(content)
        except ValueError as error:
            print(f"\nError: claims output failed schema validation: {error}", file=sys.stderr)
            sys.exit(1)

    # Gather citations
    citations = list(response.citations) if response.citations else []

    # Gather usage
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "reasoning_tokens": response.usage.reasoning_tokens,
        "total_tokens": response.usage.total_tokens,
        "cached_prompt_text_tokens": response.usage.cached_prompt_text_tokens,
    }

    # Gather tool usage
    tool_usage = {}
    if response.server_side_tool_usage:
        tool_usage = dict(response.server_side_tool_usage)

    if args.json_output:
        output = {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "profile": args.profile,
            "output_format": args.output_format,
            "content": content,
            "claims": claims,
            "citations": citations,
            "usage": usage,
            "tool_usage": tool_usage,
            "tool_calls": tool_calls_log,
            "elapsed_seconds": round(elapsed, 2),
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        if args.output_format == "claims":
            print(json.dumps(claims, indent=2))
        # Print footer with metadata
        print(f"\n\n---")
        print(f"Model: {model} | Profile: {args.profile} | Reasoning effort: {reasoning_effort} | Time: {elapsed:.1f}s")
        print(
            f"Tokens — prompt: {usage['prompt_tokens']}, "
            f"completion: {usage['completion_tokens']}, "
            f"reasoning: {usage['reasoning_tokens']}, "
            f"cached: {usage['cached_prompt_text_tokens']}"
        )
        if tool_usage:
            print(f"Tools used: {tool_usage}")
        if citations:
            print(f"Citations ({len(citations)}):")
            for c in citations[:20]:
                print(f"  {c}")
            if len(citations) > 20:
                print(f"  ... and {len(citations) - 20} more")


if __name__ == "__main__":
    main()
