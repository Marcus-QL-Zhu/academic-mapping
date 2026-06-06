# Contact Enrichment

Use this reference when the user asks to find candidate emails, phones, contact details, outreach routes, or sourcing contact information from an academic mapping candidate list.

## Allowed Contact Grades

- **A**: Person-specific public professional contact on an official institutional page, publisher page, paper PDF, PubMed/PMC affiliation, patent page, official lab page, or conference speaker page.
- **B**: Person-specific public professional contact on a personal academic homepage, CV, Google Sites lab page, GitHub profile, ResearchGate profile, ORCID public record, or other professional profile.
- **D**: Generic public professional contact for a lab, department, institution, company office, or switchboard when no person-specific contact is found.
- **X**: No usable public professional contact found.

## Disallowed Methods

Do not provide or run workflows for:

- private mobile-number search or reverse lookup;
- data-broker or people-search sites;
- leaked data, breach data, paste sites, deep web, or dark web;
- account registration/enumeration to test whether an email or phone is registered;
- contact sync or social-app phone discovery;
- guessing personal emails or phone numbers without public evidence.

If a phone number appears on an official professional source, such as an institution profile, lab page, office directory, conference bio, or paper PDF, it may be recorded with source evidence. Treat generic office or company switchboard numbers as D grade unless clearly person-specific.

## Search Patterns

Run targeted searches using candidate name, organization, work title, DOI, and domain:

```text
"Person Name" "Organization"
"Person Name" "Work Title"
"Person Name" email
"Person Name" "@institution-domain"
"Person Name" filetype:pdf
"Person Name" CV filetype:pdf
site:institution-domain "Person Name"
site:institution-domain "Person Name" email
site:institution-domain "Person Name" phone
site:institution-domain "Person Name" directory
"Work Title" "corresponding author"
"Work Title" "@"
"DOI" "@"
```

For patents:

```text
"Person Name" "patent"
"Person Name" "Patent Title"
inventor:"Person Name" assignee:"Organization"
```

## Output Schema

Write contact enrichment outputs under `outputs/`:

```text
contact_enrichment_topN.csv
```

Columns:

```text
rank,person,organization,contact_type,contact_value,grade,source_url,confidence,notes
```

## Verification

Before reporting contact results:

- Check that every A/B contact has a source URL tying the contact to the person.
- Check that every D contact is clearly generic and labeled as such.
- Keep source snippets short; do not copy long page text.
- State that public availability does not remove privacy, transparency, or opt-out obligations for recruiting use.
