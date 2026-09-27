# AI Usage

This entire prototype (gateway, signals/risk/policy, decoys, Model DNA,
collective immunity, dashboard, simulator, eval, and this documentation) was
built with Claude Code, working phase by phase from a written spec, with a
human stopping to review and approve after each phase before the next one
started.

## How it was used

- **Phase-gated build.** The work was split into seven phases (repo review,
  gateway/firewall, signals/risk/policy, decoys/Model DNA, collective
  immunity, dashboard/simulator, eval/docs), each requiring explicit human
  sign-off before continuing. Nothing was auto-approved across phase
  boundaries.
- **Real verification at every phase, not just code review.** Every phase
  ended with the actual server started, real HTTP requests sent (via curl or
  the simulator scripts), and the SQLite database inspected directly to
  confirm the claimed behavior actually happened — not just that the code
  compiled or that unit tests passed in isolation.
- **A real browser check for the dashboard**, not just curl: the dashboard
  (Phase 6) was opened in an actual Chrome browser via browser automation,
  and every button (Send client, Send bot, Send hacker, Auto-play, Scan
  suspect model, Attack Customer B, Reset) was clicked and its visible effect
  confirmed, rather than assuming the JavaScript worked because the HTML
  looked right.
- **License and scope discipline for the third-party dependency.** Before
  writing any firewall code, the referenced AISecurity repo's README, Guard
  Lab README, sentinel-core README, `bindings.rs`, and license/NOTICE files
  were read to confirm the exact API (`EngineRegistry().analyze_patterns`),
  the pinned commit, and the project's own stated limits (Linux x86-64 /
  Python 3.11 only, historical/non-revalidated accuracy figures) before any
  code depended on it.

## What was checked or fixed along the way

These are real defects found by actually running the system, not
hypothetical review comments:

1. **Fingerprint design bug (Phase 3).** The original fingerprint hashed in
   the account's own API key, so two different accounts could never share a
   fingerprint — silently breaking the "linked accounts" signal that the
   whole system depends on to catch multi-account bot farms. Found by
   deliberately testing two accounts from the same IP/UA and noticing the
   linked signal stayed at zero. Fixed by hashing only IP + User-Agent.
2. **A genuine spec tension, surfaced rather than silently resolved (Phase
   3).** With the risk weights exactly as specified, `rate + templates` alone
   could reach 45/100 — enough to punish a legitimate high-volume,
   single-template caller (the "Dev CI must not be punished" requirement)
   with zero contribution from the signals that actually indicate
   distillation. This was found by literally running 25 Dev CI requests and
   watching it get throttled, not by reasoning about the formula in the
   abstract. Flagged to the human with three options; the chosen fix
   (`threshold_slow` 40 → 50) was verified by re-running the same 25 requests
   and confirming Dev CI never got punished.
3. **Clone tie-break bug (Phase 4).** The clone stand-in's nearest-neighbor
   lookup picked whichever harvested answer SQLite happened to return first
   on a similarity tie, which turned out to be an old *real* answer instead
   of the intended *decoy* one — found by manually querying `/clone` for a
   known trap question and getting the wrong answer back. Fixed with an
   exact-match-first lookup strategy, then re-verified against the actual
   Model DNA verifier output (4/4 trap matches, p ≈ 3.6e-15).
4. **Bot/topic indexing collision (Phase 6).** Because the bot-account list
   and the topic list both happened to have length 8, the initial indexing
   scheme locked every bot to exactly one topic forever, crushing the
   topic-coverage signal the traffic was supposed to exercise. Found by
   inspecting the actual risk breakdown after a bot run and seeing coverage
   stuck near zero, not by reading the code and assuming it was right.
5. **Connection-reuse performance bug (Phase 6).** The simulator opened a
   fresh HTTP connection per request; 120 requests took 20 seconds. Found by
   timing an actual run. Fixed with a persistent `httpx.Client`, cutting the
   same run to 2.5 seconds — verified by timing it again.
6. **An honest, unfixed cost, not hidden.** Splitting bot traffic across 8
   accounts (the realistic evasion tactic) genuinely takes ~110-120 total
   requests before per-account signals alone would cross the decoy
   threshold — this was measured, not assumed, and is documented as-is in
   `app/demo_actions.py` and the README rather than quietly tuned away by
   picking easier demo parameters.

## Second pass: a deliberate deeper bug hunt after the build was "done"

After all seven phases were complete and the app was running, a further
adversarial pass was done specifically to find what a normal build-and-test
cycle might miss — probing edge cases (empty/malformed input, large payloads,
concurrency, header spoofing) rather than re-reading the same code. This
found two more real issues, both fixed and covered by new regression tests:

7. **Origin fingerprint spoofing.** The gateway trusted the client-supplied
   `X-Forwarded-For` and `User-Agent` headers unconditionally with no
   validation against the actual connection. Verified live: two requests
   from the same account claiming two different IPs got two different risk
   profiles, with nothing tying the claim back to reality. This meant any
   client could (a) evade the linked-accounts signal — the system's
   strongest defense against multi-account bot farms — by rotating a fake
   IP per request, or worse, (b) frame an innocent customer by spoofing
   their known IP while sending bot-like traffic, causing that innocent IP
   to be flagged and blocked at every other tenant via collective immunity.
   Fixed with a `PUARO_TRUST_FORWARDED_HEADERS` setting (default `true`,
   required for the local demo/simulator to work at all) that falls back to
   the real TCP peer address when `false`. User-Agent is not part of this
   fix — it's inherently client-controlled in HTTP with or without a proxy,
   so there was no trust boundary there to restore.
8. **No request size limit.** A 2 MB JSON payload was accepted and fully
   processed (firewall scan, signal computation, SQLite write) in under half
   a second with zero rejection — verified by actually sending one and
   timing it, not by inspecting the code for a limit that might be missing
   elsewhere. Fixed with a `Content-Length`-based 413 check
   (`PUARO_MAX_REQUEST_BYTES`, default 256 KiB), with the caveat — stated in
   `SECURITY.md` — that a chunked request without `Content-Length` can still
   bypass an application-level check alone.

Both fixes were verified against the live server (not just unit tests): the
oversized-payload rejection was re-tested with the same 2 MB payload that
originally got through, and the fingerprint fix was checked by confirming
that the full demo (`scripts/run_demo.py`) still works identically with the
default trust setting, since the simulator legitimately depends on that
trust to simulate multiple origins from one machine.

## What a human should still check

- The risk-score weights and thresholds were tuned against exactly one
  scenario (Dev CI). They have not been validated against a broader or
  adversarial population — see the Limits section of `README.md`.
- The native `sentinel-core` firewall path was never actually exercised in
  this build (the dev machine is Windows; that dependency's own docs only
  cover Linux x86-64). The regex fallback is what's tested throughout.
- No independent security review has been done on this code.
