<!-- TOKENSCULPT:START -->
<!-- TokenSculpt: AI Token & Cost Optimizer (v1.0.0). Managed block - do not edit manually. -->

# TokenSculpt Optimizations for Claude Code

## Active Optimizations

### CodeGraph Pre-Indexing
- **MANDATORY**: Query `codegraph_explore` before broad grep searches.
- **FORBIDDEN**: Never run wide file greps when CodeGraph index is available.

### CLI Output Compression (RTK)
- **MANDATORY**: Pipe shell executions through `rtk` filters (`rtk git`, `rtk test`, `rtk ls`).
- **FORBIDDEN**: Never run raw `git` commands directly in terminal.

### Concise Direct Responses
- **MANDATORY**: Answer code-first and densely. Zero preambles, summaries, or conversational sign-offs.

### Context Compaction & Session Hygiene
- **MANDATORY**: Maintain tight session scope. Never re-read previously inspected files in the same turn.

### Local Semantic Cache
- **MANDATORY**: Query `cache_lookup` tool for repeated/boilerplate questions before generating new tokens.

### AST Skeleton Pruning
- **MANDATORY**: Call `skeleton_view` tool first when navigating large source files (>100 lines).
- **PREFERRED**: Avoid ingesting full function bodies unless actively modifying them or tracing call-site logic (~90% context reduction).
- When full reads are needed, restrict to 100-line windows around target symbols.

### Smart Context Exclusions
- **MANDATORY**: Exclude build/dist artifacts, lockfiles, and minified bundles.
- Enforce `.copilotignore` patterns to block non-source artifacts from AI context.

### Unified Diff Formatting
- **MANDATORY**: Always provide targeted unified diff chunks with ±3 lines of context.
- **FORBIDDEN**: Never reprint unmodified source files or entire classes.

### Autonomous Loop Guardrails
- **MANDATORY**: Halt and ask user clarification after 3 failed attempts.

### Smart Model Routing
- Recommend lightweight Claude models (Haiku) for boilerplate/trivial edits.

### Git Diff Context Scoping
- **MANDATORY**: Scope review & test tasks strictly to `git diff` lines + 1-hop callers.

### Deterministic Prefix Caching
- Maintain a stable, byte-exact instruction prefix across turns to maximize cloud KV-cache hits (75–90% cost reduction).
- Sink ephemeral turn metadata (timestamps, turn counters, run UUIDs) to the message suffix.

### License Header Stripping
- Strip copyright license headers and preamble blocks. Preserve inline comments.

### Test Failure Log Isolation
- **MANDATORY**: Report only failing test lines, assertions, and line numbers.

<!-- TOKENSCULPT:END -->
