# Gold Standard Chats — Discovery Audit

**Audit date:** 2026-05-22
**Auditor:** Claude Code (discovery pass only — no files modified)
**Scope:** All 23 `gc-*.json` files in `gold_standard/chats/`

---

## Summary Table

| Status | Count | Chat IDs |
|--------|-------|----------|
| PDF found, clean unique mapping | 19 | gc-001–012, gc-016–023 (excl. gc-014, gc-015) |
| PDF found — DUPLICATE SOURCE (same PDF as another gc-*) | 2 | gc-014 (= gc-013), gc-015 (= gc-002) |
| Raw source NOT FOUND | 0 | — |
| PDF in repo with NO corresponding gc-*.json | 1 | `Jay_ChatGPT2.pdf` |

**All 23 annotations are complete: 8/8 bands scored, 8/8 dimension notes populated, scorer = sangillence.**

**All 23 turns are placeholders.** Every file has exactly one synthetic turn (`role: user`) with a `[Full transcript not pasted into this file. Chat source: ...]` description. No real conversation turns exist in any gc-*.json yet.

**All raw sources are PDFs** located in `gold_standard/chats/` alongside the JSON files. No markdown exports, plain-text files, HTML, or screenshots were found anywhere in the repo.

---

## FLAGS — RESOLVED 2026-05-22

### FLAG 1 — gc-014 source reference corrected to Jay_ChatGPT2
gc-014's placeholder previously said `Jay_ChatGPT1` (same as gc-013) — a copy-paste error. **Fixed:** `turns[0].content` updated to reference `Jay_ChatGPT2.pdf`. Bands are retained as provisional. Notes in gc-014 still reflect Jay_ChatGPT1 content and **must be replaced** by sangillence after Jay_ChatGPT2.pdf turns are extracted — this is the one remaining scoring task before Phase 1.

### FLAG 2 — gc-002 and gc-015 confirmed as two independent scorings
Notes are genuinely different (different specific student behaviours observed). gc-015 is a second independent scoring of the same Pratik session — valid for IRR analysis. **Fixed:** `turns[0].content` updated to say "session 2" and note the relationship to gc-002. No bands or annotation fields were changed.

---

## Per-Chat Detail

### gc-001
- **Raw source:** `Career - Google PM Strategy.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=low, PR=low, AUI=mid, EC=low, CS=mid, CD=low, ES=not_applicable, CA=low
- **Stated turn count:** not stated in placeholder
- **Topic:** Career strategy session — Google PM role, APM acceptance rates, profile positioning, transition planning
- **Notes:** Clean unique mapping. Placeholder text references PDF by name.

---

### gc-002
- **Raw source:** `Pratik_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=low, PR=mid, AUI=mid, EC=low, CS=mid, CD=low, ES=not_applicable, CA=low
- **Topic:** Academic presentation — PPT, IEEE base paper on micro-Doppler signal processing, CNN vs. Transformer
- **Notes:** SEE FLAG 2 — gc-015 references the same PDF with identical bands.

---

### gc-003
- **Raw source:** `Ritesh_Gemini.pdf` — found in `gold_standard/chats/`
- **Platform:** gemini
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=mid, ES=not_applicable, CA=high
- **Topic:** Physics exam prep — Lorentz transformations, time dilation, relativistic energy, spacetime interval; used text + math + slide images
- **Notes:** Clean unique mapping. Highest-scoring chat in the set — useful as a "Orchestrator" archetype anchor.

---

### gc-004
- **Raw source:** `Kartikeya_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=mid, PR=high, AUI=high, EC=low, CS=high, CD=mid, ES=low, CA=high
- **Topic:** Cybersecurity presentation — phishing, ransomware, brute force scripts, ZIP cracking, fault injection; includes Python/Flask code generation
- **Notes:** Clean unique mapping. One of two chats with ES=low (non-null ethics flag).

---

### gc-005
- **Raw source:** `Darshit_Chat1.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=mid, ES=not_applicable, CA=high
- **Topic:** Reinforcement learning tutoring — TD Learning, Monte Carlo Q-values, gridworld calculations, exam prep
- **Notes:** Clean unique mapping. Part of a three-session Darshit series (gc-005, gc-006, gc-007 from same person).

---

### gc-006
- **Raw source:** `Darshit_Chat2.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=mid, ES=not_applicable, CA=high
- **Topic:** RL tutoring session 2 — TD Learning, Monte Carlo, Q-learning, off-policy, professor-style question generation
- **Notes:** Clean unique mapping.

---

### gc-007
- **Raw source:** `Darshit_Chat3.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=mid, CS=high, CD=low, ES=not_applicable, CA=high
- **Topic:** ML revision — Naive Bayes, Laplace smoothing, LMS, Kernel methods, SVMs, notes preparation
- **Notes:** Clean unique mapping. EC drops to mid (vs high in gc-005/006) — useful intra-person variation.

---

### gc-008
- **Raw source:** `Abhishek_1.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=mid, PR=mid, AUI=high, EC=low, CS=mid, CD=low, ES=not_applicable, CA=mid
- **Topic:** HCI exam prep — dense notes to explanations, case-based questions, structured study material
- **Notes:** Clean unique mapping. Part of two-session Abhishek series.

---

### gc-009
- **Raw source:** `Abhishek_2.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=low, ES=not_applicable, CA=high
- **Topic:** ML exam prep — Lagrange duality, SVMs, feature mappings, SMO, derivation notes
- **Notes:** Clean unique mapping. Significantly higher scores than gc-008 — same person, different session quality.

---

### gc-010
- **Raw source:** `Advitya_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=mid, PR=mid, AUI=mid, EC=low, CS=mid, CD=low, ES=mid, CA=low
- **Topic:** Coursera Intro to AI quiz assistance, responsible AI topics, personal study scheduling
- **Notes:** Clean unique mapping. One of two chats with ES=mid — useful for ethics-sensitive calibration.

---

### gc-011
- **Raw source:** `Akshita_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=mid, PR=mid, AUI=mid, EC=low, CS=mid, CD=low, ES=not_applicable, CA=mid
- **Topic:** Digital marketing strategy for a jewellery business — target audience, tools, weekly action plan
- **Notes:** Clean unique mapping.

---

### gc-012
- **Raw source:** `Bharath_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=high, ES=not_applicable, CA=high
- **Topic:** Technical architecture critique — custom coding-agent framework vs. Claude Code; TAPES, execution-feedback loops, routing, validation policy
- **Notes:** Clean unique mapping. The only chat with CD=high (all others are mid or low) — unique signal for Creative Divergence calibration. Perfect 8/8 highs excluding ES.

---

### gc-013
- **Raw source:** `Jay_ChatGPT1.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=low, PR=low, AUI=mid, EC=low, CS=mid, CD=low, ES=not_applicable, CA=low
- **Topic:** HCI exam prep — uploaded PDFs converted into chapter explanations, summaries, rapid study notes
- **Notes:** SEE FLAG 1 — gc-014 is an exact duplicate of this entry (identical source, bands, and notes).

---

### gc-014
- **Raw source:** `Jay_ChatGPT1.pdf` — found in `gold_standard/chats/` — **SAME AS gc-013**
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes (IDENTICAL to gc-013)
- **Bands:** AL=low, PR=low, AUI=mid, EC=low, CS=mid, CD=low, ES=not_applicable, CA=low
- **Topic:** Same as gc-013
- **Notes:** SEE FLAG 1 — this is an exact duplicate. Likely accidental copy. `Jay_ChatGPT2.pdf` exists in repo with no corresponding entry.

---

### gc-015
- **Raw source:** `Pratik_ChatGPT.pdf` — found in `gold_standard/chats/` — **SAME AS gc-002**
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=low, PR=mid, AUI=mid, EC=low, CS=mid, CD=low, ES=not_applicable, CA=low (identical to gc-002)
- **Topic:** Same as gc-002 (Pratik micro-Doppler; notes are slightly rephrased but same substance)
- **Notes:** SEE FLAG 2 — bands match gc-002 exactly. Notes are minor rephrases. No second Pratik PDF in repo.

---

### gc-016
- **Raw source:** `Puransh_Gemini.pdf` — found in `gold_standard/chats/`
- **Platform:** gemini
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=high, ES=not_applicable, CA=high
- **Topic:** Calculus and kinematics tutoring — limits, derivatives, first principles, average velocity, syllabus-aligned reasoning
- **Notes:** Clean unique mapping. Second chat with CD=high alongside gc-012.

---

### gc-017
- **Raw source:** `RamKrishna_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=mid, CS=high, CD=low, ES=not_applicable, CA=high
- **Topic:** Wireless communications exam prep — handwritten derivations, multipath propagation, Rayleigh fading, SNR calculations
- **Notes:** Clean unique mapping.

---

### gc-018
- **Raw source:** `Shreyas_Gemini.pdf` — found in `gold_standard/chats/`
- **Platform:** gemini
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=high, AUI=high, EC=high, CS=high, CD=mid, ES=not_applicable, CA=high
- **Topic:** Wireless comms + random processes exam prep — handwritten notes, derivations, omission auditing, master document
- **Notes:** Clean unique mapping. Third Gemini chat alongside gc-003 and gc-016.

---

### gc-019
- **Raw source:** `Shreyash_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=high, PR=mid, AUI=high, EC=high, CS=high, CD=low, ES=not_applicable, CA=high
- **Topic:** Game theory + RL tutoring — Walrasian equilibrium, the core, Monte Carlo rules, graph-to-text problem framing
- **Notes:** Clean unique mapping.

---

### gc-020
- **Raw source:** `Simran_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=low, PR=low, AUI=low, EC=low, CS=low, CD=low, ES=not_applicable, CA=low
- **Topic:** CS/cybersecurity lookup — Kruskal/Prim algorithms, SQL injection, XSS definitions
- **Notes:** Clean unique mapping. Only chat with AUI=low — the only pure "lookup" behaviour in the set. Useful as the low-end anchor across all dimensions.

---

### gc-021
- **Raw source:** `Yatendra_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=mid, PR=mid, AUI=high, EC=mid, CS=high, CD=mid, ES=not_applicable, CA=high
- **Topic:** Civil engineering docs + materials research — certificate drafting, image-to-table, graphical abstract, hydrogen-storage ideas
- **Notes:** Clean unique mapping.

---

### gc-022
- **Raw source:** `rahul_chatgpt.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=mid, PR=high, AUI=high, EC=mid, CS=high, CD=mid, ES=not_applicable, CA=high
- **Topic:** Materials-science manuscript prep — cover letters, highlights, ATK/VNL scripting, defect-engineering, graphical abstract, conclusion
- **Notes:** Clean unique mapping. Note: filename uses lowercase `rahul` while all others use TitleCase — inconsistent but not a blocker.

---

### gc-023
- **Raw source:** `Shivansh_ChatGPT.pdf` — found in `gold_standard/chats/`
- **Platform:** chatgpt
- **Annotation status:** Complete — 8/8 bands, 8/8 notes
- **Bands:** AL=low, PR=low, AUI=high, EC=low, CS=mid, CD=high, ES=low, CA=high
- **Topic:** Healthcare app product-building — React fixes, doctor dashboard, video calling, Razorpay, document scanning, admin access, feature ideation
- **Notes:** Clean unique mapping. One of two chats with ES=low. Unusual profile: low AL/PR/EC but high AUI/CD/CA — a "narrow skill" pattern.

---

## Unmatched PDF

### Jay_ChatGPT2.pdf
- **gc-*.json referencing it:** NONE
- **Notes:** Exists in `gold_standard/chats/` but no JSON was created for it. If gc-014 (duplicate of gc-013) is reassigned to this PDF, it would need to be re-scored from scratch.

---

## Observations for next step

1. **The PDF format is uniform** — all 22 raw sources are PDFs. One extraction approach covers everything.

2. **Two decisions are needed before extraction begins** (see FLAGS above). Resolving them determines whether the gold set is 21, 22, or 23 chats going into Phase 1.

3. **Annotation data is safe** — all annotations are in `gc-*.json` and are not in the PDFs. An extractor that only writes to `turns: []` cannot corrupt them.

4. **Stated turn count is not recorded in any placeholder** — the placeholder descriptions describe topics and format but not a specific turn count. Actual turn counts will be discovered from PDF extraction.

5. **Platform split after deduplication:** 20 ChatGPT, 3 Gemini. No Claude.ai chats in the current set.
