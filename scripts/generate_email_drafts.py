from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = """You are an expert executive-search outreach writer for technical and academic talent.
Write precise, credible, technically informed, and respectful candidate emails.
Do not invent credentials, compensation numbers, company names, private details,
or contact information. Use only the candidate evidence supplied in the input.
Return valid JSON only with keys subject and email_draft."""


USER_PROMPT = """Write a first-touch English email.
Requirements:
- Make it clear this is a targeted invitation based on the candidate's public research, patent, or technical footprint.
- Reference one or two candidate-specific works, topics, or technical themes.
- Connect the candidate's background to the client mission.
- Preserve confidentiality and do not name the client unless explicitly provided.
- Mention the value proposition only in the terms supplied by the user.
- Ask whether the candidate would be open to a short confidential conversation.
- Use "Dear {candidate_full_name}," exactly. Do not use Dr., Prof., Mr., or Ms. unless explicitly supplied.
- Do not mention NDA, non-disclosure agreement, relocation, visa, or compensation numbers unless explicitly supplied.
- Keep the body around 150-220 words.
- Sign as {recruiter}, {firm}.
Return JSON only:
{{"subject": "...", "email_draft": "..."}}"""


def load_dotenv(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path or not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
        os.environ.setdefault(key.strip(), value)
    return values


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def compact(value: str, limit: int = 96) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def load_rankings(path: Path) -> dict[str, dict[str, str]]:
    return {row["person"]: row for row in read_csv(path)}


def candidate_context(contact: dict[str, str], ranking: dict[str, str] | None, client: dict[str, str]) -> dict[str, Any]:
    ranking = ranking or {}
    return {
        "person": contact.get("person", ""),
        "rank": contact.get("rank", ""),
        "organization": contact.get("organization", ""),
        "contact_grade": contact.get("grade", ""),
        "contact_type": contact.get("contact_type", ""),
        "contact_source_url": contact.get("source_url", ""),
        "ranking_score": ranking.get("score", ""),
        "works_count": ranking.get("works_count", ""),
        "topics_count": ranking.get("topics_count", ""),
        "collaborators_count": ranking.get("collaborators_count", ""),
        "topics": split_semicolon(ranking.get("topics", ""))[:8],
        "works": split_semicolon(ranking.get("works", ""))[:4],
        "collaborators_sample": split_semicolon(ranking.get("collaborators", ""))[:6],
        "client_context": client,
    }


def template_draft(context: dict[str, Any], recruiter: str, firm: str) -> dict[str, str]:
    person = context["person"]
    client = context["client_context"]
    topics = context.get("topics") or [client.get("technical_scope") or "the target technical area"]
    works = context.get("works") or []
    topic_phrase = ", ".join(topics[:3])
    if works:
        evidence_sentence = (
            f'I noticed your work on "{compact(works[0])}", which sits close to {topic_phrase}.'
        )
    else:
        evidence_sentence = (
            f"Your public technical footprint around {topic_phrase} stood out in a recent mapping exercise."
        )
    subject = f"Targeted invitation: {client.get('role', 'technical leadership opportunity')}"
    body = f"""Dear {person},

I am {recruiter} from {firm}. I am reaching out with a targeted invitation after reviewing your public research and technical footprint.

{evidence_sentence} Your broader work appears relevant to a confidential search I am supporting for {client.get('client_description', 'a leading organization')}.

The role is focused on {client.get('mission', client.get('technical_scope', 'a strategic technical build-out'))}. Given your background with {context.get('organization') or 'your current organization'}, I thought it would be more appropriate to approach you directly rather than send a generic market message.

{client.get('value_proposition', 'The opportunity may provide a meaningful platform for the right mutual fit.')}

Would you be open to a short confidential conversation to compare the opportunity with your current research and career priorities?

Best regards,
{recruiter}
{firm}"""
    return {"subject": subject, "email_draft": body}


def normalize_base_url(raw: str | None) -> str:
    base = (raw or "https://api.minimaxi.com/v1").strip().rstrip("/")
    suffix = "/chat/completions"
    if base.endswith(suffix):
        return base[: -len(suffix)]
    return base


def call_llm(context: dict[str, Any], env_path: Path | None, timeout: int) -> dict[str, str]:
    vals = load_dotenv(env_path)
    key = (
        vals.get("MINIMAX_API_KEY")
        or vals.get("LLM_API_KEY")
        or vals.get("OPENAI_API_KEY")
        or os.environ.get("MINIMAX_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key:
        raise RuntimeError("Missing API key in environment or --env file.")
    model = vals.get("MINIMAX_REASONING_MODEL") or vals.get("MODEL") or os.environ.get("MODEL") or "MiniMax-M3"
    base_url = normalize_base_url(
        vals.get("MINIMAX_REASONING_BASE_URL")
        or vals.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
    )
    endpoint = f"{base_url}/chat/completions"
    client = context["client_context"]
    prompt = USER_PROMPT.format(candidate_full_name=context["person"], recruiter=client["recruiter"], firm=client["firm"])
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": prompt
                + "\n\nCandidate and client evidence:\n"
                + json.dumps(context, ensure_ascii=False),
            },
        ],
        "temperature": 0.35,
        "thinking": {"type": "disabled"},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {detail[:500]}") from exc
    return parse_json_response(data["choices"][0]["message"]["content"])


def parse_json_response(content: str) -> dict[str, str]:
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise
        data = json.loads(cleaned[start : end + 1])
    return {
        "subject": str(data.get("subject", "")).strip(),
        "email_draft": str(data.get("email_draft", "")).strip(),
    }


def repair_draft(context: dict[str, Any], draft: dict[str, str]) -> dict[str, str]:
    person = context["person"]
    body = draft.get("email_draft", "").strip()
    subject = draft.get("subject", "").strip()
    body = re.sub(r"Dear\s+(?:Dr\.|Prof\.|Mr\.|Ms\.)\s+[^,\n]+,", f"Dear {person},", body)
    body = re.sub(r"^Dear\s+[^,\n]+,", f"Dear {person},", body)
    if not body.startswith(f"Dear {person},"):
        body = f"Dear {person},\n\n{body}"
    body = re.sub(r"\bunder NDA\b", "once there is mutual interest", body, flags=re.IGNORECASE)
    body = re.sub(r"\ban NDA\b", "a later confidential discussion", body, flags=re.IGNORECASE)
    body = re.sub(r"\bNDA\b", "confidential discussion", body)
    if "targeted" not in (subject + " " + body).lower():
        paragraphs = body.split("\n\n")
        paragraphs.insert(1, "This is a targeted invitation based on your public technical footprint, not a general recruitment message.")
        body = "\n\n".join(paragraphs)
    if "targeted" not in subject.lower():
        subject = "Targeted invitation: " + subject
    draft["subject"] = subject
    draft["email_draft"] = body
    return draft


def validate_draft(person: str, recruiter: str, firm: str, draft: dict[str, str]) -> list[str]:
    issues = []
    body = draft.get("email_draft", "")
    subject = draft.get("subject", "")
    if not subject:
        issues.append("missing subject")
    if person.lower() not in body.lower():
        issues.append("candidate full name not used")
    for token in ["targeted", recruiter, firm]:
        if token.lower() not in (subject + " " + body).lower():
            issues.append(f"missing {token}")
    if re.search(r"Dear\s+(Dr\.|Prof\.|Mr\.|Ms\.)", body):
        issues.append("unsupported honorific")
    if re.search(r"\bNDA\b|non-disclosure agreement", body, flags=re.IGNORECASE):
        issues.append("mentions NDA")
    if any(marker in body for marker in ["{", "}", "[", "]"]):
        issues.append("contains placeholder-like characters")
    return issues


def build_client(args: argparse.Namespace) -> dict[str, str]:
    return {
        "recruiter": args.recruiter,
        "firm": args.firm,
        "client_description": args.client_description,
        "role": args.role,
        "mission": args.mission,
        "technical_scope": args.technical_scope,
        "value_proposition": args.value_proposition,
        "confidentiality": args.confidentiality,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Add tailored outreach email drafts to contact enrichment CSV files.")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--contact-csv", type=Path, action="append", required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--provider", choices=["template", "llm"], default="template")
    parser.add_argument("--env", type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-suffix", default="email_drafts")
    parser.add_argument("--recruiter", default="Marcus Zhu")
    parser.add_argument("--firm", default="Michael Page")
    parser.add_argument("--client-description", default="a confidential client")
    parser.add_argument("--role", default="technical expert opportunity")
    parser.add_argument("--mission", default="a strategic technical build-out")
    parser.add_argument("--technical-scope", default="the mapped technical domain")
    parser.add_argument("--value-proposition", default="The opportunity may provide a meaningful platform for the right mutual fit.")
    parser.add_argument("--confidentiality", default="Keep the client name confidential in the first email.")
    args = parser.parse_args()

    project = args.project.resolve()
    rankings_path = args.rankings if args.rankings.is_absolute() else project / args.rankings
    rankings = load_rankings(rankings_path)
    client = build_client(args)
    all_drafts: dict[str, dict[str, str]] = {}

    for contact_arg in args.contact_csv:
        contact_path = contact_arg if contact_arg.is_absolute() else project / contact_arg
        rows = read_csv(contact_path)
        fieldnames = list(rows[0].keys()) if rows else []
        if "email draft" not in fieldnames:
            fieldnames.append("email draft")
        for row in rows:
            grade = row.get("grade", "").strip().upper()
            person = row.get("person", "").strip()
            if grade not in {"A", "B"} or not person:
                row["email draft"] = row.get("email draft", "")
                continue
            if person not in all_drafts:
                context = candidate_context(row, rankings.get(person), client)
                if args.provider == "llm":
                    draft = call_llm(context, args.env, args.timeout)
                    time.sleep(0.3)
                else:
                    draft = template_draft(context, args.recruiter, args.firm)
                draft = repair_draft(context, draft)
                draft["quality_issues"] = "; ".join(validate_draft(person, args.recruiter, args.firm, draft))
                all_drafts[person] = draft
                print(f"{args.provider}: {person} issues={draft['quality_issues'] or 'none'}")
            draft = all_drafts[person]
            if draft.get("email_draft"):
                row["email draft"] = f"Subject: {draft.get('subject', '')}\n\n{draft['email_draft']}"
        target = contact_path if args.write else contact_path.with_name(contact_path.stem + f"_{args.output_suffix}.csv")
        write_csv(target, rows, fieldnames)
        print(f"Wrote {target}")

    out_json = project / "outputs" / f"email_drafts_{args.provider}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(all_drafts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
