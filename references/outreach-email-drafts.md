# Outreach Email Drafts

Use this reference when the user asks to create tailored recruiting or expert
outreach emails from academic-mapping outputs.

## Default Policy

- Default language: English.
- Write drafts only for A/B-grade public professional contacts unless the user
  explicitly changes the policy.
- Add drafts to contact enrichment CSV files as an `email draft` column.
- Leave D/X-grade rows blank unless the user asks for generic institution
  outreach.
- Never invent private details, unverified titles, compensation numbers, client
  names, or contact information.
- Do not use honorifics such as Dr., Prof., Mr., or Ms. unless they are present
  in the supplied evidence.

## Required Inputs

Collect or infer:

- recruiter name and firm;
- client description and confidentiality level;
- role title or mission;
- technical scope;
- value proposition;
- tone and length preference;
- candidate evidence from `talent_rankings.csv`;
- contact rows from `contact_enrichment_*.csv`.

## Neutral Prompt Structure

System role:

```text
You are an expert semiconductor executive-search outreach writer. Write
precise, credible, technically informed, and respectful candidate emails. Do
not invent credentials, compensation numbers, company names, private details,
or contact information. Use only the candidate evidence supplied in the input.
Return valid JSON only with keys subject and email_draft.
```

User prompt:

```text
Write a first-touch English email.

Requirements:
- Make it clear this is a targeted invitation based on the candidate's public
  research, patent, or technical footprint.
- Reference one or two candidate-specific works, topics, or technical themes.
- Connect the candidate's background to the client mission.
- Preserve confidentiality and do not name the client unless explicitly
  provided.
- Mention the value proposition only in the terms supplied by the user.
- Ask whether the candidate would be open to a short confidential conversation.
- Use "Dear {candidate full name}," exactly.
- Sign as {recruiter name}, {firm}.
- Return JSON only: {"subject": "...", "email_draft": "..."}.

Candidate evidence:
{candidate_context_json}

Client context:
{client_context_json}
```

## Quality Gate

Before writing to CSV, check each draft:

- has a subject line;
- uses full-name salutation;
- states targeted invitation or targeted approach;
- mentions the relevant technical domain;
- signs with the recruiter and firm;
- avoids unsupported honorifics;
- avoids NDA or non-disclosure wording unless explicitly requested;
- does not contain placeholders;
- is concise enough for first contact.

## External LLM Use

External LLMs are optional. If used:

- load API keys only from environment variables or a user-supplied local `.env`;
- do not copy secrets into the project;
- do not log keys;
- preserve a deterministic template fallback;
- run the quality gate after model output and repair only wording issues that
  do not change factual claims.
