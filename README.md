# git_conflict_resolver

This application uses a team of AI agents, built with crewAI, to automatically detect and resolve git conflicts.

## How it works

The application is orchestrated by a `manager` agent that oversees the entire conflict resolution process. The process is as follows:

1.  **Conflict Detection**: The `conflict_detector` agent uses the `GitConflictFinderTool` to identify files with merge conflicts.
2.  **Conflict Resolution**: The `conflict_resolver` agent then uses the `GitConflictResolverTool` to resolve the identified conflicts.
3.  **Summary**: Finally, the `summary_reporter` agent provides a summary of the resolved conflicts.

This hierarchical process, managed by the `manager` agent, ensures that git conflicts are handled efficiently and autonomously. The application is powered by a Gemini Large Language Model.

