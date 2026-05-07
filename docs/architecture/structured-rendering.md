# Structured Rendering and Proposal Modes

Structured rendering means OTerminus executes typed command-family arguments rendered by Python,
rather than trusting arbitrary shell strings.

## Supported proposal modes

OTerminus supports exactly two first-class proposal modes.

### Structured mode

Structured mode is the preferred normal path for supported capabilities. A structured proposal
contains:

- `mode=structured`
- `command_family`
- typed `arguments`

Python validates the arguments against family-specific schemas, renders a deterministic display
command, and builds the `argv` passed to execution. The structured renderer is authoritative; if
legacy command text is present on a structured proposal, validation ignores it in favor of
`command_family + arguments`.

### Experimental mode

Experimental mode is a constrained fallback for single-command proposals that cannot yet be
represented safely with structured arguments. An experimental proposal may contain command text, but
it is still:

- limited to curated command families and maturity policy
- rejected for shell chaining, pipelines, redirection, substitution, and unsupported shapes
- checked against risk policy and allowed roots
- shown in preview before execution
- subject to stronger confirmation

Experimental mode is not a shortcut around registry, validator, or renderer design. If a workflow is
common and safe enough to model, contributors should add structured schema/rendering support instead
of relying on experimental fallback.

## Structured flow

1. Proposal contains `mode=structured`, `command_family`, and typed `arguments`.
2. Arguments are validated against family-specific schemas.
3. Renderer builds deterministic `argv` and display command string.
4. Validator re-checks rendered output against policy/allowlists.
5. User sees a preview and must confirm before execution.

## Benefits

- deterministic command output
- reduced prompt-injection surface
- predictable validation behavior
- cleaner diffs in eval fixtures

## Compatibility handling

Legacy `"mode": "raw"` payloads may be accepted only as internal transitional compatibility at parse
boundaries. They are normalized to `experimental` before downstream validation/rendering and are not
a public proposal mode.
