const root = document.getElementById("graph-root");
const sidebar = document.getElementById("selection-panel");
const loading = document.getElementById("graph-loading");
const viewMode = document.getElementById("graph-view-mode");

if (window.cytoscape && window.cytoscapeElk) {
  window.cytoscape.use(window.cytoscapeElk);
}

if (root) {
  if (viewMode) {
    viewMode.value = "file";
  }
  loadGraph(root.dataset.graphUrl);
}

async function loadGraph(url) {
  showLoading("Loading graph…");
  sidebar.textContent = "Loading graph…";
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error("Failed to load graph data.");
    }

    const graph = await response.json();
    if (!window.cytoscape) {
      renderFallback(graph);
      hideLoading();
      return;
    }

    const graphStates = buildGraphStates(graph);
    let currentMode = viewMode && viewMode.value === "method" ? "method" : "file";

    const cy = window.cytoscape({
      container: root,
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#f5f5f5",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": 140,
            "background-color": "#111111",
            "border-color": "#404040",
            "border-width": 1.5,
            shape: "round-rectangle",
            width: "label",
            height: "label",
            padding: "10px",
          },
        },
        {
          selector: 'node[kind = "package"]',
          style: {
            "background-color": "#0e1417",
            "background-opacity": 0.3,
            "border-color": "#4f87b5",
            "border-style": "solid",
            "border-width": 2,
            "text-valign": "top",
            "text-halign": "left",
            "text-margin-x": 14,
            "text-margin-y": 14,
            "font-size": 18,
            "font-weight": 700,
            "padding-left": 30,
            "padding-right": 30,
            "padding-top": 34,
            "padding-bottom": 30,
          },
        },
        {
          selector: 'node[kind = "file"]',
          style: {
            color: "#111111",
            "background-color": "#f3f7fb",
            "background-opacity": 0.92,
            "border-color": "#c4d4e5",
            "border-style": "solid",
            "border-width": 1.5,
            "text-valign": "top",
            "text-halign": "center",
            "text-margin-y": 12,
            "font-size": 12,
            "font-weight": 600,
            "padding-left": 20,
            "padding-right": 20,
            "padding-top": 28,
            "padding-bottom": 20,
          },
        },
        {
          selector: 'node[kind = "file"][view_mode = "file"]',
          style: {
            "text-valign": "center",
            "text-halign": "center",
            "text-margin-y": 0,
            "font-size": 13,
            "font-weight": 700,
            "text-wrap": "wrap",
            "text-max-width": 150,
            width: 180,
            height: 88,
            padding: 0,
          },
        },
        {
          selector: 'node[kind = "method"]',
          style: {
            "background-color": "#191c20",
            "border-color": "#c6d8ef",
            "border-width": 1,
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 150,
            "text-valign": "center",
            "text-halign": "center",
            width: 170,
            height: 38,
            padding: 0,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#dce8f6",
            "target-arrow-color": "#9dcbff",
            "target-arrow-shape": "triangle",
            "curve-style": "round-taxi",
            "taxi-direction": "rightward",
            "taxi-turn": "55%",
            "taxi-turn-min-distance": 32,
            "taxi-radius": 12,
            opacity: 0.82,
          },
        },
        {
          selector: ":selected",
          style: {
            "border-color": "#7ee787",
            "line-color": "#7ee787",
            "target-arrow-color": "#7ee787",
          },
        },
        {
          selector: ".is-hidden",
          style: {
            display: "none",
          },
        },
      ],
    });
    applyGraphState(cy, graphStates[currentMode], true);

    if (viewMode) {
      viewMode.addEventListener("change", () => {
        currentMode = viewMode.value === "file" ? "file" : "method";
        showLoading(`Switching to ${currentMode === "file" ? "file" : "method"} view…`);
        applyGraphState(cy, graphStates[currentMode], true);
      });
    }

    const focusNode = (event) => {
      const data = event.target.data();
      const focusedState = buildFocusedState(graphStates[currentMode], { type: "node", data });
      if (!focusedState) {
        sidebar.innerHTML = describeNode(data);
        return;
      }
      applyFocus(cy, focusedState);
      sidebar.innerHTML = describeNode(data, focusedState.summary.focus_label);
    };

    const focusEdge = (event) => {
      const data = event.target.data();
      const focusedState = buildFocusedState(graphStates[currentMode], { type: "edge", data });
      if (!focusedState) {
        sidebar.innerHTML = describeEdge(data);
        return;
      }
      applyFocus(cy, focusedState);
      sidebar.innerHTML = describeEdge(data, focusedState.summary.focus_label);
    };

    cy.on("tap", "node", focusNode);
    cy.on("click", "node", focusNode);
    cy.on("tap", "edge", focusEdge);
    cy.on("click", "edge", focusEdge);

    const clearFocus = (event) => {
      if (event.target === cy) {
        restoreFullGraph(cy, graphStates[currentMode]);
      }
    };
    cy.on("tap", clearFocus);
    cy.on("click", clearFocus);

    document.addEventListener("click", (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }
      if (!root.contains(event.target)) {
        restoreFullGraph(cy, graphStates[currentMode]);
      }
    });
  } catch (error) {
    hideLoading();
    sidebar.textContent = error instanceof Error ? error.message : "Failed to load graph data.";
  }
}

function buildGraphStates(graph) {
  const methodState = buildMethodGraphState(graph);
  return {
    method: methodState,
    file: buildFileGraphState(graph),
  };
}

function buildMethodGraphState(graph) {
  const positions = buildMethodViewPositions(graph.nodes);
  const nodes = sortedNodes(graph.nodes).map((node) => ({
    data: {
      id: node.id,
      label:
        node.kind === "file"
          ? shortFileLabel(node)
          : node.kind === "package"
            ? shortPackageLabel(node)
            : node.label,
      kind: node.kind,
      view_mode: "method",
      parent: node.parent_id || undefined,
      path: node.path,
      import_path: node.import_path,
      qualname: node.qualname,
      signature: node.signature,
      line: node.line,
    },
    position: positions.get(node.id),
  }));

  const edges = sortedEdges(graph.edges).map((edge) => ({
    data: {
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      kind: edge.kind,
      expression: edge.expression,
      line: edge.line,
      resolution: edge.resolution,
    },
  }));

  return {
    elements: [...nodes, ...edges],
    summary: {
      package_count: graph.summary.package_count,
      file_count: graph.summary.file_count,
      method_count: graph.summary.method_count,
      edge_count: graph.summary.edge_count,
      mode: "method",
    },
    layout: createLayoutConfig("method_preset"),
  };
}

function buildFileGraphState(graph) {
  const packageNodes = graph.nodes.filter((node) => node.kind === "package");
  const fileNodes = graph.nodes.filter((node) => node.kind === "file");
  const methodNodes = graph.nodes.filter((node) => node.kind === "method");

  const fileById = new Map(fileNodes.map((node) => [node.id, node]));
  const methodToFile = new Map(
    methodNodes
      .filter((node) => node.parent_id)
      .map((node) => [node.id, node.parent_id]),
  );

  const aggregatedEdges = new Map();
  for (const edge of graph.edges) {
    const sourceFileId = methodToFile.get(edge.source_id);
    const targetFileId = methodToFile.get(edge.target_id);
    if (!sourceFileId || !targetFileId || sourceFileId === targetFileId) {
      continue;
    }
    const key = `${sourceFileId}:${targetFileId}`;
    if (!aggregatedEdges.has(key)) {
      const sourceFile = fileById.get(sourceFileId);
      const targetFile = fileById.get(targetFileId);
      aggregatedEdges.set(key, {
        id: `file_edge_${key}`,
        source_id: sourceFileId,
        target_id: targetFileId,
        kind: "calls",
        line: edge.line,
        expression: `${sourceFile?.label || sourceFileId} -> ${targetFile?.label || targetFileId}`,
        resolution: "aggregated_file_transition",
        call_count: 0,
      });
    }
    aggregatedEdges.get(key).call_count += 1;
  }

  const collapsedNodes = [
    ...packageNodes.map((node) => ({
      ...node,
      label: shortPackageLabel(node),
    })),
    ...fileNodes.map((node) => ({
      ...node,
      label: shortFileLabel(node),
      kind: "file",
    })),
  ];
  const positions = buildFileViewPositions(collapsedNodes);
  const nodes = sortedNodes(collapsedNodes).map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      kind: node.kind,
      view_mode: "file",
      parent: node.parent_id || undefined,
      path: node.path,
      import_path: node.import_path,
      qualname: node.qualname,
      signature: node.signature,
      line: node.line,
    },
    position: positions.get(node.id),
  }));
  const edges = Array.from(aggregatedEdges.values())
    .sort((left, right) =>
      `${left.source_id}:${left.target_id}`.localeCompare(`${right.source_id}:${right.target_id}`),
    )
    .map((edge) => ({
    data: {
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      kind: edge.kind,
      expression: edge.expression,
      line: edge.line,
      resolution: edge.resolution,
      call_count: edge.call_count,
    },
    }));

  return {
    elements: [...nodes, ...edges],
    summary: {
      package_count: graph.summary.package_count,
      file_count: graph.summary.file_count,
      method_count: 0,
      edge_count: edges.length,
      mode: "file",
    },
    layout: createLayoutConfig("file_preset"),
  };
}

function groupBy(items, keySelector) {
  const groups = new Map();
  for (const item of items) {
    const key = keySelector(item);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(item);
  }
  return groups;
}

function describeSummary(summary) {
  return `
    <div class="selection-list">
      ${summary.focus_label ? `<div><strong>Focus</strong> ${escapeHtml(summary.focus_label)}</div>` : ""}
      <div><strong>Mode</strong> ${summary.mode === "file" ? "Files" : "Methods"}</div>
      <div><strong>Packages</strong> ${summary.package_count}</div>
      <div><strong>Files</strong> ${summary.file_count}</div>
      ${
        summary.mode === "method"
          ? `<div><strong>Methods</strong> ${summary.method_count}</div>`
          : ""
      }
      <div><strong>Edges</strong> ${summary.edge_count}</div>
    </div>
  `;
}

function describeNode(data, focusLabel) {
  return `
    <div class="selection-list">
      ${focusLabel ? `<div><strong>Focus</strong> ${escapeHtml(focusLabel)}</div>` : ""}
      <div><strong>${escapeHtml(data.kind)}</strong></div>
      <div>${escapeHtml(data.label)}</div>
      ${data.qualname ? `<div><code>${escapeHtml(data.qualname)}</code></div>` : ""}
      ${data.signature ? `<div><code>${escapeHtml(data.signature)}</code></div>` : ""}
      ${data.import_path ? `<div><strong>Import</strong> <code>${escapeHtml(data.import_path)}</code></div>` : ""}
      ${data.path ? `<div><strong>Path</strong> <code>${escapeHtml(data.path)}</code></div>` : ""}
      ${data.line ? `<div><strong>Line</strong> ${data.line}</div>` : ""}
    </div>
  `;
}

function describeEdge(data, focusLabel) {
  return `
    <div class="selection-list">
      ${focusLabel ? `<div><strong>Focus</strong> ${escapeHtml(focusLabel)}</div>` : ""}
      <div><strong>Call</strong></div>
      <div><code>${escapeHtml(data.expression)}</code></div>
      ${
        data.call_count
          ? `<div><strong>Collapsed calls</strong> ${data.call_count}</div>`
          : ""
      }
      <div><strong>Line</strong> ${data.line}</div>
      <div><strong>Resolution</strong> ${escapeHtml(data.resolution)}</div>
    </div>
  `;
}

function renderFallback(graph) {
  root.innerHTML = `
    <div class="empty-state">
      Cytoscape.js failed to load. The graph JSON is still available from this page.
    </div>
  `;
  sidebar.innerHTML = describeSummary(graph.summary);
}

function showLoading(message) {
  if (!loading) {
    return;
  }
  const text = loading.querySelector(".graph-loading__text");
  if (text) {
    text.textContent = message;
  }
  loading.classList.remove("is-hidden");
}

function hideLoading() {
  if (!loading) {
    return;
  }
  loading.classList.add("is-hidden");
}

function applyGraphState(cy, state) {
  cy.elements().remove();
  cy.add(state.elements);
  cy.elements().removeClass("is-hidden");
  sidebar.innerHTML = describeSummary(state.summary);
  const layout = cy.layout(state.layout);
  layout.once("layoutstop", () => {
    hideLoading();
    cy.fit(undefined, state.layout.padding || 60);
    cy.center();
  });
  layout.run();
}

function restoreFullGraph(cy, state) {
  if (cy.elements(".is-hidden").length === 0) {
    return;
  }
  cy.elements().removeClass("is-hidden");
  sidebar.innerHTML = describeSummary(state.summary);
  cy.fit(cy.elements(), state.layout.padding || 60);
  cy.center();
}

function applyFocus(cy, state) {
  const keptIds = new Set(state.elements.map((element) => element.data.id));
  cy.elements().forEach((element) => {
    if (keptIds.has(element.id())) {
      element.removeClass("is-hidden");
      return;
    }
    element.addClass("is-hidden");
  });
  sidebar.innerHTML = describeSummary(state.summary);
  cy.fit(cy.elements(":visible"), state.layout.padding || 60);
  cy.center();
}

function buildFocusedState(state, focusTarget) {
  if (focusTarget.type === "node" && !["file", "method"].includes(focusTarget.data.kind)) {
    return null;
  }

  const nodes = state.elements.filter((element) => element.data && !("source" in element.data));
  const edges = state.elements.filter((element) => element.data && "source" in element.data);
  const nodesById = new Map(nodes.map((element) => [element.data.id, element]));
  const childNodeIdsByParent = new Map();

  for (const node of nodes) {
    const parentId = node.data.parent;
    if (!parentId) {
      continue;
    }
    if (!childNodeIdsByParent.has(parentId)) {
      childNodeIdsByParent.set(parentId, []);
    }
    childNodeIdsByParent.get(parentId).push(node.data.id);
  }

  const keptNodeIds = new Set();
  const keptEdgeIds = new Set();
  const focusSeedNodeIds = resolveFocusSeedNodeIds(
    focusTarget,
    state.summary.mode,
    childNodeIdsByParent,
  );

  for (const nodeId of focusSeedNodeIds) {
    keptNodeIds.add(nodeId);
  }

  if (focusTarget.type === "edge") {
    keptEdgeIds.add(focusTarget.data.id);
    keptNodeIds.add(focusTarget.data.source);
    keptNodeIds.add(focusTarget.data.target);
  } else {
    for (const edge of edges) {
      if (!focusSeedNodeIds.has(edge.data.source) && !focusSeedNodeIds.has(edge.data.target)) {
        continue;
      }
      keptEdgeIds.add(edge.data.id);
      keptNodeIds.add(edge.data.source);
      keptNodeIds.add(edge.data.target);
    }
  }

  expandAncestorNodes(keptNodeIds, nodesById);

  const focusedNodes = nodes.filter((node) => keptNodeIds.has(node.data.id));
  const focusedEdges = edges.filter((edge) => keptEdgeIds.has(edge.data.id));
  return {
    elements: [...focusedNodes, ...focusedEdges],
    summary: buildFocusSummary(state.summary.mode, focusedNodes, focusedEdges, focusTarget.data),
    layout: state.layout,
  };
}

function resolveFocusSeedNodeIds(focusTarget, mode, childNodeIdsByParent) {
  if (focusTarget.type !== "node") {
    return new Set();
  }

  const seedNodeIds = new Set([focusTarget.data.id]);
  if (mode === "method" && focusTarget.data.kind === "file") {
    const methodChildIds = childNodeIdsByParent.get(focusTarget.data.id) || [];
    for (const nodeId of methodChildIds) {
      seedNodeIds.add(nodeId);
    }
  }
  return seedNodeIds;
}

function expandAncestorNodes(nodeIds, nodesById) {
  const pending = [...nodeIds];
  while (pending.length > 0) {
    const nodeId = pending.pop();
    const node = nodesById.get(nodeId);
    const parentId = node?.data?.parent;
    if (!parentId || nodeIds.has(parentId)) {
      continue;
    }
    nodeIds.add(parentId);
    pending.push(parentId);
  }
}

function buildFocusSummary(mode, nodes, edges, focusData) {
  return {
    mode,
    package_count: nodes.filter((node) => node.data.kind === "package").length,
    file_count: nodes.filter((node) => node.data.kind === "file").length,
    method_count: mode === "method"
      ? nodes.filter((node) => node.data.kind === "method").length
      : 0,
    edge_count: edges.length,
    focus_label: focusSummaryLabel(focusData),
  };
}

function focusSummaryLabel(data) {
  if (data.kind === "file") {
    return `Connected files for ${data.label}`;
  }
  if (data.kind === "method") {
    return `Connected methods for ${data.label}`;
  }
  return `Call path ${data.label || data.expression || ""}`.trim();
}

function shortFileLabel(node) {
  if (node.import_path) {
    const parts = node.import_path.split(".");
    return parts[parts.length - 1] || node.import_path;
  }
  return node.label;
}

function shortPackageLabel(node) {
  if (node.label) {
    const parts = node.label.split(".");
    return parts[parts.length - 1] || node.label;
  }
  return node.id;
}

function sortedNodes(nodes) {
  return [...nodes].sort((left, right) =>
    nodeSortKey(left).localeCompare(nodeSortKey(right)),
  );
}

function sortedEdges(edges) {
  return [...edges].sort((left, right) =>
    `${left.source_id}:${left.target_id}:${left.id}`.localeCompare(
      `${right.source_id}:${right.target_id}:${right.id}`,
    ),
  );
}

function nodeSortKey(node) {
  const kindOrder = { package: "0", file: "1", method: "2" };
  return [
    kindOrder[node.kind] || "9",
    node.path || "",
    node.import_path || "",
    node.qualname || "",
    node.label || "",
    node.id || "",
  ].join("|");
}

function compareLayoutNodes(left, right) {
  return nodeSortKey(left.data()).localeCompare(nodeSortKey(right.data()));
}

function createLayoutConfig(mode) {
  if (mode === "method_preset") {
    return {
      name: "preset",
      fit: true,
      padding: 120,
      animate: false,
    };
  }

  if (mode === "file_preset") {
    return {
      name: "preset",
      fit: true,
      padding: 120,
      animate: false,
    };
  }

  if (window.cytoscapeElk) {
    return {
      name: "elk",
      fit: true,
      padding: mode === "file" ? 100 : 80,
      animate: false,
      nodeDimensionsIncludeLabels: true,
      elk: {
        algorithm: "layered",
        "elk.direction": "RIGHT",
        "elk.spacing.nodeNode": mode === "file" ? 80 : 55,
        "elk.layered.spacing.nodeNodeBetweenLayers": mode === "file" ? 180 : 140,
        "elk.layered.spacing.edgeNodeBetweenLayers": mode === "file" ? 90 : 70,
        "elk.layered.spacing.edgeEdgeBetweenLayers": 40,
        "elk.layered.crossingMinimization.semiInteractive": false,
      },
      sort: compareLayoutNodes,
    };
  }

  return {
    name: "grid",
    fit: true,
    padding: 80,
    animate: false,
    condense: false,
    spacingFactor: mode === "file" ? 2.8 : 2.2,
    sort: compareLayoutNodes,
  };
}

function buildFileViewPositions(nodes) {
  const positions = new Map();
  const packages = sortedNodes(nodes.filter((node) => node.kind === "package"));
  const files = sortedNodes(nodes.filter((node) => node.kind === "file"));
  const filesByPackage = groupBy(files, (node) => node.parent_id);

  const packageGapX = 220;
  const packageGapY = 220;
  const packagePaddingX = 120;
  const packagePaddingY = 110;
  const fileGapX = 240;
  const fileGapY = 132;
  const fileBoxWidth = 180;
  const fileBoxHeight = 88;
  const packageLayouts = packages.map((pkg) => {
    const packageFiles = filesByPackage.get(pkg.id) || [];
    const fullRowWidth = Math.max(1, Math.ceil(Math.sqrt(Math.max(packageFiles.length, 1))));
    const shortRowWidth = Math.max(1, fullRowWidth - 1);
    const rowWidths = [];
    let remainingFiles = packageFiles.length;
    let rowIndex = 0;
    while (remainingFiles > 0) {
      const width = rowIndex % 2 === 0 ? fullRowWidth : shortRowWidth;
      const rowWidth = Math.min(width, remainingFiles);
      rowWidths.push(rowWidth);
      remainingFiles -= rowWidth;
      rowIndex += 1;
    }
    if (rowWidths.length === 0) {
      rowWidths.push(1);
    }
    const rows = rowWidths.length;
    const maxRowWidth = Math.max(...rowWidths);
    const width = Math.max(
      420,
      packagePaddingX * 2 + (maxRowWidth - 1) * fileGapX + fileBoxWidth,
    );
    const height = Math.max(
      300,
      packagePaddingY * 2 + (rows - 1) * fileGapY + fileBoxHeight,
    );

    return {
      pkg,
      files: packageFiles,
      rowWidths,
      width,
      height,
      originX: 0,
      originY: 0,
    };
  });

  let cursorX = 180;
  let cursorY = 180;
  applyPackagePacking(packageLayouts, packageGapX, packageGapY, cursorX, cursorY);

  for (const layout of packageLayouts) {
    positions.set(layout.pkg.id, {
      x: layout.originX + layout.width / 2,
      y: layout.originY + layout.height / 2,
    });

    let fileOffset = 0;
    layout.rowWidths.forEach((rowWidth, row) => {
      const rowContentWidth = (rowWidth - 1) * fileGapX;
      const rowXOffset = (layout.width - packagePaddingX * 2 - rowContentWidth) / 2;
      for (let col = 0; col < rowWidth; col += 1) {
        const file = layout.files[fileOffset];
        if (!file) {
          break;
        }
        positions.set(file.id, {
          x: layout.originX + packagePaddingX + rowXOffset + col * fileGapX,
          y: layout.originY + packagePaddingY + row * fileGapY,
        });
        fileOffset += 1;
      }
    });
  }

  return positions;
}

function buildMethodViewPositions(nodes) {
  const positions = new Map();
  const packages = sortedNodes(nodes.filter((node) => node.kind === "package"));
  const files = sortedNodes(nodes.filter((node) => node.kind === "file"));
  const methods = sortedNodes(nodes.filter((node) => node.kind === "method"));
  const filesByPackage = groupBy(files, (node) => node.parent_id);
  const methodsByFile = groupBy(methods, (node) => node.parent_id);

  const packageGapX = 240;
  const packageGapY = 240;
  const packagePaddingX = 140;
  const packagePaddingY = 120;
  const fileGapX = 320;
  const fileGapY = 180;
  const fileBoxWidth = 240;
  const methodGapY = 54;
  const methodStackTop = 72;
  const methodBoxHeight = 38;
  const packageLayouts = packages.map((pkg) => {
    const packageFiles = filesByPackage.get(pkg.id) || [];
    const fullRowWidth = Math.max(1, Math.ceil(Math.sqrt(Math.max(packageFiles.length, 1))));
    const shortRowWidth = Math.max(1, fullRowWidth - 1);
    const rowWidths = [];
    let remainingFiles = packageFiles.length;
    let rowIndex = 0;
    while (remainingFiles > 0) {
      const width = rowIndex % 2 === 0 ? fullRowWidth : shortRowWidth;
      const rowWidth = Math.min(width, remainingFiles);
      rowWidths.push(rowWidth);
      remainingFiles -= rowWidth;
      rowIndex += 1;
    }
    if (rowWidths.length === 0) {
      rowWidths.push(1);
    }

    const fileHeights = packageFiles.map((file) => {
      const fileMethods = methodsByFile.get(file.id) || [];
      return Math.max(130, methodStackTop + fileMethods.length * methodGapY + methodBoxHeight);
    });

    const rowHeights = [];
    let offset = 0;
    rowWidths.forEach((rowWidth, row) => {
      const slice = fileHeights.slice(offset, offset + rowWidth);
      rowHeights[row] = slice.length ? Math.max(...slice) : 130;
      offset += rowWidth;
    });

    const maxRowWidth = Math.max(...rowWidths);
    const width = Math.max(
      520,
      packagePaddingX * 2 + (maxRowWidth - 1) * fileGapX + fileBoxWidth,
    );
    const height = Math.max(
      360,
      packagePaddingY * 2 + rowHeights.reduce((sum, value) => sum + value, 0) + (rowHeights.length - 1) * fileGapY,
    );

    return {
      pkg,
      files: packageFiles,
      rowWidths,
      rowHeights,
      fileHeights,
      width,
      height,
      originX: 0,
      originY: 0,
    };
  });

  let cursorX = 180;
  let cursorY = 180;
  applyPackagePacking(packageLayouts, packageGapX, packageGapY, cursorX, cursorY);

  for (const layout of packageLayouts) {
    positions.set(layout.pkg.id, {
      x: layout.originX + layout.width / 2,
      y: layout.originY + layout.height / 2,
    });

    let fileOffset = 0;
    let rowY = layout.originY + packagePaddingY;
    layout.rowWidths.forEach((rowWidth, rowIndex) => {
      const rowContentWidth = (rowWidth - 1) * fileGapX;
      const rowXOffset = (layout.width - packagePaddingX * 2 - rowContentWidth) / 2;

      for (let col = 0; col < rowWidth; col += 1) {
        const file = layout.files[fileOffset];
        if (!file) {
          break;
        }
        const fileX = layout.originX + packagePaddingX + rowXOffset + col * fileGapX;
        const fileY = rowY;
        positions.set(file.id, { x: fileX, y: fileY });

        const fileMethods = methodsByFile.get(file.id) || [];
        fileMethods.forEach((method, methodIndex) => {
          positions.set(method.id, {
            x: fileX,
            y: fileY + methodStackTop + methodIndex * methodGapY,
          });
        });

        fileOffset += 1;
      }

      rowY += layout.rowHeights[rowIndex] + fileGapY;
    });
  }

  return positions;
}

function applyPackagePacking(packageLayouts, packageGapX, packageGapY, startX, startY) {
  const fullRowWidth = Math.max(1, Math.ceil(Math.sqrt(Math.max(packageLayouts.length, 1))));
  const shortRowWidth = Math.max(1, fullRowWidth - 1);
  const rowLayouts = [];
  let remaining = packageLayouts.length;
  let offset = 0;
  let rowIndex = 0;

  while (remaining > 0) {
    const capacity = rowIndex % 2 === 0 ? fullRowWidth : shortRowWidth;
    const rowWidth = Math.min(capacity, remaining);
    rowLayouts.push(packageLayouts.slice(offset, offset + rowWidth));
    offset += rowWidth;
    remaining -= rowWidth;
    rowIndex += 1;
  }

  let currentY = startY;
  for (const row of rowLayouts) {
    const rowWidth = row.reduce((sum, layout) => sum + layout.width, 0) + Math.max(0, row.length - 1) * packageGapX;
    let currentX = startX + Math.max(0, (2800 - rowWidth) / 2);
    let rowHeight = 0;

    for (const layout of row) {
      layout.originX = currentX;
      layout.originY = currentY;
      currentX += layout.width + packageGapX;
      rowHeight = Math.max(rowHeight, layout.height);
    }

    currentY += rowHeight + packageGapY;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
