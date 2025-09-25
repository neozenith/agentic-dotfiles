# Static Sites

To assist with easy UI and visualisation of projects we sometimes need to build simple static HTML/JS/CSS websites.

---
<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Static Sites](#static-sites)
  - [Basic Structure](#basic-structure)
  - [Tooling](#tooling)
    - [Makefile](#makefile)
      - [Serving](#serving)
      - [Multi-site Makefiles](#multi-site-makefiles)
    - [Playwright](#playwright)
      - [Playwright Test Suite](#playwright-test-suite)
      - [Playwright MCP](#playwright-mcp)
  - [Frameworks](#frameworks)
    - [MermaidJS](#mermaidjs)
    - [DuckDB](#duckdb)
    - [Deck.GL](#deckgl)
    - [Cytoscape](#cytoscape)
    - [HuggingFace Transformers.JS](#huggingface-transformersjs)
    - [PyScript](#pyscript)
  - [Misc](#misc)
    - [Favicon](#favicon)
    - [Github Pages](#github-pages)
      - [Repo Setup](#repo-setup)
      - [Workflow](#workflow)

<!--TOC-->
</details>

----

## Basic Structure

This is a basic structure

```sh
sites/my_static_site
├── Makefile
├── index.html
├── script.js
├── config.json
├── data.json # Optional
└── styles.css
scripts
└── my_datapipeline_script.py # Optional
tests
├── test_my_datapipeline_script.py  # Optional
└── my_static_site                  # Playwright scripts
    └── test_my_static_site.py
```

There are some parts above that are marked `Optional` and left there for illustrative purposes on how they integrate other pregenerated content.

Eg the `data.json` is a built artifact which could be a very simple way for Javascript to read a datasource that is orthogonal to our template visualisation

## Tooling

### Makefile

Always have a `Makefile` with targets for `build`, `clean`, `test`, `serve`, `format`.

This `Makefile` lives in the same directory as our `index.html` so it can stay isolated from other sites in the same project.
The benefit is that if can selve discover the project name and automatically template itself.

The port numbers will need to be unique across each site.

```Makefile
PORT_NUMBER ?= 8004
THIS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
THIS_DIR_NAME := $(notdir $(patsubst %/,%,$(THIS_DIR)))
TEST_DIR := tests/$(THIS_DIR_NAME)

.PHONY: debug serve build docs format test clean

debug:
	@echo "THIS_DIR: $(THIS_DIR)"
	@echo "THIS_DIR_NAME: $(THIS_DIR_NAME)"
	@echo "PORT_NUMBER: $(PORT_NUMBER)"

serve:
	uv run -m http.server --directory $(THIS_DIR) $(PORT_NUMBER)

build:
    uv run scripts/my_datapipeline_script.py

docs:
	# Markdown
	uvx --from md-toc md_toc --in-place github --header-levels 4 *.md
	uvx rumdl check --fix --config ../../pyproject.toml *.md

format:
	# Code Formatting
	npx -y prettier './**/*.{js,css,html}' --write --print-width 120    

test: format
	uv run pytest ../../"$(TEST_DIR)" --base-url http://localhost:$(PORT_NUMBER) --browser chromium

clean:
	rm -rfv ./data.json
```

#### Serving

The `serve` target will have the designated port number we have chosen, which is `8002` in this example.

IMPORTANT: 
- I will start / stop the server. 
- DO NOT TRY TO START OR STOP THE SERVER YOURSELF.
- To address any caching issues use a new incognito browser session.

#### Multi-site Makefiles

Sometimes when we have many sites within the same project we may need to namespace them and their makefile commmands.

For example the 2 sites:

- `sites/knowledge_graph/`
- `sites/embeddings_comparrison/`

The `Makefiles` should be:
- `sites/knowledge_graph/Makefile`
- `sites/embeddings_comparrison/Makefile.`

Then issuing the commands like:

```sh
make -C sites/knowledge_graph clean
make -C sites/knowledge_graph build
make -C sites/knowledge_graph test
```

`-C` changes to a new working directory first then looks for `./Makefile`

### Playwright

We will use `playwright` for testing as well as `Playwright MCP` for debugging.

#### Playwright Test Suite

We should build up playwright tests under `tests/my_static_site/`

#### Playwright MCP

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

---

## Frameworks

### MermaidJS

Import

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
</script>
```

Example:

```html
<pre class="mermaid">
    graph LR
    A --- B
    B-->C[fa:fa-ban forbidden]
    B-->D(fa:fa-spinner);
</pre>
```

We may want to have a directory of `.mmd` files that we use our `script.js` to map the file content to filling in the `innerHtml`.

For example if we had `diagrams/architecture.mmd` then we can map to an id attribute like `diagrams__architecture_mmd` for a `pre` tag like:

```html
<pre class="mermaid" id="diagrams__architecture_mmd"></pre>
```

### DuckDB

DuckDB WASM provides a powerful in-browser SQL analytics database with vector search capabilities. Here's the implementation pattern for effective DuckDB integration:

#### HTML Setup

```html
<!-- DuckDB WASM -->
<script type="module">
  import * as duckdb from "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@latest/+esm";
  window.duckdb = duckdb;
</script>

<!-- Optional: Transformers.js for embeddings -->
<script type="module">
  import { pipeline, env } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers";
  env.allowLocalModels = false;
  env.useBrowserCache = true;
  window.transformers = { pipeline, env };
</script>
```

#### JavaScript Implementation Pattern

**1. Library Initialization**
```javascript
// Wait for libraries with retry mechanism
async function waitForLibraries() {
  let attempts = 0;
  while (!window.duckdb && attempts < 50) {
    await new Promise(resolve => setTimeout(resolve, 100));
    attempts++;
  }
  if (!window.duckdb) {
    throw new Error("DuckDB WASM failed to load");
  }
  return window.duckdb;
}
```

**2. DuckDB Instance Setup**
```javascript
async function initializeDuckDB() {
  const duckdb = await waitForLibraries();

  // Get CDN bundles
  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

  // Create Web Worker for async operations
  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" })
  );

  // Initialize DuckDB with worker
  const worker = new Worker(worker_url);
  const logger = new duckdb.ConsoleLogger();
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);

  // Create connection
  const conn = await db.connect();

  // Install extensions (e.g., VSS for vector search)
  await conn.query("INSTALL vss");
  await conn.query("LOAD vss");

  return { db, conn };
}
```

**3. Loading External Database Files**
```javascript
async function loadDatabase(db, conn) {
  // Fetch the database file
  const response = await fetch("data.duckdb");
  const buffer = await response.arrayBuffer();

  // Register file with DuckDB
  await db.registerFileBuffer("data.duckdb", new Uint8Array(buffer));

  // Attach the database
  await conn.query("ATTACH 'data.duckdb' AS external_db");

  // Verify data
  const result = await conn.query("SELECT COUNT(*) as count FROM external_db.my_table");
  const count = result.toArray()[0].count;
  console.log(`Database contains ${count} records`);
}
```

**4. Vector Search Implementation**
```javascript
async function performVectorSearch(conn, queryEmbedding) {
  // Get embedding dimension from database
  let embeddingDim = 384;
  try {
    const dimResult = await conn.query(`
      SELECT LENGTH(embedding) as dim
      FROM documents
      LIMIT 1
    `);
    if (dimResult.toArray().length > 0) {
      const dim = dimResult.toArray()[0].dim;
      // Handle BigInt conversion
      embeddingDim = typeof dim === "bigint" ? Number(dim) : dim;
    }
  } catch (e) {
    console.log("Using default dimension:", embeddingDim);
  }

  // Ensure embedding matches database dimension
  const adjustedEmbedding = new Array(embeddingDim).fill(0);
  for (let i = 0; i < Math.min(queryEmbedding.length, embeddingDim); i++) {
    adjustedEmbedding[i] = queryEmbedding[i];
  }

  // Format for SQL
  const embeddingStr = "[" + adjustedEmbedding.join(",") + "]";

  const searchQuery = `
    SELECT
      text,
      source,
      array_cosine_similarity(embedding, ${embeddingStr}::FLOAT[${embeddingDim}]) as similarity
    FROM documents
    ORDER BY similarity DESC
    LIMIT 10
  `;

  const results = await conn.query(searchQuery);
  return results.toArray();
}
```


**6. Debounced Search UI Pattern**
```javascript
let searchTimeout = null;

function handleSearchInput(event) {
  const query = event.target.value;

  // Clear previous timeout
  if (searchTimeout) {
    clearTimeout(searchTimeout);
  }

  // Hide results if empty
  if (!query.trim()) {
    hideResults();
    return;
  }

  // Debounce search - wait 300ms after user stops typing
  searchTimeout = setTimeout(() => {
    performSearch(query);
  }, 300);
}

// Set up event listener
document.getElementById("searchInput").addEventListener("input", handleSearchInput);
```

#### Key Implementation Patterns

1. **Library Loading**: Always use async loading with retry mechanism for CDN resources
2. **Worker Architecture**: Use Web Workers for async operations to prevent UI blocking
3. **Database Attachment**: For existing `.duckdb` files, use `registerFileBuffer` + `ATTACH`
4. **Vector Search**: Install VSS extension and use `array_cosine_similarity` for similarity search with embeddings
6. **UI Feedback**: Show loading states and progress during initialization
7. **Query Results**: Use `.toArray()` to convert DuckDB results to JavaScript arrays
8. **BigInt Handling**: Convert BigInt values to Number for JavaScript compatibility
9. **Debounced Search**: Use setTimeout to prevent excessive API calls during typing
10. **Explicit Database Handling**: Use attached database or throw error if unavailable

#### Testing Considerations

- DuckDB initialization can take 2-5 seconds depending on database size
- Console messages provide initialization status: "DuckDB WASM initialized successfully"
- Use Playwright to wait for loading indicators to disappear before testing
- Vector search requires VSS extension to be loaded

#### File Structure
```
sites/my_site/
├── index.html
├── script.js
├── styles.css
└── data.duckdb  # Pre-built database file
```

### HuggingFace Transformers.JS

HuggingFace Transformers.js provides in-browser machine learning models for NLP tasks like text embeddings, classification, and generation. Here's the implementation pattern for effective integration:

#### HTML Setup

```html
<!-- HuggingFace Transformers.js -->
<script type="module">
  import { pipeline, env } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers";

  // Configure Transformers.js settings
  env.allowLocalModels = false;  // Download models from HuggingFace Hub and skip local checks
  env.useBrowserCache = true;    // Cache models in browser for faster reloads

  // Make available globally
  window.transformers = { pipeline, env };
</script>
```

#### JavaScript Implementation Pattern

**1. Library Initialization with Explicit Error Handling**
```javascript
// Wait for library to load
async function waitForTransformers() {
  let attempts = 0;
  while (!window.transformers && attempts < 50) {
    await new Promise(resolve => setTimeout(resolve, 100));
    attempts++;
  }
  if (!window.transformers) {
    throw new Error("Transformers.js failed to load");
  }
  return window.transformers;
}
```

**2. Model Loading with WebGPU Support**
```javascript
let sentenceEmbedder = null;

async function loadEmbeddingModel() {
  const transformers = await waitForTransformers();

  try {
    const model_id = "Xenova/all-MiniLM-L6-v2"; // 384-dim embeddings

    // Create pipeline with WebGPU acceleration if available
    sentenceEmbedder = await transformers.pipeline(
      "feature-extraction",
      model_id,
      {
        device: 'webgpu',     // Use WebGPU for faster inference
        pooling: "mean",      // Mean pooling for sentence embeddings
        normalize: true       // L2 normalization for cosine similarity
      }
    );

    console.log("Sentence transformer model loaded successfully");
    return sentenceEmbedder;
  } catch (error) {
    console.error("Failed to load model:", error);
    throw error;
  }
}
```

**3. Generating Embeddings**
```javascript
async function generateEmbedding(text) {
    // Run inference
    const output = await sentenceEmbedder(text, {
      pooling: "mean",
      normalize: true
    });

    // Convert tensor to array
    const embedding = Array.from(output.data);
    console.log(`Generated ${embedding.length}-dim embedding`);

    return embedding;
}
```

**4. Integration with Vector Search (DuckDB Example)**
```javascript
async function searchWithEmbeddings(query, conn) {
  // Generate query embedding
  const queryEmbedding = await generateEmbedding(query);

  // Format for SQL query
  const embeddingStr = "[" + queryEmbedding.join(",") + "]";
  const embeddingDim = queryEmbedding.length;

  // Vector similarity search
  const searchQuery = `
    SELECT
      text,
      source,
      array_cosine_similarity(embedding, ${embeddingStr}::FLOAT[${embeddingDim}]) as similarity
    FROM documents
    ORDER BY similarity DESC
    LIMIT 10
  `;

  const results = await conn.query(searchQuery);
  return results.toArray();
}
```

#### Common Models and Use Cases

**Text Embeddings (Sentence Transformers)**
- `Xenova/all-MiniLM-L6-v2` - 384-dim, fast, general purpose
- `Xenova/all-mpnet-base-v2` - 768-dim, higher quality
- `Xenova/multilingual-e5-small` - Multilingual support

**Text Generation**
- `Xenova/t5-small` - Text-to-text generation
- `Xenova/gpt2` - Autoregressive text generation

**Classification**
- `Xenova/bert-base-uncased` - Text classification
- `Xenova/distilbert-base-uncased-finetuned-sst-2-english` - Sentiment analysis

#### Key Implementation Patterns

1. **Progressive Loading**: Show UI immediately, load models in background with explicit error handling
3. **WebGPU Acceleration**: Use `device: 'webgpu'` for 10-100x faster inference when available
4. **Browser Caching**: Set `env.useBrowserCache = true` to avoid re-downloading models
5. **Model Size Awareness**: Small models (20-100MB) load quickly, large models may timeout
6. **Memory Management**: Models stay in memory, consider cleanup for SPAs
7. **First Load UX**: First model download can take 10-30 seconds, show progress
8. **Error Handling**: Network failures, unsupported browsers, WebGPU unavailability

#### Testing Considerations

- First load will download model (10-30 seconds depending on size)
- Subsequent loads use browser cache (1-3 seconds)
- Console shows: "Sentence transformer model loaded successfully"
- WebGPU may not be available in all browsers (falls back to WASM)
- Use Playwright to wait for model loading before testing inference

#### Complete Example Structure
```javascript
// Full initialization flow
async function initializeML() {
  try {
    // Update UI
    showStatus("Loading AI models...");

    // Load transformer model
    await loadEmbeddingModel();

    // Verify model works
    const testEmbedding = await generateEmbedding("test");
    console.log("Model verification successful");

    // Update UI
    showStatus("Ready");
    enableSearchInput();

  } catch (error) {
    console.error("ML initialization failed:", error);
    showStatus("ML initialization failed - check console");
    throw error; // Explicit failure instead of fallback
  }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", initializeML);
```

### Deck.GL

Deck.GL is a WebGL-powered framework for visualizing large-scale data with high performance. Here's the implementation pattern for effective 3D visualization:

#### HTML Setup

```html
<!-- Deck.GL CDN -->
<script src="https://unpkg.com/deck.gl@8.9.35/dist.min.js"></script>
<script src="https://unpkg.com/@luma.gl/core@8.5.21/dist.min.js"></script>
```

#### JavaScript Implementation Pattern

**1. Container and Canvas Setup**
```javascript
function initializeDeckGL() {
  const container = document.getElementById("deckgl-container");

  if (!container || !window.deck) {
    throw new Error("Deck.GL container or library not found");
  }

  // Create canvas element
  const canvas = document.createElement("canvas");
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  container.appendChild(canvas);

  return { container, canvas };
}
```

**2. Lighting and Visual Effects**
```javascript
function createLightingEffects() {
  const ambientLight = new deck.AmbientLight({
    color: [255, 255, 255],
    intensity: 0.2,
  });

  const directionalLight = new deck.DirectionalLight({
    color: [255, 255, 255],
    intensity: 0.8,
    direction: [-1, -1, -2],
    _shadow: true, // Experimental shadow support
  });

  const pointLight = new deck.PointLight({
    color: [255, 255, 255],
    intensity: 1.0,
    position: [0, 0, 1000],
  });

  return new deck.LightingEffect({
    ambientLight,
    directionalLight,
    pointLight,
  });
}
```

**3. Deck Instance Creation**
```javascript
function createDeckInstance(canvas, container) {
  const lightingEffect = createLightingEffects();

  // Create initial data points
  const dataPoints = generateVisualizationData();

  // Create sphere mesh for 3D points
  const sphere = new luma.SphereGeometry({
    radius: 1,
    nlat: 10,
    nlong: 20,
  });

  const deckInstance = new deck.Deck({
    canvas: canvas,
    width: container.clientWidth,
    height: 500,
    views: [
      new deck.OrbitView({
        orbitAxis: "Y",
        fov: 50,
      }),
    ],
    initialViewState: {
      target: [0, 0, 0],
      zoom: 1,
    },
    controller: true,
    effects: [lightingEffect],
    layers: [
      new deck.SimpleMeshLayer({
        id: "data-mesh-layer",
        data: dataPoints,
        mesh: sphere,
        getPosition: d => d.position,
        getColor: d => d.color,
        getTransformMatrix: d => [
          d.radius, 0, 0, 0,
          0, d.radius, 0, 0,
          0, 0, d.radius, 0,
          0, 0, 0, 1,
        ],
        pickable: true,
        autoHighlight: true,
      }),
    ],
    getTooltip: ({ object }) => object && {
      html: `<div>${object.text}</div>`,
      style: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        padding: '8px',
        borderRadius: '4px',
      }
    },
  });

  return deckInstance;
}
```

**4. Dynamic Layer Updates**
```javascript
function updateVisualization(deckInstance, newData, queryPoint = null) {
  if (!deckInstance) {
    throw new Error("Deck.GL instance not initialized");
  }

  const allPoints = [...newData];
  if (queryPoint) {
    allPoints.push({
      ...queryPoint,
      color: [250, 100, 100], // Red for query
      radius: 8,
    });
  }

  const sphere = new luma.SphereGeometry({
    radius: 1,
    nlat: 10,
    nlong: 20,
  });

  deckInstance.setProps({
    layers: [
      new deck.SimpleMeshLayer({
        id: "data-mesh-layer",
        data: allPoints,
        mesh: sphere,
        getPosition: d => d.position,
        getColor: d => d.color,
        getTransformMatrix: d => [
          d.radius, 0, 0, 0,
          0, d.radius, 0, 0,
          0, 0, d.radius, 0,
          0, 0, 0, 1,
        ],
        pickable: true,
        autoHighlight: true,
        updateTriggers: {
          getPosition: allPoints,
          getColor: allPoints,
          getTransformMatrix: allPoints,
        },
      }),
    ],
  });
}
```

**5. Responsive Resize Handling**
```javascript
function setupResponsiveResize(deckInstance, container) {
  const resizeObserver = new ResizeObserver((entries) => {
    for (let entry of entries) {
      const { width } = entry.contentRect;
      deckInstance.setProps({
        width: width,
        height: 500, // Fixed height
      });
    }
  });

  resizeObserver.observe(container);
  return resizeObserver;
}
```

#### Common Layer Types and Use Cases

**Visualization Layers:**
- `SimpleMeshLayer`: 3D objects with custom meshes (spheres, cubes, models)
- `ScatterplotLayer`: 2D/3D point clouds with size and color mapping
- `LineLayer`: Connections between points, flight paths, network edges
- `ArcLayer`: Curved connections, geographic arcs, flow visualization
- `GeoJsonLayer`: Geographic data, boundaries, polygons

**Mesh Geometries:**
- `SphereGeometry`: Points, nodes, particles
- `CubeGeometry`: Voxels, building blocks, data cubes
- `CylinderGeometry`: Towers, bars, vertical elements
- Custom geometries: GLTF models, procedural shapes

#### Key Implementation Patterns

1. **Strict Error Handling**: Throw errors immediately when libraries or containers unavailable
2. **Layer Performance**: Use `visible` property instead of removing/adding layers
3. **Update Triggers**: Specify `updateTriggers` for efficient layer updates
4. **Memory Management**: Properly dispose of geometries and clean up resources
5. **View Configuration**: Use appropriate views (`OrbitView`, `MapView`) for use case
6. **Lighting Setup**: Configure lighting for realistic 3D rendering
7. **Responsive Design**: Handle container resizing with ResizeObserver
8. **Tooltip Implementation**: Provide informative hover feedback
9. **Canvas Management**: Create and manage canvas elements programmatically

#### Performance Optimization

**Layer Management:**
```javascript
// Good: Use visible property for performance
layers: [
  new deck.SimpleMeshLayer({
    id: 'data-layer',
    visible: showData, // Boolean flag
    data: dataPoints,
    // ... other props
  })
]

// Bad: Conditionally creating layers causes regeneration
layers: [
  showData && new deck.SimpleMeshLayer({
    id: 'data-layer',
    data: dataPoints,
    // ... other props
  })
].filter(Boolean)
```

**Pixel Ratio Adjustment:**
```javascript
// For large datasets on high-DPI displays
const deckInstance = new deck.Deck({
  pixelRatio: 1, // Force 1:1 ratio for performance
  // ... other props
});
```

#### Testing Considerations

- Deck.GL requires WebGL support and may fail on older browsers
- 3D visualizations can be GPU-intensive, especially with many points
- Layer initialization can take time with large datasets
- Use loading indicators during data processing and rendering

#### Complete Integration Example
```javascript
// Full initialization workflow
async function initializeVisualization() {
  try {
    const { container, canvas } = initializeDeckGL();
    const deckInstance = createDeckInstance(canvas, container);

    // Setup responsive behavior
    setupResponsiveResize(deckInstance, container);

    // Make globally available for updates
    window.deckInstance = deckInstance;

    console.log("Deck.GL visualization initialized");
    return deckInstance;
  } catch (error) {
    throw new Error(`Failed to initialize Deck.GL: ${error.message}`);
  }
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
    initializeVisualization();
  }, 100);
});
```

### Cytoscape

Cytoscape.js is a graph theory library for modeling and visualizing relational data, ideal for network graphs, knowledge graphs, and social networks.

#### HTML Setup

```html
<!-- Cytoscape.js CDN -->
<script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>

<!-- Container with proper styling -->
<div id="cy" style="width: 100%; height: 500px;"></div>
```

#### JavaScript Implementation Pattern

**1. Basic Initialization**
```javascript
class GraphVisualizer {
  constructor() {
    this.cy = null;
    this.rawData = null;
    this.currentLayout = 'cose';

    this.init();
  }

  async init() {
    try {
      await this.loadData();
      this.processData();
      this.initializeCytoscape();
      this.setupEventHandlers();
      this.applyLayout('cose');
    } catch (error) {
      throw new Error(`Failed to initialize graph: ${error.message}`);
    }
  }
}
```

**2. Data Loading and Processing**
```javascript
async loadData() {
  const response = await fetch('./graph-data.json');
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  this.rawData = await response.json();
}

processData() {
  const nodes = this.rawData.elements.nodes;
  const edges = this.rawData.elements.edges;

  // Calculate frequency ranges for styling
  const nodeFreqs = nodes.map(n => n.data.frequency || 0);
  const minFreq = Math.min(...nodeFreqs);
  const maxFreq = Math.max(...nodeFreqs);

  nodes.forEach(node => {
    const freq = node.data.frequency || 0;
    const ratio = maxFreq > minFreq ? (freq - minFreq) / (maxFreq - minFreq) : 0;

    // Classify frequency for styling
    if (ratio >= 0.7) node.data.frequencyClass = 'high';
    else if (ratio >= 0.3) node.data.frequencyClass = 'medium';
    else node.data.frequencyClass = 'low';

    // Calculate size based on frequency
    node.data.computedSize = 20 + (60 * ratio); // 20-80px range
  });

  edges.forEach(edge => {
    const confidence = edge.data.confidence || 0.5;
    edge.data.computedOpacity = Math.max(0.3, confidence);
  });
}
```

**3. Cytoscape Instance Creation**
```javascript
initializeCytoscape() {
  this.cy = cytoscape({
    container: document.getElementById('cy'),
    elements: this.rawData.elements,

    style: [
      {
        selector: 'node',
        style: {
          'width': 'data(computedSize)',
          'height': 'data(computedSize)',
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '12px',
          'color': '#ffffff',
          'text-outline-width': 2,
          'text-outline-color': '#000000'
        }
      },
      {
        selector: 'node[entityType = "ORG"]',
        style: {
          'background-color': '#1f77b4',
          'shape': 'rectangle'
        }
      },
      {
        selector: 'node[entityType = "PERSON"]',
        style: {
          'background-color': '#ff7f0e',
          'shape': 'ellipse'
        }
      },
      {
        selector: 'node[entityType = "CONCEPT"]',
        style: {
          'background-color': '#2ca02c',
          'shape': 'diamond'
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#666666',
          'target-arrow-color': '#666666',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'opacity': 'data(computedOpacity)'
        }
      },
      {
        selector: '.highlighted',
        style: {
          'background-color': '#ff6b6b',
          'line-color': '#ff6b6b',
          'target-arrow-color': '#ff6b6b',
          'transition-property': 'background-color, line-color, target-arrow-color',
          'transition-duration': '0.3s'
        }
      }
    ],

    layout: {
      name: 'grid',
      rows: 1
    },

    // Interaction settings
    zoomingEnabled: true,
    userZoomingEnabled: true,
    panningEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: true,
    autoungrabify: false
  });
}
```

**4. Event Handling**
```javascript
setupEventHandlers() {
  // Node selection
  this.cy.on('select', 'node', (evt) => {
    const node = evt.target;
    this.displayNodeDetails(node);
  });

  this.cy.on('unselect', 'node', () => {
    this.clearNodeDetails();
  });

  // Hover effects
  this.cy.on('mouseover', 'node', (evt) => {
    const node = evt.target;
    node.addClass('highlighted');

    // Highlight connected elements
    const neighborhood = node.neighborhood();
    neighborhood.addClass('highlighted');
  });

  this.cy.on('mouseout', 'node', (evt) => {
    const node = evt.target;
    node.removeClass('highlighted');
    node.neighborhood().removeClass('highlighted');
  });

  // Edge interactions
  this.cy.on('select', 'edge', (evt) => {
    const edge = evt.target;
    this.displayEdgeDetails(edge);
  });
}
```

**5. Layout Management**
```javascript
applyLayout(layoutName) {
  let layoutOptions = {
    name: layoutName,
    animate: true,
    animationDuration: 1000,
  };

  switch (layoutName) {
    case 'cose':
      layoutOptions = {
        ...layoutOptions,
        idealEdgeLength: 100,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        padding: 30,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0
      };
      break;

    case 'circle':
      layoutOptions.radius = 200;
      break;

    case 'grid':
      layoutOptions.rows = Math.ceil(Math.sqrt(this.cy.nodes().length));
      break;

    case 'breadthfirst':
      layoutOptions.directed = true;
      layoutOptions.spacingFactor = 1.75;
      break;
  }

  const layout = this.cy.layout(layoutOptions);
  layout.run();
}
```

**6. Filtering and Search**
```javascript
applyFilters(filters) {
  // Reset visibility
  this.cy.nodes().style('display', 'element');

  let nodesToHide = this.cy.collection();

  // Frequency filter
  if (filters.frequency !== 'all') {
    const freqFilter = {
      'high-freq': node => node.data('frequencyClass') !== 'high',
      'medium-freq': node => !['high', 'medium'].includes(node.data('frequencyClass'))
    };

    if (freqFilter[filters.frequency]) {
      nodesToHide = nodesToHide.union(
        this.cy.nodes().filter(freqFilter[filters.frequency])
      );
    }
  }

  // Entity type filter
  if (filters.entityType !== 'all') {
    nodesToHide = nodesToHide.union(
      this.cy.nodes().filter(node =>
        node.data('entityType') !== filters.entityType
      )
    );
  }

  // Apply visibility
  nodesToHide.style('display', 'none');

  // Re-fit graph
  this.cy.fit();
}

searchNodes(query) {
  if (!query.trim()) {
    this.cy.elements().removeClass('search-highlight');
    return;
  }

  const matches = this.cy.nodes().filter(node => {
    const label = node.data('label') || '';
    return label.toLowerCase().includes(query.toLowerCase());
  });

  this.cy.elements().removeClass('search-highlight');
  matches.addClass('search-highlight');

  if (matches.length > 0) {
    this.cy.fit(matches, 50);
  }
}
```

#### Common Layout Algorithms

**Force-Directed Layouts:**
- `cose`: Physics-based layout with customizable forces
- `fcose`: Fast compound spring embedder (better for large graphs)
- `cola`: Constraint-based layout with overlap removal

**Hierarchical Layouts:**
- `breadthfirst`: Tree-like structure from root nodes
- `dagre`: Directed acyclic graph layout

**Geometric Layouts:**
- `grid`: Arrange nodes in a grid
- `circle`: Nodes arranged in a circle
- `concentric`: Concentric circles based on node properties

#### Key Implementation Patterns

1. **Error Handling**: Throw errors immediately when data loading fails or containers missing
2. **Data Processing**: Pre-calculate styling properties for performance
3. **Event Management**: Use specific event handlers for different interactions
4. **Layout Performance**: Cache layout options and use appropriate algorithms for graph size
5. **Filtering Logic**: Use Cytoscape collections for efficient node/edge operations
6. **Responsive Design**: Handle container resize events
7. **Memory Management**: Properly destroy instances when cleaning up
8. **Batch Operations**: Use `cy.batch()` for multiple simultaneous changes

#### Performance Optimization

**Large Graph Handling:**
```javascript
// For graphs with >1000 nodes
const cy = cytoscape({
  // ... other options
  hideEdgesOnViewport: true, // Hide edges during pan/zoom
  textureOnViewport: false,  // Disable texture rendering during interaction
  motionBlur: false,         // Disable motion blur
  wheelSensitivity: 1,       // Adjust zoom sensitivity
  pixelRatio: 1             // Force 1:1 ratio for performance
});
```

**Style Optimization:**
```javascript
// Fast edge styles
'curve-style': 'haystack',  // Fastest curve style
'line-style': 'solid',      // Avoid dashed/dotted
'width': 1,                 // Minimize edge width

// Avoid unnecessary visual effects
'text-outline-width': 0,    // Remove text outlines
'background-image': 'none'  // Avoid background images
```

#### Testing Considerations

- Graph rendering performance depends on number of nodes/edges
- Layout algorithms can take time with large datasets (>1000 nodes)
- Use loading indicators during layout calculations
- Test with different graph sizes and structures
- Consider progressive loading for very large graphs

#### Complete Integration Example
```javascript
// Initialize graph visualization
async function initializeGraph() {
  try {
    const visualizer = new GraphVisualizer();

    // Setup UI controls
    document.getElementById('layout-select').addEventListener('change', (e) => {
      visualizer.applyLayout(e.target.value);
    });

    document.getElementById('search-input').addEventListener('input', (e) => {
      visualizer.searchNodes(e.target.value);
    });

    return visualizer;
  } catch (error) {
    throw new Error(`Graph initialization failed: ${error.message}`);
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializeGraph);
```


### PyScript

PyScript enables running Python code directly in the browser, bridging Python data science libraries with JavaScript frontend frameworks. Here's the implementation pattern for effective Python-JavaScript integration:

#### HTML Setup

```html
<!-- PyScript Core CSS and JS -->
<link rel="stylesheet" href="https://pyscript.net/releases/2024.9.2/core.css" />
<script type="module" src="https://pyscript.net/releases/2024.9.2/core.js"></script>

<!-- PyScript Configuration -->
<py-config>
packages = ["numpy", "scikit-learn", "umap-learn"]
</py-config>
```

#### Python Implementation Pattern

**1. Core Python Module (utils.py)**
```python
import numpy as np
import json
from umap import UMAP
from sklearn.preprocessing import StandardScaler
from js import window, document, console
from pyodide.ffi import create_proxy, to_js
import asyncio

# Global state
umap_reducer = None
scaler = None

def initialize_reducer():
    """Initialize UMAP reducer for 3D visualization"""
    global umap_reducer, scaler
    umap_reducer = UMAP(n_components=3, random_state=42, n_neighbors=15, min_dist=0.1)
    scaler = StandardScaler()
    console.log("UMAP reducer initialized")
    return True

def reduce_embeddings_to_3d(embeddings_list, fit_new=True):
    """
    Reduce high-dimensional embeddings to 3D using UMAP

    Args:
        embeddings_list: List of embeddings (each embedding is a list of floats)
        fit_new: Whether to fit new data or use existing fit

    Returns:
        List of 3D coordinates
    """
    global umap_reducer, scaler

    if umap_reducer is None:
        initialize_reducer()

    # Convert to numpy array
    embeddings_array = np.array(embeddings_list)
    console.log(f"Processing {len(embeddings_array)} embeddings of dimension {embeddings_array.shape[1] if len(embeddings_array) > 0 else 0}")

    # Apply UMAP reduction
    if fit_new:
        embeddings_3d = umap_reducer.fit_transform(embeddings_array)
    else:
        embeddings_3d = umap_reducer.transform(embeddings_array)

    # Normalize to reasonable range for visualization
    embeddings_3d = embeddings_3d * 30  # Scale up for better visualization

    # Convert to list for JavaScript
    result = embeddings_3d.tolist()
    console.log(f"UMAP reduction complete: {len(result)} points in 3D")

    return result
```

**2. JavaScript Bridge Functions**
```python
async def process_search_embeddings(embeddings_data):
    """
    Process embeddings from search results
    embeddings_data should contain:
    - embeddings: list of embeddings
    - texts: list of text snippets
    - sources: list of source files
    - similarities: list of similarity scores
    """
    try:
        # Parse the data - handle JS to Python conversion
        data = embeddings_data.to_py() if hasattr(embeddings_data, 'to_py') else embeddings_data

        embeddings = data.get('embeddings', [])
        texts = data.get('texts', [])
        sources = data.get('sources', [])
        similarities = data.get('similarities', [])
        query_embedding = data.get('query_embedding', None)

        if not embeddings:
            console.log("No embeddings to process")
            return None

        # Add query embedding if provided
        all_embeddings = embeddings.copy()
        if query_embedding:
            all_embeddings.append(query_embedding)

        # Reduce dimensions
        coords_3d = reduce_embeddings_to_3d(all_embeddings)

        # Prepare visualization data
        viz_points = []
        for i, coord in enumerate(coords_3d[:-1] if query_embedding else coords_3d):
            point = {
                'position': coord,
                'color': [100, 150, 250],  # Blue for search results
                'radius': 5 + (similarities[i] * 10 if i < len(similarities) else 5),
                'text': f"{sources[i] if i < len(sources) else 'Unknown'}\n{texts[i][:100] if i < len(texts) else '...'}...\nSimilarity: {(similarities[i]*100):.1f}%" if i < len(similarities) else "N/A",
                'category': 'search_result',
                'snippet': texts[i] if i < len(texts) else '',
                'source': sources[i] if i < len(sources) else '',
                'similarity': similarities[i] if i < len(similarities) else 0
            }
            viz_points.append(point)

        # Add query point if it exists
        if query_embedding and len(coords_3d) > len(embeddings):
            query_point = {
                'position': coords_3d[-1],
                'color': [250, 100, 100],  # Red for query
                'radius': 10,
                'text': 'Search Query',
                'category': 'query',
                'snippet': 'Your search query',
                'source': 'query',
                'similarity': 1.0
            }
            viz_points.append(query_point)

        # Call JavaScript function to update visualization
        window.updateVisualizationFromPython(to_js(viz_points))

        return viz_points

    except Exception as e:
        console.error(f"Error processing embeddings: {str(e)}")
        return None

# Make functions available to JavaScript
window.initializeReducer = create_proxy(initialize_reducer)
window.processSearchEmbeddings = create_proxy(process_search_embeddings)
window.reduceEmbeddingsTo3D = create_proxy(reduce_embeddings_to_3d)

# Initialize reducer on load
initialize_reducer()
console.log("PyScript dimensionality reduction module loaded and ready")
```

**3. JavaScript Integration**
```javascript
// Function called by Python to update visualization
window.updateVisualizationFromPython = function(vizPoints) {
  const points = vizPoints; // Already converted from Python

  if (window.deckInstance) {
    // Update Deck.GL visualization with Python-processed data
    updateVisualization(points);
    console.log(`Updated visualization with ${points.length} points from Python`);
  } else {
    console.warn("Deck.GL instance not ready for Python data");
  }
};

// Call Python functions from JavaScript
async function processEmbeddingsWithPython(embeddingData) {
  try {
    // Call Python function
    const result = await window.processSearchEmbeddings(embeddingData);

    if (result) {
      console.log("Python processing successful");
    } else {
      throw new Error("Python processing returned null");
    }
  } catch (error) {
    console.error("Failed to process embeddings with Python:", error);
    // Fail loudly - no graceful fallback
    throw error;
  }
}
```

#### HTML Integration Pattern

```html
<!-- Embed Python script -->
<script type="py" src="utils.py"></script>

<!-- Alternative: Inline Python -->
<script type="py">
from js import console
import numpy as np

def hello_from_python():
    console.log("Hello from PyScript!")
    data = np.random.random((5, 3))
    return data.tolist()

# Make available to JavaScript
from pyodide.ffi import create_proxy
from js import window
window.helloFromPython = create_proxy(hello_from_python)
</script>
```

#### Common Use Cases and Patterns

**Data Processing Workflows:**
- **UMAP/t-SNE**: Dimensionality reduction for visualization
- **Clustering**: HDBSCAN, K-means for data grouping
- **Statistical Analysis**: NumPy, SciPy for mathematical operations
- **Machine Learning**: Scikit-learn for preprocessing and modeling

**Integration Patterns:**
- **JavaScript → Python**: Pass data for processing
- **Python → JavaScript**: Return processed results
- **Bidirectional**: Real-time data exchange
- **Async Operations**: Handle long-running computations

#### Key Implementation Patterns

1. **Explicit Error Handling**: Throw errors immediately when Python modules fail to load
2. **Data Type Conversion**: Use `to_js()` and `.to_py()` for proper data exchange
3. **Proxy Functions**: Use `create_proxy()` to expose Python functions to JavaScript
4. **Global State Management**: Carefully manage Python global variables
5. **Module Organization**: Separate Python code into logical modules
6. **Console Logging**: Use `console.log()` for debugging from Python
7. **Async Pattern**: Handle asynchronous operations properly
8. **Resource Management**: Initialize expensive objects once and reuse

#### Configuration Best Practices

**Package Management:**
```html
<py-config>
packages = [
  "numpy",
  "scikit-learn",
  "umap-learn",
  "pandas"
]
</py-config>
```

**Version Pinning:**
```html
<py-config>
packages = [
  "numpy==1.24.3",
  "scikit-learn==1.3.0"
]
</py-config>
```

#### Performance Considerations

**Optimization Strategies:**
```python
# Cache expensive operations
@functools.lru_cache(maxsize=128)
def expensive_computation(data_hash):
    # Expensive operation here
    return result

# Use NumPy for performance
def process_large_dataset(data):
    # Convert to NumPy array for speed
    np_data = np.array(data)
    # Vectorized operations
    result = np.multiply(np_data, 2.0)
    return result.tolist()

# Batch processing for efficiency
def process_in_batches(large_dataset, batch_size=1000):
    for i in range(0, len(large_dataset), batch_size):
        batch = large_dataset[i:i + batch_size]
        yield process_batch(batch)
```

#### Common Gotchas and Solutions

**1. Module Loading Failures:**
```python
# Bad: Silent failure
try:
    import expensive_module
except ImportError:
    expensive_module = None  # Graceful fallback - BAD!

# Good: Explicit failure
try:
    import expensive_module
except ImportError:
    raise ImportError("Required module 'expensive_module' failed to load")
```

**2. Data Type Issues:**
```python
# Handle JavaScript data properly
def process_js_data(js_data):
    # Convert JavaScript object to Python dict
    python_data = js_data.to_py() if hasattr(js_data, 'to_py') else js_data

    # Process data
    result = perform_analysis(python_data)

    # Convert back to JavaScript
    return to_js(result)
```

**3. Class Instantiation:**
```javascript
// Wrong: Direct instantiation
const myObj = new MyJavaScriptClass("value");

// Right: Use .new() method from Python
const myObj = MyJavaScriptClass.new("value");
```

#### Testing Considerations

- PyScript loading can take 10-30 seconds on first load
- Python package installation happens at runtime
- Large datasets may cause memory issues in browser
- Not all Python packages are available in Pyodide
- Use loading indicators during Python initialization
- Test with different browser memory limits

#### Complete Integration Example

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://pyscript.net/releases/2024.9.2/core.css" />
    <script type="module" src="https://pyscript.net/releases/2024.9.2/core.js"></script>

    <py-config>
    packages = ["numpy", "scikit-learn", "umap-learn"]
    </py-config>
</head>
<body>
    <div id="status">Loading Python environment...</div>
    <button id="process-btn" disabled>Process Data</button>

    <script type="py">
import numpy as np
from js import window, document, console
from pyodide.ffi import create_proxy, to_js

def process_data(raw_data):
    try:
        data = np.array(raw_data)
        result = np.mean(data, axis=0)
        console.log(f"Processed {len(data)} items")
        return result.tolist()
    except Exception as e:
        console.error(f"Processing failed: {str(e)}")
        raise

# Initialize
window.processData = create_proxy(process_data)
document.getElementById("status").textContent = "Python ready!"
document.getElementById("process-btn").disabled = False
console.log("PyScript initialization complete")
    </script>

    <script>
document.getElementById("process-btn").addEventListener("click", async () => {
    try {
        const testData = [[1, 2, 3], [4, 5, 6], [7, 8, 9]];
        const result = await window.processData(testData);
        console.log("Result:", result);
    } catch (error) {
        console.error("Processing failed:", error);
        alert("Data processing failed - check console");
    }
});
    </script>
</body>
</html>
```

---

## Misc

### Favicon

You can use the following snippet to use any emoji as a favicon for a browser.

```html
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🐮</text></svg>">
```

- It self embeds an SVG as the image canvas
- Then adds a `<text>` element to render the one emoji as the only content for the image


### Github Pages

#### Repo Setup

Per github repo you will need to go to:

https://github.com/ORGANISATION/REPO_NAME/settings/pages

And enable github pages and set the deployment type to `Github Actions`.

#### Workflow

Create this github actions workflow file to automate build and deployments

`.github/workflows/deploy-github-pages.yml`

```yaml
name: Deploy to GitHub Pages

on:
  # Runs on pushes targeting the default branch
  push:
    branches: ["main"]
    
    # List key files that is modified should trigger this pipeline
    # NOTE: Might need a workflow PER site if a multi site project.
    paths:
      - 'site/mystatic_site/**'
      - 'scripts/my_datapipeline_script.py'
      - '.github/workflows/deploy-github-pages.yml'

  # Allows you to run this workflow manually from the Actions tab
  workflow_dispatch:

# Sets permissions of the GITHUB_TOKEN to allow deployment to GitHub Pages
permissions:
  contents: read
  pages: write
  id-token: write

# Allow only one concurrent deployment, skipping runs queued between the run in-progress and latest queued.
# However, do NOT cancel in-progress runs as we want to allow these production deployments to complete.
concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  # Build job
  build:
    env:
      GOOGLE_MAPS_API_KEY: ${{ secrets.GOOGLE_MAPS_API_KEY }} # Optionally export any API keys or secrets
    runs-on: ubuntu-latest
    steps:

      - uses: actions/checkout@v4

      # Only add these steps if actaully needing python for running scripts
      - uses: astral-sh/setup-uv@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
      - name: My python script for the build or data pipeline
        run: uv run scripts/my_datapipeline_script.py

      # This is absolutely essential for uploading artifacts ready for deployment to github pages
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          # Upload static folder
          path: './site/mystatic_site'

  # Deployment job
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```