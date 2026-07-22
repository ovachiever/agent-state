# aime30 anchor set: source verification

Frozen anchor set of 30 AIME problems: 15 from AIME 2024 (I and II), 15 from AIME 2025 (I and II), spread across early, middle, and late positions of each exam. Curated 2026-07-22.

## Methodology

- artofproblemsolving.com hard-blocks non-browser fetchers (Cloudflare 403), so every AoPS page was retrieved as original bytes from its Wayback Machine snapshot (`web.archive.org/web/<timestamp>id_/<url>`). The snapshot URL recorded per item below is the exact document the data was extracted from; the live AoPS URL is given alongside it.
- Problem statements were extracted from each problem page's HTML with LaTeX taken verbatim from image `alt` attributes, then converted to LaTeX-lite plain text (`^` for powers, `sqrt()`, fractions as `a/b`). Two independent parsers were run over every page and their outputs compared to catch extraction corruption. A final automated pass confirmed every numeric literal in the source appears with identical multiplicity in the transcription.
- Every answer was verified against two independent AoPS pages: (A) the exam's Answer Key page, and (B) the final `\boxed{}` answer(s) in the solutions on the problem's own page. All 30 agreed; nothing was dropped.
- Third-source cross-check (beyond the required two): all 30 answers were also compared against the HuggingFace datasets `Maxwell-Jia/AIME_2024` and `yentinglin/aime_2025` via the datasets-server API. All 30 agreed there as well.
- Answers are stored as integers without leading zeros (the Answer Key prints zero-padded three-digit forms, e.g. `033` -> `33`).
- `[asy]` diagrams cannot be carried in plain text. Where a statement references its diagram, the marker `[diagram omitted]` was left in place (aime2024-II-15, aime2025-I-11, aime2025-II-6); purely illustrative unreferenced diagrams were dropped (aime2024-I-5, aime2024-II-8). Every selected problem is fully specified by its text alone.
- One wiki transcription typo was normalized without changing the math: aime2025-I-13 "lines segments" -> "line segments".

## Per-item verification

Source A = AoPS Answer Key page (via the Wayback snapshot listed). Source B = AoPS problem page with boxed solution answer (via the Wayback snapshot listed).

### aime2024-I-1 | answer 204 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_1 (snapshot used: https://web.archive.org/web/20251117231614/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_1)

### aime2024-I-3 | answer 809 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_3 (snapshot used: https://web.archive.org/web/20251118002321/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_3)

### aime2024-I-5 | answer 104 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_5 (snapshot used: https://web.archive.org/web/20250905114955/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_5)

### aime2024-I-7 | answer 540 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_7 (snapshot used: https://web.archive.org/web/20250902234048/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_7)

### aime2024-I-9 | answer 480 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_9 (snapshot used: https://web.archive.org/web/20251118233840/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_9)

### aime2024-I-11 | answer 371 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_11 (snapshot used: https://web.archive.org/web/20251120025656/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_11)

### aime2024-I-13 | answer 110 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_13 (snapshot used: https://web.archive.org/web/20251122104803/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_13)

### aime2024-I-15 | answer 721 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20250901133422/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_15 (snapshot used: https://web.archive.org/web/20251126151718/https://artofproblemsolving.com/wiki/index.php/2024_AIME_I_Problems/Problem_15)

### aime2024-II-2 | answer 236 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_2 (snapshot used: https://web.archive.org/web/20251122215135/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_2)

### aime2024-II-4 | answer 33 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_4 (snapshot used: https://web.archive.org/web/20251117180809/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_4)

### aime2024-II-6 | answer 55 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_6 (snapshot used: https://web.archive.org/web/20251119135803/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_6)

### aime2024-II-8 | answer 127 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_8 (snapshot used: https://web.archive.org/web/20250911161150/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_8)

### aime2024-II-10 | answer 468 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_10 (snapshot used: https://web.archive.org/web/20250912222914/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_10)

### aime2024-II-13 | answer 321 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_13 (snapshot used: https://web.archive.org/web/20251119212512/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_13)

### aime2024-II-15 | answer 315 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250905181609/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_15 (snapshot used: https://web.archive.org/web/20251118201102/https://artofproblemsolving.com/wiki/index.php/2024_AIME_II_Problems/Problem_15)

### aime2025-I-1 | answer 70 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_1 (snapshot used: https://web.archive.org/web/20250819040216/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_1)

### aime2025-I-3 | answer 16 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_3 (snapshot used: https://web.archive.org/web/20251003014629/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_3)

### aime2025-I-5 | answer 279 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_5 (snapshot used: https://web.archive.org/web/20251003014258/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_5)

### aime2025-I-7 | answer 821 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_7 (snapshot used: https://web.archive.org/web/20251003014752/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_7)

### aime2025-I-9 | answer 62 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_9 (snapshot used: https://web.archive.org/web/20251003014732/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_9)

### aime2025-I-11 | answer 259 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_11 (snapshot used: https://web.archive.org/web/20250819040219/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_11)

### aime2025-I-13 | answer 204 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_13 (snapshot used: https://web.archive.org/web/20251021155323/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_13)

### aime2025-I-15 | answer 735 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key (snapshot used: https://web.archive.org/web/20251003014021/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_15 (snapshot used: https://web.archive.org/web/20251003013941/https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_15)

### aime2025-II-2 | answer 49 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_2 (snapshot used: https://web.archive.org/web/20250819205027/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_2)

### aime2025-II-4 | answer 106 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_4 (snapshot used: https://web.archive.org/web/20250819205025/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_4)

### aime2025-II-6 | answer 293 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_6 (snapshot used: https://web.archive.org/web/20250819205028/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_6)

### aime2025-II-8 | answer 610 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_8 (snapshot used: https://web.archive.org/web/20250819202033/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_8)

### aime2025-II-10 | answer 907 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_10 (snapshot used: https://web.archive.org/web/20250819202040/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_10)

### aime2025-II-13 | answer 248 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_13 (snapshot used: https://web.archive.org/web/20250819202031/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_13)

### aime2025-II-15 | answer 240 | sources agree: YES [x]
- Source A (answer key): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key (snapshot used: https://web.archive.org/web/20250819205023/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Answer_Key)
- Source B (problem page, boxed solution answer): https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_15 (snapshot used: https://web.archive.org/web/20250819202042/https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_15)

## Regeneration notes

To extend this set to 60 items later:

- The four exams used here (AIME 2024 I/II, 2025 I/II) still have exactly 30 unused problems, enough for aime60 on their own with the same year balance: 2024 I problems 2, 4, 6, 8, 10, 12, 14; 2024 II problems 1, 3, 5, 7, 9, 11, 12, 14; 2025 I problems 2, 4, 6, 8, 10, 12, 14; 2025 II problems 1, 3, 5, 7, 9, 11, 12, 14.
- Alternatively, pull from AIME 2023 I/II and earlier (all on the AoPS wiki with the same page structure) if broader year coverage is wanted. Note that pre-2024 exams are more heavily represented in model training data; 2024-2025 problems were chosen here partly to reduce contamination.
- Reuse the pipeline: (1) resolve each page's Wayback snapshot via `https://archive.org/wayback/available?url=...`; (2) fetch original bytes with the `id_` timestamp modifier and `curl --compressed`; (3) extract the Problem section, substituting each `<img>` with its `alt` LaTeX BEFORE any other tag stripping is applied to that text (raw `<` inside LaTeX will otherwise be eaten by tag-stripping, this bug was caught on 2025 I Problem 11); (4) verify each answer against both the Answer Key page and the final boxed solution answers, dropping any item where the two disagree; (5) run the numeric-literal preservation check between source extraction and final transcription.
- Keep the JSONL schema identical (`id`, `set`, `problem`, `answer`); a new 60-item file should use `"set": "aime60"` and fresh ids following the `aime<year>-<I|II>-<n>` pattern.
- Prefer problems fully specified by text; if a candidate problem is unintelligible without its diagram, substitute a neighboring position instead.
