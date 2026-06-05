const root = document.getElementById("graph-root");
const hovercard = document.getElementById("graph-hovercard");
const loading = document.getElementById("graph-loading");
const viewMode = document.getElementById("graph-view-mode");
const proposalStatus = document.getElementById("graph-proposal-status");

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
  showLoading("Scanning project…");
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) {
      showGraphError(payload?.error?.message || "Failed to load graph data.");
      hideLoading();
      return;
    }
    renderProposalStatus(payload.graph?.active_proposal, payload.graph?.warnings || []);
    if (!window.cytoscape) {
      renderFallback(payload);
      hideLoading();
      return;
    }

    showLoading("Rendering graph…");
    const graphStates = buildGraphStates(payload);
    let currentMode = viewMode && viewMode.value === "method" ? "method" : "file";

    const cy = window.cytoscape({
      container: root,
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#f8f2e9",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": 140,
            "background-color": "#0d1720",
            "border-color": "#405463",
            "border-width": 1.5,
            shape: "round-rectangle",
            width: "label",
            height: "label",
            padding: "10px",
          },
        },
        {
          selector: 'node[iteration_state = "add"]',
          style: {
            "border-color": "#7ee787",
            "background-color": "#173324",
          },
        },
        {
          selector: 'node[iteration_state = "change"]',
          style: {
            "border-color": "#f1c95b",
            "background-color": "#2a2416",
          },
        },
        {
          selector: 'node[iteration_state = "remove"]',
          style: {
            "border-color": "#ff6b6b",
            "background-color": "#311819",
          },
        },
        {
          selector: 'node[node_type = "package"]',
          style: {
            "background-color": "#13212d",
            "background-opacity": 0.44,
            "border-color": "#f36d61",
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
            color: "#fff6e8",
          },
        },
        {
          selector: 'node[node_type = "file"]',
          style: {
            color: "#11202a",
            "background-color": "#f5efdf",
            "background-opacity": 0.92,
            "border-color": "#d8c8a7",
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
          selector: 'node[node_type = "file"][view_mode = "file"]',
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
          selector: 'node[node_type = "method"]',
          style: {
            "background-color": "#162633",
            "border-color": "#7fcfb6",
            "border-width": 1,
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 220,
            "text-valign": "center",
            "text-halign": "center",
            width: 240,
            height: 52,
            padding: 0,
            color: "#eff7f3",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#b89490",
            "target-arrow-color": "#f3b86c",
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
          selector: 'edge[iteration_state = "add"]',
          style: {
            "line-color": "#7ee787",
            "target-arrow-color": "#7ee787",
          },
        },
        {
          selector: 'edge[iteration_state = "change"]',
          style: {
            "line-color": "#f1c95b",
            "target-arrow-color": "#f1c95b",
          },
        },
        {
          selector: 'edge[iteration_state = "remove"]',
          style: {
            "line-color": "#ff6b6b",
            "target-arrow-color": "#ff6b6b",
          },
        },
        {
          selector: "node:selected, node.is-hovered",
          style: {
            "border-color": "#7ee787",
            "border-width": 3,
          },
        },
        {
          selector: "edge:selected, edge.is-hovered",
          style: {
            "line-color": "#7ee787",
            width: 3,
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
        hideHovercard();
        showLoading(`Rendering ${currentMode === "file" ? "file" : "method"} view…`);
        applyGraphState(cy, graphStates[currentMode], true);
      });
    }

    const focusNode = (event) => {
      const data = event.target.data();
      const focusedState = buildFocusedState(graphStates[currentMode], { type: "node", data });
      if (!focusedState) {
        return;
      }
      hideHovercard();
      applyFocus(cy, focusedState);
    };

    const focusEdge = (event) => {
      const data = event.target.data();
      const focusedState = buildFocusedState(graphStates[currentMode], { type: "edge", data });
      if (!focusedState) {
        return;
      }
      hideHovercard();
      applyFocus(cy, focusedState);
    };

    cy.on("tap", "node", focusNode);
    cy.on("click", "node", focusNode);
    cy.on("tap", "edge", focusEdge);
    cy.on("click", "edge", focusEdge);
    cy.on("mouseover", "node, edge", (event) => {
      event.target.addClass("is-hovered");
      if (event.target.isEdge()) {
        highlightEdgeEndpoints(event.target);
        showHovercard(event.renderedPosition || event.position, describeEdge(event.target.data()));
        return;
      }
      showHovercard(
        event.renderedPosition || event.position,
        describeNodeHover(
          event.target.data(),
          collectNodeConnections(cy, event.target, currentMode),
        ),
      );
    });
    cy.on("mousemove", "node", (event) => {
      showHovercard(
        event.renderedPosition || event.position,
        describeNodeHover(
          event.target.data(),
          collectNodeConnections(cy, event.target, currentMode),
        ),
      );
    });
    cy.on("mousemove", "edge", (event) => {
      highlightEdgeEndpoints(event.target);
      showHovercard(event.renderedPosition || event.position, describeEdge(event.target.data()));
    });
    cy.on("mouseout", "node, edge", (event) => {
      event.target.removeClass("is-hovered");
      if (event.target.isEdge()) {
        clearEdgeEndpointHighlights(cy);
        hideHovercard();
        return;
      }
      hideHovercard();
    });

    const clearFocus = (event) => {
      if (event.target === cy) {
        hideHovercard();
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
        hideHovercard();
        restoreFullGraph(cy, graphStates[currentMode]);
      }
    });
  } catch (error) {
    hideLoading();
    hideHovercard();
  }
}

function buildGraphStates(payload) {
  const methodState = buildMethodGraphState(payload.graph);
  return {
    method: methodState,
    file: buildFileGraphState(payload.graph),
  };
}

function buildMethodGraphState(graph) {
  const positions = buildMethodViewPositions(graph.nodes);
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const nodes = sortedNodes(graph.nodes).map((node) => ({
    data: {
      id: node.id,
      label:
        nodeType(node) === "file"
          ? shortFileLabel(node)
          : nodeType(node) === "package"
            ? shortPackageLabel(node)
            : node.label,
      node_type: nodeType(node),
      view_mode: "method",
      parent: node.parent_id || undefined,
      path: node.path,
      import_path: node.import_path,
      qualname: node.qualname,
      signature: node.signature,
      line: node.line,
      iteration_state: node.iteration_state || "present",
    },
    position: positions.get(node.id),
  }));

  const edges = sortedEdges(graph.edges).map((edge) => ({
    data: {
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      source_label: edgeEndpointLabel(nodeById.get(edge.source_id)),
      target_label: edgeEndpointLabel(nodeById.get(edge.target_id)),
      line: edge.line,
      iteration_state: edge.iteration_state || "present",
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
  const packageNodes = graph.nodes
    .filter((node) => nodeType(node) === "package")
    .map((pkg) => ({
      id: pkg.id,
      label: pkg.label,
      path: pkg.path,
      node_type: "package",
      iteration_state: pkg.iteration_state || "present",
    }));
  const fileNodes = graph.nodes
    .filter((node) => nodeType(node) === "file")
    .map((file) => ({
      id: file.id,
      label: file.import_path,
      parent_id: file.parent_id,
      path: file.path,
      import_path: file.import_path,
      node_type: "file",
      iteration_state: file.iteration_state || "present",
    }));
  const methodNodes = graph.nodes.filter((node) => nodeType(node) === "method");
  const methodById = new Map(methodNodes.map((node) => [node.id, node]));
  const fileById = new Map(fileNodes.map((node) => [node.id, node]));
  const collapsedNodes = [
    ...packageNodes.map((node) => ({
      ...node,
      label: shortPackageLabel(node),
    })),
    ...fileNodes.map((node) => ({
      ...node,
      label: shortFileLabel(node),
    })),
  ];
  const positions = buildFileViewPositions(collapsedNodes);
  const nodes = sortedNodes(collapsedNodes).map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      node_type: nodeType(node),
      view_mode: "file",
      parent: node.parent_id || undefined,
      path: node.path,
      import_path: node.import_path,
      qualname: node.qualname,
      signature: node.signature,
      line: node.line,
      iteration_state: node.iteration_state || "present",
    },
    position: positions.get(node.id),
  }));
  const transitionsById = new Map();
  graph.edges.forEach((edge) => {
    const sourceMethod = methodById.get(edge.source_id);
    const targetMethod = methodById.get(edge.target_id);
    if (!sourceMethod || !targetMethod) {
      return;
    }
    const sourceFileId = sourceMethod.parent_id;
    const targetFileId = targetMethod.parent_id;
    if (!sourceFileId || !targetFileId || sourceFileId === targetFileId) {
      return;
    }
    const sourceFile = fileById.get(sourceFileId);
    const targetFile = fileById.get(targetFileId);
    if (!sourceFile || !targetFile) {
      return;
    }
    const transitionId = `transition_${sourceFileId}_${targetFileId}`;
    const current = transitionsById.get(transitionId);
    if (!current) {
      transitionsById.set(transitionId, {
        id: transitionId,
        source_id: sourceFileId,
        target_id: targetFileId,
        source_label: edgeEndpointLabel(sourceFile),
        target_label: edgeEndpointLabel(targetFile),
        referenced_methods: targetMethod.qualname ? [targetMethod.qualname] : [],
        iteration_state: edge.iteration_state || "present",
      });
      return;
    }
    if (targetMethod.qualname && !current.referenced_methods.includes(targetMethod.qualname)) {
      current.referenced_methods.push(targetMethod.qualname);
    }
    current.iteration_state = mergeTransitionState(current.iteration_state, edge.iteration_state || "present");
  });
  const aggregatedEdges = [...transitionsById.values()].map((transition) => ({
    ...transition,
    referenced_methods: [...transition.referenced_methods].sort(),
  }));
  const edges = aggregatedEdges
    .sort((left, right) => left.id.localeCompare(right.id))
    .map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source_id,
        target: edge.target_id,
        source_label: edge.source_label,
        target_label: edge.target_label,
        referenced_methods: edge.referenced_methods,
        view_mode: "file",
        iteration_state: edge.iteration_state || "present",
      },
    }));

  return {
    elements: [...nodes, ...edges],
    summary: {
      package_count: packageNodes.length,
      file_count: fileNodes.length,
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

function describeEdge(data) {
  const referencedMethods = Array.isArray(data.referenced_methods)
    ? data.referenced_methods
    : [];
  return `
    <div class="hovercard-list">
      <div><strong>${data.view_mode === "file" ? "Dependency" : "Call"}</strong></div>
      <div><code>${escapeHtml(`${data.source_label} -> ${data.target_label}`)}</code></div>
      <div><strong>State</strong> ${escapeHtml(data.iteration_state || "present")}</div>
      ${
        referencedMethods.length > 0
          ? `<div><strong>Referenced Methods</strong></div><div class="hovercard-methods">${referencedMethods.map((method) => `<code>${escapeHtml(method)}</code>`).join("")}</div>`
          : ""
      }
      ${data.line ? `<div><strong>Line</strong> ${data.line}</div>` : ""}
    </div>
  `;
}

function describeNodeHover(data, connections) {
  const incoming = connections.incoming || [];
  const outgoing = connections.outgoing || [];
  return `
    <div class="hovercard-list">
      <div><strong>${escapeHtml(nodeType(data))}</strong></div>
      <div><code>${escapeHtml(data.label)}</code></div>
      <div><strong>State</strong> ${escapeHtml(data.iteration_state || "present")}</div>
      ${data.qualname ? `<div><strong>Qualified Name</strong></div><div><code>${escapeHtml(data.qualname)}</code></div>` : ""}
      ${data.import_path ? `<div><strong>Import</strong></div><div><code>${escapeHtml(data.import_path)}</code></div>` : ""}
      ${
        outgoing.length > 0
          ? `<div><strong>Outgoing</strong></div><div class="hovercard-methods">${outgoing.map((item) => `<code>${escapeHtml(item)}</code>`).join("")}</div>`
          : ""
      }
      ${
        incoming.length > 0
          ? `<div><strong>Incoming</strong></div><div class="hovercard-methods">${incoming.map((item) => `<code>${escapeHtml(item)}</code>`).join("")}</div>`
          : ""
      }
      ${
        incoming.length === 0 && outgoing.length === 0
          ? `<div><strong>Connections</strong></div><div><code>No visible links</code></div>`
          : ""
      }
    </div>
  `;
}

function renderFallback(payload) {
  root.innerHTML = `
    <div class="empty-state">
      Cytoscape.js failed to load. The graph JSON is still available from this page.
    </div>
  `;
  hideHovercard();
}

function showGraphError(message) {
  hideHovercard();
  if (proposalStatus) {
    proposalStatus.hidden = false;
    proposalStatus.classList.add("graph-proposal-status--error");
    proposalStatus.innerHTML = `<strong>Proposal blocked</strong><div>${escapeHtml(message)}</div>`;
  }
  root.innerHTML = `
    <div class="empty-state">
      ${escapeHtml(message)}
    </div>
  `;
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

function renderProposalStatus(activeProposal, warnings) {
  if (!proposalStatus) {
    return;
  }
  if (!activeProposal) {
    proposalStatus.hidden = true;
    proposalStatus.classList.remove("graph-proposal-status--error");
    proposalStatus.innerHTML = "";
    return;
  }
  const warningCount = Array.isArray(warnings) ? warnings.length : 0;
  const warningItems = Array.isArray(warnings)
    ? warnings.map((warning) => `<li>${escapeHtml(warning.message || warning.code || "Warning")}</li>`).join("")
    : "";
  proposalStatus.hidden = false;
  proposalStatus.classList.remove("graph-proposal-status--error");
  proposalStatus.innerHTML = `
    <div><strong>Active proposal</strong> ${escapeHtml(activeProposal.name)}</div>
    <div><code>${escapeHtml(activeProposal.id)}</code></div>
    <div>${warningCount} warning${warningCount === 1 ? "" : "s"}</div>
    ${warningCount > 0 ? `<ul class="graph-proposal-status__warnings">${warningItems}</ul>` : ""}
  `;
}

function mergeTransitionState(left, right) {
  if (left === right) {
    return left;
  }
  const states = new Set([left, right]);
  if (states.has("change")) {
    return "change";
  }
  if (states.has("add") && states.has("remove")) {
    return "change";
  }
  if (states.has("add") || states.has("remove")) {
    return "change";
  }
  return "present";
}

function applyGraphState(cy, state) {
  cy.elements().remove();
  cy.add(state.elements);
  cy.elements().removeClass("is-hidden");
  hideHovercard();
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
  hideHovercard();
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
  hideHovercard();
  cy.fit(cy.elements(":visible"), state.layout.padding || 60);
  cy.center();
}

function buildFocusedState(state, focusTarget) {
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

  if (focusTarget.type === "edge") {
    keptEdgeIds.add(focusTarget.data.id);
    keptNodeIds.add(focusTarget.data.source);
    keptNodeIds.add(focusTarget.data.target);
  } else {
    const focusType = nodeType(focusTarget.data);
    if (focusType === "package" || (focusType === "file" && state.summary.mode === "method")) {
      const subtreeNodeIds = collectDescendantNodeIds(
        focusTarget.data.id,
        childNodeIdsByParent,
      );
      for (const nodeId of subtreeNodeIds) {
        keptNodeIds.add(nodeId);
      }
      for (const edge of edges) {
        if (!subtreeNodeIds.has(edge.data.source) || !subtreeNodeIds.has(edge.data.target)) {
          continue;
        }
        keptEdgeIds.add(edge.data.id);
      }
    } else if (focusType === "file") {
      const focusSeedNodeIds = resolveFocusSeedNodeIds(
        focusTarget,
        state.summary.mode,
        childNodeIdsByParent,
      );
      for (const nodeId of focusSeedNodeIds) {
        keptNodeIds.add(nodeId);
      }
      for (const edge of edges) {
        if (!focusSeedNodeIds.has(edge.data.source) && !focusSeedNodeIds.has(edge.data.target)) {
          continue;
        }
        keptEdgeIds.add(edge.data.id);
        keptNodeIds.add(edge.data.source);
        keptNodeIds.add(edge.data.target);
      }
    } else if (focusType === "method") {
      const focusSeedNodeIds = resolveFocusSeedNodeIds(
        focusTarget,
        state.summary.mode,
        childNodeIdsByParent,
      );
      for (const nodeId of focusSeedNodeIds) {
        keptNodeIds.add(nodeId);
      }
      for (const edge of edges) {
        if (!focusSeedNodeIds.has(edge.data.source) && !focusSeedNodeIds.has(edge.data.target)) {
          continue;
        }
        keptEdgeIds.add(edge.data.id);
        keptNodeIds.add(edge.data.source);
        keptNodeIds.add(edge.data.target);
      }
    } else {
      return null;
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
  if (mode === "method" && nodeType(focusTarget.data) === "file") {
    const methodChildIds = childNodeIdsByParent.get(focusTarget.data.id) || [];
    for (const nodeId of methodChildIds) {
      seedNodeIds.add(nodeId);
    }
  }
  return seedNodeIds;
}

function collectDescendantNodeIds(rootNodeId, childNodeIdsByParent) {
  const nodeIds = new Set([rootNodeId]);
  const pending = [rootNodeId];
  while (pending.length > 0) {
    const nodeId = pending.pop();
    const childIds = childNodeIdsByParent.get(nodeId) || [];
    for (const childId of childIds) {
      if (nodeIds.has(childId)) {
        continue;
      }
      nodeIds.add(childId);
      pending.push(childId);
    }
  }
  return nodeIds;
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
    package_count: nodes.filter((node) => nodeType(node.data) === "package").length,
    file_count: nodes.filter((node) => nodeType(node.data) === "file").length,
    method_count: mode === "method"
      ? nodes.filter((node) => nodeType(node.data) === "method").length
      : 0,
    edge_count: edges.length,
    focus_label: focusSummaryLabel(focusData),
  };
}

function focusSummaryLabel(data) {
  if (nodeType(data) === "file") {
    return `Connected files for ${data.label}`;
  }
  if (nodeType(data) === "method") {
    return `Connected methods for ${data.label}`;
  }
  return `Call path ${data.source_label || ""} -> ${data.target_label || ""}`.trim();
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
    kindOrder[nodeType(node)] || "9",
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
  const packages = sortedNodes(nodes.filter((node) => nodeType(node) === "package"));
  const files = sortedNodes(nodes.filter((node) => nodeType(node) === "file"));
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
  const packages = sortedNodes(nodes.filter((node) => nodeType(node) === "package"));
  const files = sortedNodes(nodes.filter((node) => nodeType(node) === "file"));
  const methods = sortedNodes(nodes.filter((node) => nodeType(node) === "method"));
  const filesByPackage = groupBy(files, (node) => node.parent_id);
  const methodsByFile = groupBy(methods, (node) => node.parent_id);

  const packageGapX = 240;
  const packageGapY = 240;
  const packagePaddingX = 140;
  const packagePaddingY = 120;
  const fileGapX = 320;
  const fileGapY = 180;
  const fileBoxWidth = 300;
  const methodGapY = 64;
  const methodStackTop = 72;
  const methodBoxHeight = 52;
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

function nodeType(node) {
  if (node.node_type) {
    return node.node_type;
  }
  if (node.qualname) {
    return "method";
  }
  if (node.import_path) {
    return "file";
  }
  return "package";
}

function edgeEndpointLabel(node) {
  if (!node) {
    return "";
  }
  if (nodeType(node) === "file") {
    return shortFileLabel(node);
  }
  if (nodeType(node) === "package") {
    return shortPackageLabel(node);
  }
  return node.label || node.id;
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

function showHovercard(position, html) {
  if (!hovercard || !position) {
    return;
  }
  hovercard.innerHTML = html;
  hovercard.hidden = false;
  const offsetX = 18;
  const offsetY = 18;
  const cardWidth = hovercard.offsetWidth || 320;
  const cardHeight = hovercard.offsetHeight || 180;
  const maxLeft = Math.max(16, root.clientWidth - cardWidth - 16);
  const maxTop = Math.max(16, root.clientHeight - cardHeight - 16);
  const left = Math.min(maxLeft, Math.max(16, position.x + offsetX));
  const top = Math.min(maxTop, Math.max(16, position.y + offsetY));
  hovercard.style.left = `${left}px`;
  hovercard.style.top = `${top}px`;
}

function hideHovercard() {
  if (!hovercard) {
    return;
  }
  hovercard.hidden = true;
  hovercard.innerHTML = "";
}

function highlightEdgeEndpoints(edge) {
  const source = edge.source();
  const target = edge.target();
  if (source) {
    source.addClass("is-hovered");
  }
  if (target) {
    target.addClass("is-hovered");
  }
}

function clearEdgeEndpointHighlights(cy) {
  cy.nodes().removeClass("is-hovered");
}

function collectNodeConnections(cy, node, mode) {
  const nodeIds = collectConnectionNodeIds(node, mode);
  const incoming = [];
  const outgoing = [];
  const seenIncoming = new Set();
  const seenOutgoing = new Set();

  cy.edges(":visible").forEach((edge) => {
    const sourceId = edge.data("source");
    const targetId = edge.data("target");
    const label = `${edge.data("source_label")} -> ${edge.data("target_label")}`;
    if (nodeIds.has(sourceId)) {
      if (!seenOutgoing.has(label)) {
        seenOutgoing.add(label);
        outgoing.push(label);
      }
    }
    if (nodeIds.has(targetId)) {
      if (!seenIncoming.has(label)) {
        seenIncoming.add(label);
        incoming.push(label);
      }
    }
  });

  incoming.sort();
  outgoing.sort();
  return { incoming, outgoing };
}

function collectConnectionNodeIds(node, mode) {
  const ids = new Set([node.id()]);
  const type = nodeType(node.data());
  if (mode === "method" && (type === "file" || type === "package")) {
    node.descendants().nodes().forEach((child) => {
      ids.add(child.id());
    });
    return ids;
  }
  if (mode === "file" && type === "package") {
    node.descendants().nodes().forEach((child) => {
      ids.add(child.id());
    });
  }
  return ids;
}
