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

Deck.GL is a WebGL-powered framework for visualizing large-scale data with high performance. We have two distinct Deck.GL usage patterns: **3D visualizations** and **geospatial map overlays**.

---

#### Pattern 1: 3D Visualization (Point Clouds, Embeddings)

For visualizing 3D data like embeddings, point clouds, or scientific data. Here's the implementation pattern for effective 3D visualization:

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

---

#### Pattern 2: Geospatial Map Overlays (GeoJSON, Transport Networks)

For visualizing geospatial data on interactive maps with MapLibre GL base maps. This pattern is optimized for large-scale GeoJSON datasets, multi-layer overlays, and interactive selections.

##### HTML Setup

```html
<!-- Deck.GL with MapLibre GL base map -->
<script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@3.0.0/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@3.0.0/dist/maplibre-gl.css" rel="stylesheet" />

<!-- Optional: DuckDB for data queries -->
<script type="module">
  import * as duckdb from 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@latest/+esm';
  window.duckdb = duckdb;
</script>

<!-- Optional: Plotly for charts -->
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
```

##### Key Architecture Components

**1. Layer Configuration System**

Use JSON configuration files to define all map layers externally:

```json
{
  "version": "2024-09-24-15:45",
  "colors": {
    "fill5min": [0, 200, 100, 20],
    "line5min": [0, 150, 75, 200],
    "hover": [255, 150, 0, 120]
  },
  "layers": [
    {
      "id": "isochrones-5min",
      "type": "GeoJsonLayer",
      "data": "./data/5.geojson",
      "filled": true,
      "stroked": true,
      "pickable": false,
      "getFillColor": "color:fill5min",
      "getLineColor": "color:line5min",
      "getLineWidth": 1,
      "highlightColor": "color:hover"
    },
    {
      "id": "postcodes",
      "type": "GeoJsonLayer",
      "data": "./data/postcodes.geojson",
      "pickable": true,
      "autoHighlight": true,
      "getFillColor": [200, 50, 200, 0],
      "getLineColor": [200, 50, 200, 100],
      "getLineWidth": 6
    }
  ]
}
```

**Benefits:**
- **Separation of concerns**: Visual config separate from code
- **Easy updates**: Non-developers can modify layer visibility, colors, widths
- **Color references**: `"color:fill5min"` references color palette
- **Layer management**: Toggle layers on/off without code changes

**2. Deck.GL with MapLibre GL Base Map**

```javascript
// Initialize MapLibre GL JS base map
const { DeckGL, GeoJsonLayer, ScatterplotLayer } = deck;

const INITIAL_VIEW_STATE = {
  longitude: 144.9631,
  latitude: -37.8136,
  zoom: 11,
  pitch: 0,
  bearing: 0
};

// Create Deck instance with MapLibre integration
window.deckgl = new DeckGL({
  container: 'container',
  mapStyle: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  initialViewState: INITIAL_VIEW_STATE,
  controller: true,
  getTooltip: ({ object }) => {
    if (!object) return null;
    return {
      html: createTooltipHTML(object),
      style: {
        background: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        padding: '8px',
        borderRadius: '4px'
      }
    };
  },
  onClick: ({ object, layer }) => {
    if (object && layer.props.pickable) {
      handleSelection(object, layer);
    }
  }
});
```

**3. Dynamic Layer Creation from Config**

```javascript
// Function to resolve color references
function resolveColorReference(value, colors) {
  if (typeof value === "string" && value.startsWith("color:")) {
    const colorKey = value.substring(6);
    return colors[colorKey] || [255, 255, 255, 255];
  }
  return value;
}

// Function to create layers from config
function createLayersFromConfig(config) {
  if (!config || !config.layers) return [];

  const colors = config.colors || {};

  return config.layers.map((layerConfig) => {
    const processedConfig = { ...layerConfig };

    // Resolve color references
    ["getFillColor", "getLineColor", "highlightColor"].forEach((prop) => {
      if (processedConfig[prop]) {
        processedConfig[prop] = resolveColorReference(
          processedConfig[prop],
          colors
        );
      }
    });

    // Handle special cases (e.g., dynamic data loading)
    if (processedConfig.id === "real-estate-candidates") {
      // Load and process GeoJSON
      fetch(processedConfig.data)
        .then(response => response.json())
        .then(geojson => {
          const features = geojson.features.map(feature => ({
            ...feature.properties,
            coordinates: feature.geometry.coordinates,
            geometry: feature.geometry
          }));

          // Handle color extraction from properties
          if (processedConfig.getFillColor === "ptv_walkability_colour") {
            processedConfig.getFillColor = (d) => {
              const hex = d.ptv_walkability_colour;
              return hexToRgbA(hex) || [255, 255, 255, 255];
            };
          }

          processedConfig.data = features;

          // Update layer dynamically
          const newLayer = new GeoJsonLayer(processedConfig);
          const currentLayers = window.deckgl.props.layers || [];
          const filtered = currentLayers.filter(l => l.id !== processedConfig.id);
          window.deckgl.setProps({ layers: [...filtered, newLayer] });
        });

      // Return placeholder while loading
      return new GeoJsonLayer({
        ...processedConfig,
        data: []
      });
    }

    // Remove type property (not needed by deck.gl)
    delete processedConfig.type;

    return new GeoJsonLayer(processedConfig);
  });
}

// Load and apply configuration
fetch("./layers_config.json")
  .then(response => response.json())
  .then(config => {
    const layers = createLayersFromConfig(config);
    window.deckgl.setProps({ layers });
    console.log(`Loaded ${layers.length} layers from config`);
  })
  .catch(error => {
    console.error("Error loading layer configuration:", error);
  });
```

**4. Interactive Layer Controls**

```javascript
// Layer visibility management
const layerVisibility = {
  "isochrones-5min": true,
  "isochrones-15min": true,
  "postcodes": true,
  "lga-boundaries": true,
  "suburbs-sal": true
};

function toggleLayer(layerId) {
  layerVisibility[layerId] = !layerVisibility[layerId];

  const updatedLayers = window.deckgl.props.layers.map(layer => {
    if (layer.id === layerId) {
      return layer.clone({ visible: layerVisibility[layerId] });
    }
    return layer;
  });

  window.deckgl.setProps({ layers: updatedLayers });
}

// Setup UI checkboxes
document.querySelectorAll('.layer-item input[type="checkbox"]').forEach(checkbox => {
  checkbox.addEventListener('change', (e) => {
    const layerId = e.target.dataset.layerId;
    toggleLayer(layerId);
  });
});
```

**5. Selection Management System**

```javascript
// Multi-selection with type-based limits
const MAX_SELECTIONS_BY_TYPE = {
  "real-estate-candidates": 2,
  "postcodes": 2,
  "lga": 2,
  "sal": 2,
  "ptv-stops-tram": 1,
  "ptv-stops-train": 1
};

let selectedItems = [];

function handleSelection(object, layer) {
  const layerType = getLayerType(layer.id);
  const maxSelections = MAX_SELECTIONS_BY_TYPE[layerType] || 1;

  // Check if already selected
  const existingIndex = selectedItems.findIndex(item =>
    item.id === object.id && item.type === layerType
  );

  if (existingIndex !== -1) {
    // Remove if clicking again
    selectedItems.splice(existingIndex, 1);
  } else {
    // Check limits
    const typeCount = selectedItems.filter(item =>
      item.type === layerType
    ).length;

    if (typeCount >= maxSelections) {
      // Remove oldest of this type
      const oldestIndex = selectedItems.findIndex(item =>
        item.type === layerType
      );
      selectedItems.splice(oldestIndex, 1);
    }

    // Add new selection
    selectedItems.push({
      id: object.id || generateId(object),
      type: layerType,
      properties: object.properties || object,
      geometry: object.geometry
    });
  }

  updateSelectionPanel();
}

function updateSelectionPanel() {
  const panel = document.getElementById('selection-panel');
  const container = document.getElementById('selected-items-container');

  if (selectedItems.length === 0) {
    panel.style.display = 'none';
    return;
  }

  panel.style.display = 'block';
  container.innerHTML = selectedItems.map((item, index) =>
    createSelectionCard(item, index)
  ).join('');
}

function createSelectionCard(item, index) {
  let content = '';

  // Type-specific content
  if (item.type === 'lga') {
    content = `
      <strong>${item.properties.LGA_NAME24}</strong><br/>
      LGA Code: ${item.properties.LGA_CODE24}<br/>
      <div id="chart-${index}" class="shared-chart"></div>
    `;

    // Create chart after DOM update
    setTimeout(() => {
      createAreaChart(
        `chart-${index}`,
        "LGA",
        item.properties.LGA_CODE24,
        "rental",
        item.properties.LGA_NAME24
      );
    }, 200);
  } else if (item.type === 'sal') {
    content = `
      <strong>${item.properties.SAL_NAME21}</strong><br/>
      SAL Code: ${item.properties.SAL_CODE21}<br/>
      <div id="chart-${index}" class="shared-chart"></div>
    `;

    setTimeout(() => {
      createAreaChart(
        `chart-${index}`,
        "SUBURB",
        item.properties.SAL_CODE21,
        "rental",
        item.properties.SAL_NAME21
      );
    }, 200);
  }

  return `
    <div class="selection-card" data-index="${index}">
      <button class="remove-btn" onclick="removeSelection(${index})">×</button>
      ${content}
    </div>
  `;
}
```

**6. DuckDB Integration for Analytics**

```javascript
// Initialize DuckDB WASM
async function initializeDuckDB() {
  console.log("Initializing DuckDB WASM...");

  // Wait for duckdb module
  let retries = 20;
  while (retries > 0 && typeof window.duckdb === "undefined") {
    await new Promise(resolve => setTimeout(resolve, 100));
    retries--;
  }

  if (typeof window.duckdb === "undefined") {
    throw new Error("DuckDB WASM module not loaded");
  }

  const duckdb = window.duckdb;
  const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
  const bundles = duckdb.getJsDelivrBundles();
  const worker = await duckdb.createWorker(bundles.mvp.mainWorker);
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundles.mvp.mainModule);
  const connection = await db.connect();

  // Load external database file
  const response = await fetch("./data/rental_sales.duckdb");
  if (!response.ok) {
    throw new Error(`Failed to fetch database: ${response.status}`);
  }

  const dbBuffer = await response.arrayBuffer();
  await db.registerFileBuffer("rental_sales.duckdb", new Uint8Array(dbBuffer));
  await connection.query("ATTACH 'rental_sales.duckdb' AS rental_sales;");

  // Verify connection
  const testResult = await connection.query(
    "SELECT COUNT(*) as total_records FROM rental_sales.rental_sales;"
  );
  const recordCount = testResult.toArray()[0].total_records;
  console.log(`Connected to database with ${recordCount} records`);

  // Make globally available
  window.duckdbConnection = connection;
  window.duckdbDatabase = db;

  // Dispatch ready event
  window.dispatchEvent(new CustomEvent("duckdbReady", {
    detail: { connection, database: db, recordCount }
  }));

  return { connection, database: db };
}

// Query data with hyphen-delimited code support
async function queryRentalData(geospatialType, geospatialId, dataType = "rental") {
  if (!window.duckdbConnection) {
    throw new Error("DuckDB connection not available");
  }

  // Handle hyphen-delimited codes in database
  // Database may contain multiple codes like "CODE1-CODE2-CODE3"
  // We need to split and check if our code is in the list
  const query = `
    SELECT
      time_bucket,
      dwelling_type,
      bedrooms,
      statistic,
      value,
      EXTRACT(YEAR FROM time_bucket) as year,
      EXTRACT(QUARTER FROM time_bucket) as quarter
    FROM rental_sales.rental_sales
    WHERE geospatial_type = '${geospatialType.toLowerCase()}'
      AND list_contains(string_split(geospatial_codes, '-'), '${geospatialId}')
      AND data_type = '${dataType}'
      AND statistic = 'median'
      AND value IS NOT NULL
    ORDER BY time_bucket, dwelling_type, bedrooms;
  `;

  const result = await window.duckdbConnection.query(query);
  const rows = result.toArray();

  console.log(`Found ${rows.length} records for ${geospatialType} ${geospatialId}`);

  return processQueryResults(rows);
}
```

**7. Chart Integration with Plotly**

```javascript
// Create area chart from query results
async function createAreaChart(containerId, geoType, geoId, dataType, displayName) {
  const data = await queryRentalData(geoType, geoId, dataType);

  if (data.dates.length === 0) {
    document.getElementById(containerId).innerHTML =
      '<p style="padding: 20px; text-align: center; color: #666;">No data available</p>';
    return;
  }

  // Prepare traces for Plotly
  const traces = Object.keys(data.series).map(seriesKey => {
    return {
      x: data.dates,
      y: data.series[seriesKey],
      name: seriesKey,
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      line: { color: getSeriesColor(seriesKey) }
    };
  });

  const layout = {
    title: `${displayName} - ${dataType === 'rental' ? 'Weekly Rent' : 'Sales Price'}`,
    xaxis: { title: 'Date' },
    yaxis: { title: dataType === 'rental' ? 'Weekly Rent ($)' : 'Sales Price ($)' },
    height: 300,
    margin: { t: 40, r: 20, b: 40, l: 60 }
  };

  Plotly.newPlot(containerId, traces, layout, { responsive: true });
}

function getSeriesColor(seriesKey) {
  if (seriesKey === "All Properties") return "#1976D2";

  // House series: green tones
  if (seriesKey.startsWith("House-")) {
    if (seriesKey.includes("-1")) return "#A5D6A7";
    if (seriesKey.includes("-2")) return "#81C784";
    if (seriesKey.includes("-3")) return "#4CAF50";
    if (seriesKey.includes("-4")) return "#388E3C";
    if (seriesKey.includes("-5")) return "#2E7D32";
    return "#4CAF50";
  }

  // Unit series: orange tones
  if (seriesKey.startsWith("Unit-")) {
    if (seriesKey.includes("-1")) return "#FFCC80";
    if (seriesKey.includes("-2")) return "#FFB74D";
    if (seriesKey.includes("-3")) return "#FF9800";
    if (seriesKey.includes("-4")) return "#F57C00";
    if (seriesKey.includes("-5")) return "#E65100";
    return "#FF9800";
  }

  return "#666666";
}
```

##### Key Geospatial Patterns

**1. External Configuration**: Use JSON files for layer definitions, enabling non-developer updates

**2. Color Reference System**: `"color:colorName"` allows centralized color management

**3. Dynamic Data Loading**: Lazy-load GeoJSON files and process on demand

**4. Multi-Selection Management**: Type-based limits prevent cluttered selections

**5. DuckDB Integration**:
   - Load external `.duckdb` files for analytics
   - Use `list_contains(string_split())` for hyphen-delimited code matching
   - Dispatch custom events when database ready

**6. Plotly Charts**: Integrate charts directly into selection cards

**7. MapLibre Base Maps**: Use `mapStyle` property for various base map styles:
   - CARTO Dark Matter: `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json`
   - CARTO Positron: `https://basemaps.cartocdn.com/gl/positron-gl-style/style.json`
   - OpenStreetMap: Various providers available

##### File Structure

```
sites/webapp/
├── index.html
├── scripts.js
├── layers_config.json          # Layer definitions
├── geospatial_mappings.js      # Code mappings
├── Makefile
├── data/
│   ├── 5.geojson               # Isochrone data
│   ├── 15.geojson
│   ├── postcodes.geojson       # Boundary polygons
│   ├── lga_boundaries.geojson
│   ├── sal_suburbs.geojson
│   ├── stops_train.geojson     # Point data
│   ├── stops_tram.geojson
│   └── rental_sales.duckdb     # Analytics database
└── sql/
    ├── lga_template.sql        # Query templates
    ├── postcode_template.sql
    └── sa2_template.sql
```

##### Performance Considerations

**Layer Management:**
- Use `visible` property for toggling layers (don't recreate)
- Load large GeoJSON files asynchronously
- Process features once and cache results

**DuckDB Queries:**
- Use indexed columns for fast lookups
- Batch queries when possible
- Cache query results in JavaScript

**Memory Management:**
- Dispose of old layers before creating new ones
- Limit selection count to prevent memory issues
- Use lightweight GeoJSON (avoid excessive precision)

##### Testing Considerations

- Wait for `duckdbReady` event before testing queries
- Test with various selection combinations
- Verify layer toggle behavior
- Test chart rendering with different data types
- Validate hyphen-delimited code matching

##### Complete Integration Example

See `sites/webapp/` in the isochrones project for a production implementation featuring:
- 12 GeoJSON layers (isochrones, boundaries, transport networks, real estate)
- DuckDB with 297K rental/sales records
- Interactive charts with rental vs sales toggle
- Multi-selection with type-based limits
- Hyphen-delimited geospatial code handling
- MapLibre GL base map integration

---

#### Pattern 2B: Parquet Layer Loading with Progressive Tracking

For projects with large geospatial datasets (100MB+ GeoJSON), migrating to Apache Parquet format provides significant benefits: 80%+ file size reduction, columnar storage efficiency, and browser-based SQL query capabilities through DuckDB's spatial extension.

##### Architecture Overview

**Data Flow:**
```
Parquet Files → DuckDB WASM + Spatial Extension → ST_AsGeoJSON → GeoJsonLayer → Deck.GL
```

**Key Components:**
1. **DuckDB WASM**: In-browser SQL database with spatial extension
2. **Apache Parquet**: Columnar storage format (81% smaller than GeoJSON)
3. **Progressive Loading Tracker**: Step-based progress with substep support
4. **Parallel Layer Loading**: Concurrent loading with exponential backoff retry
5. **Custom Event Coordination**: `duckdbReady` event for async initialization

##### Parquet Layer Configuration

Create a JSON configuration file for Parquet layers:

**`parquet_layers_config.json`:**
```json
{
  "layers": [
    {
      "id": "isochrones-5min-parquet",
      "displayName": "5-minute Walking",
      "parquetPath": "./data/5.parquet",
      "options": {
        "filled": true,
        "stroked": true,
        "extruded": false,
        "pickable": false,
        "getFillColor": [0, 200, 100, 20],
        "getLineColor": [0, 150, 75, 200],
        "getLineWidth": 1,
        "lineWidthMinPixels": 1,
        "autoHighlight": false,
        "highlightColor": [255, 150, 0, 120],
        "visible": true,
        "transitions": {
          "getFillColor": 200
        }
      }
    },
    {
      "id": "real-estate-candidates-parquet",
      "displayName": "Property Candidates",
      "parquetPath": "./data/all_candidates.parquet",
      "options": {
        "pickable": true,
        "opacity": 0.8,
        "stroked": true,
        "filled": true,
        "getPointRadius": 20,
        "pointRadiusMinPixels": 10,
        "pointRadiusMaxPixels": 30,
        "lineWidthMinPixels": 2,
        "lineWidthMaxPixels": 6,
        "getFillColor": "ptv_walkability_colour",
        "getLineColor": [255, 255, 255, 255],
        "getLineWidth": 2,
        "autoHighlight": true,
        "highlightColor": [255, 150, 0, 120],
        "visible": true
      }
    }
  ]
}
```

##### Progressive Loading Tracker Pattern

Implement a step-based tracker with substep support for detailed progress:

```javascript
const loadingSteps = {
  steps: [
    { id: 'duckdb-wasm', name: 'Loading DuckDB library', status: 'pending' },
    { id: 'duckdb-init', name: 'Initializing database', status: 'pending' },
    { id: 'spatial-ext', name: 'Loading spatial extension', status: 'pending' },
    { id: 'rental-db', name: 'Loading rental database', status: 'pending' },
    { id: 'db-verify', name: 'Verifying connection', status: 'pending' },
    { id: 'layers', name: 'Loading map layers', status: 'pending', substeps: { total: 12, completed: 0 } }
  ],

  getProgress() {
    const completed = this.steps.filter(s => s.status === 'success').length;
    return { completed, total: this.steps.length };
  },

  updateStep(id, status, errorMessage = null) {
    const step = this.steps.find(s => s.id === id);
    if (step) {
      step.status = status;
      if (errorMessage) {
        step.errorMessage = errorMessage;
      }
      this.updateUI();
    }
  },

  updateSubsteps(id, completed, total = null) {
    const step = this.steps.find(s => s.id === id);
    if (step && step.substeps) {
      step.substeps.completed = completed;
      if (total !== null) {
        step.substeps.total = total;
      }
      this.updateUI();
    }
  },

  updateUI() {
    const { completed, total } = this.getProgress();
    const currentStep = this.steps.find(s => s.status === 'loading');
    const errorStep = this.steps.find(s => s.status === 'error');
    const allComplete = completed === total;

    let message, status;

    if (errorStep) {
      // Red indicator with error message
      message = `(${completed}/${total}) Error: ${errorStep.errorMessage || errorStep.name}`;
      status = 'error';
    } else if (allComplete) {
      // Green indicator when complete
      const dbVerifyStep = this.steps.find(s => s.id === 'db-verify');
      message = dbVerifyStep.successMessage || `Connected (${completed}/${total})`;
      status = 'success';
    } else if (currentStep) {
      // Orange indicator during loading with substep progress
      message = `(${completed}/${total}) ${currentStep.name}`;
      if (currentStep.substeps && currentStep.substeps.total > 0) {
        message += ` (${currentStep.substeps.completed}/${currentStep.substeps.total})`;
      }
      status = 'loading';
    } else {
      message = `(${completed}/${total}) Loading...`;
      status = 'loading';
    }

    updateDuckDBStatus(status, message);
  }
};

// UI update function
function updateDuckDBStatus(status, message) {
  const statusIcon = document.getElementById('duckdb-status-icon');
  const statusText = document.getElementById('duckdb-status-text');

  // Update icon color: orange (loading), green (success), red (error)
  const colors = {
    loading: '#ffa500',
    success: '#4caf50',
    error: '#f44336'
  };

  if (statusIcon) {
    statusIcon.style.background = colors[status] || '#ffa500';
  }

  if (statusText) {
    statusText.textContent = message;
  }
}
```

##### DuckDB Initialization with Spatial Extension

Initialize DuckDB WASM with spatial extension for Parquet geometry conversion:

```javascript
async function initializeDuckDB() {
  loadingSteps.updateStep('duckdb-wasm', 'loading');

  try {
    // Wait for DuckDB WASM module
    let retries = 20;
    while (retries > 0 && typeof window.duckdb === "undefined") {
      await new Promise(resolve => setTimeout(resolve, 100));
      retries--;
    }

    if (typeof window.duckdb === "undefined") {
      throw new Error("DuckDB WASM module failed to load");
    }

    loadingSteps.updateStep('duckdb-wasm', 'success');
    loadingSteps.updateStep('duckdb-init', 'loading');

    // Initialize DuckDB instance
    const duckdb = window.duckdb;
    const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
    const bundles = duckdb.getJsDelivrBundles();
    const worker = await duckdb.createWorker(bundles.mvp.mainWorker);
    const db = new duckdb.AsyncDuckDB(logger, worker);
    await db.instantiate(bundles.mvp.mainModule);
    const connection = await db.connect();

    loadingSteps.updateStep('duckdb-init', 'success');
    loadingSteps.updateStep('spatial-ext', 'loading');

    // Install and load spatial extension for ST_AsGeoJSON
    await connection.query("INSTALL spatial");
    await connection.query("LOAD spatial");

    loadingSteps.updateStep('spatial-ext', 'success');

    // Make globally available
    window.duckdbConnection = connection;
    window.duckdbDatabase = db;

    // Dispatch ready event for coordination
    window.dispatchEvent(new CustomEvent("duckdbReady", {
      detail: { connection, database: db }
    }));

    console.log("DuckDB WASM with spatial extension initialized");
    return { connection, database: db };

  } catch (error) {
    const stepId = loadingSteps.steps.find(s => s.status === 'loading')?.id || 'duckdb-wasm';
    loadingSteps.updateStep(stepId, 'error', error.message);
    throw error;
  }
}
```

##### Parallel Parquet Layer Loading with Retry Logic

Load multiple Parquet layers concurrently with exponential backoff retry:

```javascript
// Retry with exponential backoff
async function retryWithBackoff(fn, retries = 3, delay = 1000) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === retries - 1) throw error;
      console.warn(`Retry ${i + 1}/${retries} after ${delay}ms:`, error.message);
      await new Promise(resolve => setTimeout(resolve, delay));
      delay *= 2; // Exponential backoff: 1s, 2s, 4s
    }
  }
}

// Create Parquet layer using DuckDB spatial extension
async function createParquetLayer(layerConfig) {
  const conn = window.duckdbConnection;

  if (!conn) {
    throw new Error("DuckDB connection not initialized");
  }

  // Load Parquet file into DuckDB
  const tableName = `layer_${layerConfig.id.replace(/-/g, '_')}`;

  await retryWithBackoff(async () => {
    await conn.query(`
      CREATE OR REPLACE TABLE ${tableName} AS
      SELECT * FROM read_parquet('${layerConfig.parquetPath}')
    `);
  });

  // Convert geometries to GeoJSON using ST_AsGeoJSON
  const result = await conn.query(`
    SELECT ST_AsGeoJSON(geometry) as geojson_geometry, *
    FROM ${tableName}
  `);

  const rows = result.toArray();

  // Convert to GeoJSON FeatureCollection
  const features = rows.map(row => {
    const geojson = JSON.parse(row.geojson_geometry);

    return {
      type: "Feature",
      geometry: geojson,
      properties: Object.fromEntries(
        Object.entries(row).filter(([key]) => key !== 'geojson_geometry' && key !== 'geometry')
      )
    };
  });

  // Handle dynamic property-based colors
  let processedOptions = { ...layerConfig.options };

  if (processedOptions.getFillColor === "ptv_walkability_colour") {
    processedOptions.getFillColor = (d) => {
      const hex = d.properties?.ptv_walkability_colour || '#FFFFFF';
      return hexToRgbA(hex) || [255, 255, 255, 255];
    };
  }

  // Create GeoJsonLayer from Parquet data
  return new deck.GeoJsonLayer({
    id: layerConfig.id,
    data: {
      type: "FeatureCollection",
      features: features
    },
    ...processedOptions
  });
}

// Load all layers in parallel with progress tracking
async function loadAllParquetLayers() {
  loadingSteps.updateStep('layers', 'loading');

  try {
    // Fetch layer configuration
    const configResponse = await fetch('./parquet_layers_config.json');
    const config = await configResponse.json();

    loadingSteps.updateSubsteps('layers', 0, config.layers.length);

    // Load layers in parallel
    const layerPromises = config.layers.map(async (layerConfig, index) => {
      try {
        const layer = await createParquetLayer(layerConfig);
        loadingSteps.updateSubsteps('layers', index + 1);
        console.log(`✓ Loaded layer: ${layerConfig.displayName}`);
        return layer;
      } catch (error) {
        console.error(`✗ Failed to load layer: ${layerConfig.displayName}`, error);
        loadingSteps.updateSubsteps('layers', index + 1);
        return null; // Return null for failed layers
      }
    });

    const layers = (await Promise.all(layerPromises)).filter(Boolean);

    loadingSteps.updateStep('layers', 'success');

    // Update Deck.GL instance
    window.deckgl.setProps({ layers });

    console.log(`Loaded ${layers.length}/${config.layers.length} Parquet layers`);
    return layers;

  } catch (error) {
    loadingSteps.updateStep('layers', 'error', error.message);
    throw error;
  }
}

// Initialize on DuckDB ready
window.addEventListener('duckdbReady', () => {
  loadAllParquetLayers().catch(error => {
    console.error("Failed to load Parquet layers:", error);
  });
});
```

##### Color Conversion Utilities

```javascript
// Convert hex color to RGBA array
function hexToRgbA(hex) {
  if (!hex || typeof hex !== 'string') return null;

  hex = hex.replace('#', '');

  if (hex.length === 6) {
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return [r, g, b, 255];
  }

  return null;
}
```

##### Complete Integration Pattern

**HTML Setup:**
```html
<!-- DuckDB WASM -->
<script type="module">
  import * as duckdb from 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@latest/+esm';
  window.duckdb = duckdb;
</script>

<!-- Status indicator -->
<div id="duckdb-status" style="margin-bottom: 8px; padding: 6px 8px; background: #f5f5f5; border-radius: 3px;">
  <span id="duckdb-status-icon" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ffa500;"></span>
  <span id="duckdb-status-text">Loading DuckDB...</span>
</div>
```

**Initialization Flow:**
```javascript
// Full initialization sequence
async function initialize() {
  try {
    // Step 1-3: Initialize DuckDB with spatial extension
    await initializeDuckDB();

    // Step 4: Load external analytics database (optional)
    if (window.duckdbConnection) {
      loadingSteps.updateStep('rental-db', 'loading');
      await loadExternalDatabase();
      loadingSteps.updateStep('rental-db', 'success');
    }

    // Step 5: Verify connection
    loadingSteps.updateStep('db-verify', 'loading');
    const result = await window.duckdbConnection.query("SELECT 1 as test");
    const testValue = result.toArray()[0].test;

    if (testValue === 1n || testValue === 1) {
      const dbVerifyStep = loadingSteps.steps.find(s => s.id === 'db-verify');
      dbVerifyStep.successMessage = "Connected";
      loadingSteps.updateStep('db-verify', 'success');
    }

    // Step 6: Load Parquet layers (triggered by duckdbReady event)
    // Handled by event listener above

  } catch (error) {
    console.error("Initialization failed:", error);
    throw error;
  }
}

// Start initialization
document.addEventListener('DOMContentLoaded', () => {
  initialize();
});
```

##### Key Implementation Patterns

**1. Progressive Loading Tracker:**
- Shows overall progress: `(3/6) Loading spatial extension`
- Displays substep progress: `(5/6) Loading map layers (8/12)`
- Visual status indicators: Orange (loading), Green (success), Red (error)
- Error messages displayed on failure

**2. Parquet + DuckDB Spatial:**
- Use `read_parquet()` to load Parquet files into DuckDB tables
- Use `ST_AsGeoJSON(geometry)` to convert geometries to GeoJSON
- Convert query results to GeoJSON FeatureCollection format
- Create Deck.GL GeoJsonLayer from converted data

**3. Parallel Loading with Retry:**
- Load multiple layers concurrently with `Promise.all()`
- Exponential backoff retry: 1s, 2s, 4s delays
- Continue loading remaining layers if individual layers fail
- Track progress with substep updates

**4. Custom Event Coordination:**
- Dispatch `duckdbReady` event after DuckDB initialization
- Use event listener to trigger layer loading
- Allows decoupled initialization sequence

**5. File Size Optimization:**
- **Before**: 12 GeoJSON files @ 137MB total
- **After**: 12 Parquet files @ 26MB total (81% reduction)
- Faster downloads, less bandwidth, better performance

##### Performance Considerations

**Parquet Loading:**
- Parquet files load 3-5x faster than equivalent GeoJSON
- DuckDB spatial extension adds ~1-2 seconds to initialization
- ST_AsGeoJSON conversion is fast (<100ms per layer)
- Columnar format enables efficient filtering and querying

**Memory Management:**
- DuckDB creates temporary tables for each layer
- Drop tables after conversion to free memory: `DROP TABLE ${tableName}`
- Consider batching for very large datasets (>100k features)

**Browser Caching:**
- Parquet files are cached by browser
- DuckDB spatial extension is cached
- Subsequent loads are 10x faster

##### Testing Considerations

- Wait for `duckdbReady` event before testing layer interactions
- Test retry logic with network throttling
- Verify substep progress updates during layer loading
- Test error handling with invalid Parquet files
- Validate color conversion for property-based colors
- Check memory usage with large Parquet datasets

##### File Structure

```
sites/webapp/
├── index.html
├── scripts.js
├── parquet_layers_config.json   # Parquet layer definitions
├── Makefile
├── data/
│   ├── 5.parquet                # Isochrone data (was 5.geojson)
│   ├── 15.parquet               # 81% smaller than GeoJSON
│   ├── postcodes.parquet        # Boundary polygons
│   ├── lga_boundaries.parquet
│   ├── sal_suburbs.parquet
│   ├── stops_train.parquet      # Point data
│   ├── stops_tram.parquet
│   ├── candidates.parquet       # Property data
│   └── rental_sales.duckdb      # Analytics database
```

##### Migration from GeoJSON to Parquet

**Python conversion script:**
```python
import geopandas as gpd

# Read GeoJSON
gdf = gpd.read_file("input.geojson")

# Write Parquet with compression
gdf.to_parquet(
    "output.parquet",
    compression="snappy",
    index=False
)

print(f"Size reduction: {os.path.getsize('input.geojson') / os.path.getsize('output.parquet'):.1f}x")
```

**Complete production example:** See `sites/webapp/` in the isochrones project for a full implementation featuring:
- 12 Parquet layers with 81% file size reduction vs GeoJSON
- Progressive loading tracker with 6 steps and 12 substeps
- Parallel layer loading with exponential backoff retry
- DuckDB spatial extension for ST_AsGeoJSON conversion
- Custom event coordination for async initialization
- Visual status indicators (orange/green/red)
- Error handling with detailed error messages

---

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