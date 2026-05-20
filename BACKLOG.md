# Backlog

Wishlist of improvements. Not prioritised, not committed-to.

## Defaults

- **Better out-of-the-box defaults.** 4 steps / CFG 1 is reasonable for Flux but
  wrong for SD-family models. Pick saner defaults, or at least don't bake Flux
  assumptions into the tool signatures.
- **Per-model default overrides.** Configurable defaults keyed by model name
  (steps, CFG, sampler, scheduler, size, etc.) so `generate_image` picks
  sensible values when called with just a prompt.
- **Self-learning defaults.** Capture feedback on generations and let it shape
  the per-model defaults over time — either automatically or as suggestions.
  - Storage lives alongside the explicit per-model overrides in
    `~/.config/webui-forge-maestro/` — same JSON files, same directory. The
    explicit-vs-learned distinction doesn't matter to the user; both are
    "what should this model default to". Personal observations like "model X
    is good for flowers" must never land in this public repo.
  - That config dir should be kept in a separate git repo so it can be
    versioned and roamed; the tool should handle the git plumbing
    automatically (commit on change, pull on read, etc.) rather than forcing
    the user to remember.
  - Need to decide what "feedback" looks like — explicit rating, implicit
    signal (kept vs. discarded), or both.

## Output management

- **Caller-controlled subfolders.** Let `generate_image` (and friends) accept
  an output subfolder so a batch of flower tests lands in
  `output/flowers/` automatically, rather than one flat dump.

## Workflow

- **Pull before working.** Operational reminder rather than a feature: start
  sessions with `git pull origin main` so local work isn't built on stale
  state.
