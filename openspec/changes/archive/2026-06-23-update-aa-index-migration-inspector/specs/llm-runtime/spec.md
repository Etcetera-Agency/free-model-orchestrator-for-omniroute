## MODIFIED Requirements

### Requirement: Externalized, independently editable prompts

The system SHALL load each LLM site's prompt from its own file under
`llm.prompts_dir` (one file per use case), including the `aa-index-migration`
site. Editing one site's prompt file SHALL NOT require code changes or edits to
any other site's prompt. Every wired LLM site that has a configured prompt file
SHALL pass that file to shared prompt assembly through `LlmSiteConfig.prompt_path`
or an equivalent shared-runtime site configuration, so prompt redaction,
placeholder interpolation, unresolved placeholder cleanup, and prompt length
limits apply uniformly.

#### Scenario: Edit one prompt
- GIVEN an operator edits `prompts/smart-combo-reviewer.md`
- WHEN the reviewer next runs
- THEN it uses the edited prompt and no other site's prompt or behavior changes

#### Scenario: AA migration prompt is loaded from file
- GIVEN an operator edits `prompts/aa-index-migration.md`
- WHEN `aa-index analyze` next prepares the migration Instructor call
- THEN it uses the edited prompt through the shared prompt assembly path
- AND no code change is required for the prompt edit to take effect
