---
description: Prime the agent context with instructions on how to iteratively develop a local website.
argument-hint: [site-name] [portnumber] [instructions]
---

# Arguments


- FOLDER_PATH: sites/$1
- TEST_PATH: tests/$1
- PORT: $2
- SITE_URL: http://localhost:$PORT
- INSTRUCTIONS: $3

# Context

**Inspect the Webpage**

There is a locally hosted static site on $SITE_URL

You are to use Playwright MCP to test and debug the webpage.
- Take screenshots to visually inspect what is going on especially with Deck.GL, Plotly and Cytoscape.JS web pages
- Check the output to the browser console.
- DO NOT START OR STOP THE PROCESS HOSTING THIS SERVER. IT IS TO BE MANAGED BY HUMANS.

**Read/Edit static files**

- The source files can be found in $FOLDER_PATH
- The existing test suite files can be found in $TEST_PATH
- Edit ONLY the the files in $FOLDER_PATH and $TEST_PATH
- There may be multiple static sites running and getting editted by separate processes in parallel. So stay in your lane.

**Running existing tests**

You can run the existing test suite with this command to detect regressions or find tests that have drifted from new information provided in the given instructions.

```sh
uv run pytest $TEST_PATH --browser chromium --base-url $SITE_URL
```

# Workflow

- Run the existing test suite to get a baseline
    - If one does not exist create a basic one that at least loads the page and checks the console for errors
- Then follow these instructions $INSTRUCTIONS
- Edit any files in $FOLDER_PATH or $TEST_PATH as need be.
- Run the test suite again
- Repeat until the success criteria is met in the provide instruictions.

## Playwright MCP Cautionary Guidelines

When debugging and iterating leverage Playwright MCP on the localhost address.

When working on a multi site project, IT IS CRITICAL to focus on only the target folder and target port.

There may be multiple agentic coding processes running editting separate part of the project.

**Example:**

_Process 1 - Knowledge Graph_

```sh
uv run -m http.server --directory sites/knowledge_graph 8002
```

- FOLDER: `sites/knowledge_graph`
- PORT: 8002
- URL: `http://localhost:8002`

_Process 2 - Embeddings Comparrison_

```sh
uv run -m http.server --directory sites/embeddings_comparrison 8004
```

- FOLDER: `sites/embeddings_comparrison`
- PORT: 8002
- URL: `http://localhost:8004`

Each process ABSOLUTELY needs to stay in their own lane to avoid editting the files of the wrong project or checking the website of the wrong output and getting confused about what they are editting.