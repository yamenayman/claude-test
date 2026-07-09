import { useEffect, useRef } from "react";

export const TYPE_COLORS = {
  concept: "#12824a",
  article: "#c9a227",
  topic: "#3a7ca5",
  source: "#ce1126",
  chunk: "#8a938d",
};

export const TYPE_LABELS = {
  concept: "مفهوم",
  article: "مادة",
  topic: "موضوع",
  source: "مصدر",
  chunk: "نص",
};

function radiusFor(node) {
  return Math.min(26, 6 + Math.sqrt(node.weight || 1) * 2.4);
}

/**
 * Hand-rolled force-directed graph on <canvas>.
 * Dependencies-free: repulsion + edge springs + centering, with pan/zoom,
 * drag, hover and click selection.
 */
export default function ForceGraph({ nodes, edges, selectedId, onSelect, highlightQuery }) {
  const canvasRef = useRef(null);
  const stateRef = useRef(null);
  const callbackRef = useRef(onSelect);
  callbackRef.current = onSelect;

  // (Re)build simulation state whenever data changes.
  useEffect(() => {
    const simNodes = nodes.map((node, index) => {
      const angle = (index / Math.max(1, nodes.length)) * Math.PI * 2;
      const spread = 120 + (index % 7) * 60;
      return {
        ...node,
        x: Math.cos(angle) * spread,
        y: Math.sin(angle) * spread,
        vx: 0,
        vy: 0,
        r: radiusFor(node),
      };
    });
    const byId = new Map(simNodes.map((node) => [node.id, node]));
    const simEdges = edges
      .map((edge) => ({ ...edge, a: byId.get(edge.source), b: byId.get(edge.target) }))
      .filter((edge) => edge.a && edge.b);
    // Node degree is used to normalize spring forces — without it, hub nodes
    // accumulate force from every edge each frame and the simulation diverges.
    for (const node of simNodes) node.degree = 0;
    for (const edge of simEdges) {
      edge.a.degree += 1;
      edge.b.degree += 1;
    }

    stateRef.current = {
      nodes: simNodes,
      edges: simEdges,
      byId,
      alpha: 1,
      scale: 1,
      tx: 0,
      ty: 0,
      autoFit: true,
      hover: null,
      dragNode: null,
      panning: false,
      lastX: 0,
      lastY: 0,
      moved: false,
    };
  }, [nodes, edges]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    let raf = 0;

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    function toWorld(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      const state = stateRef.current;
      const cx = rect.width / 2 + state.tx;
      const cy = rect.height / 2 + state.ty;
      return {
        x: (clientX - rect.left - cx) / state.scale,
        y: (clientY - rect.top - cy) / state.scale,
      };
    }

    function hitTest(clientX, clientY) {
      const state = stateRef.current;
      if (!state) return null;
      const point = toWorld(clientX, clientY);
      for (let i = state.nodes.length - 1; i >= 0; i -= 1) {
        const node = state.nodes[i];
        const dx = node.x - point.x;
        const dy = node.y - point.y;
        if (dx * dx + dy * dy <= (node.r + 4) * (node.r + 4)) return node;
      }
      return null;
    }

    function step() {
      const state = stateRef.current;
      if (!state) return;
      const { nodes: simNodes, edges: simEdges } = state;
      const alpha = state.alpha;
      if (alpha > 0.003) {
        // Repulsion (O(n^2), fine for a few hundred nodes)
        for (let i = 0; i < simNodes.length; i += 1) {
          const a = simNodes[i];
          for (let j = i + 1; j < simNodes.length; j += 1) {
            const b = simNodes[j];
            let dx = a.x - b.x;
            let dy = a.y - b.y;
            let dist2 = dx * dx + dy * dy;
            if (dist2 < 1) {
              dx = (Math.random() - 0.5) * 2;
              dy = (Math.random() - 0.5) * 2;
              dist2 = dx * dx + dy * dy;
            }
            const dist = Math.sqrt(dist2);
            const force = (900 * alpha) / dist2;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            a.vx += fx;
            a.vy += fy;
            b.vx -= fx;
            b.vy -= fy;
          }
        }
        // Springs (degree-normalized so hubs stay numerically stable)
        for (const edge of simEdges) {
          const { a, b } = edge;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const target = a.r + b.r + 60;
          const force = ((dist - target) / dist) * 0.06 * alpha * Math.min(3, edge.weight || 1);
          a.vx += (dx * force) / Math.max(1, a.degree);
          a.vy += (dy * force) / Math.max(1, a.degree);
          b.vx -= (dx * force) / Math.max(1, b.degree);
          b.vy -= (dy * force) / Math.max(1, b.degree);
        }
        // Centering + integrate (with a hard speed cap as a safety net)
        const maxSpeed = 6 + 40 * alpha;
        for (const node of simNodes) {
          node.vx -= node.x * 0.0035 * alpha;
          node.vy -= node.y * 0.0035 * alpha;
          const speed = Math.hypot(node.vx, node.vy);
          if (speed > maxSpeed) {
            node.vx = (node.vx / speed) * maxSpeed;
            node.vy = (node.vy / speed) * maxSpeed;
          }
          if (state.dragNode !== node) {
            node.x += node.vx;
            node.y += node.vy;
          }
          node.vx *= 0.86;
          node.vy *= 0.86;
        }
        state.alpha *= 0.995;
      }
      draw();
      raf = requestAnimationFrame(step);
    }

    function fitView(state, rect) {
      if (!state.nodes.length) return;
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      for (const node of state.nodes) {
        minX = Math.min(minX, node.x - node.r);
        maxX = Math.max(maxX, node.x + node.r);
        minY = Math.min(minY, node.y - node.r);
        maxY = Math.max(maxY, node.y + node.r);
      }
      const width = Math.max(1, maxX - minX);
      const height = Math.max(1, maxY - minY);
      const targetScale = Math.min(2, Math.max(0.12, Math.min((rect.width - 60) / width, (rect.height - 60) / height)));
      const targetTx = -((minX + maxX) / 2) * targetScale;
      const targetTy = -((minY + maxY) / 2) * targetScale;
      // Ease toward the target so the camera doesn't jitter while settling.
      state.scale += (targetScale - state.scale) * 0.12;
      state.tx += (targetTx - state.tx) * 0.12;
      state.ty += (targetTy - state.ty) * 0.12;
    }

    function draw() {
      const state = stateRef.current;
      if (!state) return;
      const rect = canvas.getBoundingClientRect();
      if (state.autoFit) fitView(state, rect);
      const styles = getComputedStyle(document.documentElement);
      const textColor = styles.getPropertyValue("--text").trim() || "#222";
      const mutedColor = styles.getPropertyValue("--text-3").trim() || "#888";
      const surface = styles.getPropertyValue("--surface").trim() || "#fff";

      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.save();
      ctx.translate(rect.width / 2 + state.tx, rect.height / 2 + state.ty);
      ctx.scale(state.scale, state.scale);

      const query = (highlightQuery || "").trim();
      const selected = selectedId ? state.byId.get(selectedId) : null;
      const neighborIds = new Set();
      if (selected) {
        for (const edge of state.edges) {
          if (edge.a === selected) neighborIds.add(edge.b.id);
          if (edge.b === selected) neighborIds.add(edge.a.id);
        }
      }

      // Edges
      for (const edge of state.edges) {
        const active = selected && (edge.a === selected || edge.b === selected);
        ctx.strokeStyle = active ? TYPE_COLORS[selected.type] : mutedColor;
        ctx.globalAlpha = active ? 0.85 : selected ? 0.08 : 0.22;
        ctx.lineWidth = Math.min(3.4, 0.6 + (edge.weight || 1) * 0.25) / state.scale;
        ctx.beginPath();
        ctx.moveTo(edge.a.x, edge.a.y);
        ctx.lineTo(edge.b.x, edge.b.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // Nodes
      for (const node of state.nodes) {
        const isSelected = selected && node.id === selected.id;
        const isNeighbor = neighborIds.has(node.id);
        const matches = query && node.label.includes(query);
        const dimmed = (selected && !isSelected && !isNeighbor) || (query && !matches);

        ctx.globalAlpha = dimmed ? 0.18 : 1;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
        ctx.fillStyle = TYPE_COLORS[node.type] || "#888";
        ctx.fill();
        if (isSelected || matches || node === state.hover) {
          ctx.lineWidth = 3 / state.scale;
          ctx.strokeStyle = textColor;
          ctx.stroke();
        } else {
          ctx.lineWidth = 1.4 / state.scale;
          ctx.strokeStyle = surface;
          ctx.stroke();
        }

        const showLabel =
          isSelected || isNeighbor || matches || node === state.hover || node.r > 11 || state.scale > 1.6;
        if (showLabel && !dimmed) {
          const fontSize = Math.max(10, Math.min(15, node.r + 3)) / Math.sqrt(state.scale);
          ctx.font = `700 ${fontSize}px Tajawal, Tahoma, sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillStyle = textColor;
          ctx.fillText(node.label, node.x, node.y + node.r + 3);
        }
      }
      ctx.globalAlpha = 1;
      ctx.restore();
    }

    function onPointerDown(event) {
      const state = stateRef.current;
      if (!state) return;
      canvas.setPointerCapture(event.pointerId);
      state.moved = false;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      const node = hitTest(event.clientX, event.clientY);
      if (node) {
        state.dragNode = node;
        state.alpha = Math.max(state.alpha, 0.25);
      } else {
        state.panning = true;
      }
    }

    function onPointerMove(event) {
      const state = stateRef.current;
      if (!state) return;
      const dx = event.clientX - state.lastX;
      const dy = event.clientY - state.lastY;
      if (state.dragNode) {
        if (Math.abs(dx) + Math.abs(dy) > 2) state.moved = true;
        state.dragNode.x += dx / state.scale;
        state.dragNode.y += dy / state.scale;
        state.dragNode.vx = 0;
        state.dragNode.vy = 0;
        state.alpha = Math.max(state.alpha, 0.18);
        state.lastX = event.clientX;
        state.lastY = event.clientY;
      } else if (state.panning) {
        if (Math.abs(dx) + Math.abs(dy) > 2) {
          state.moved = true;
          state.autoFit = false;
        }
        state.tx += dx;
        state.ty += dy;
        state.lastX = event.clientX;
        state.lastY = event.clientY;
      } else {
        const hover = hitTest(event.clientX, event.clientY);
        state.hover = hover;
        canvas.style.cursor = hover ? "pointer" : "grab";
      }
    }

    function onPointerUp(event) {
      const state = stateRef.current;
      if (!state) return;
      if (!state.moved) {
        const node = hitTest(event.clientX, event.clientY);
        if (callbackRef.current) callbackRef.current(node ? node.id : null);
      }
      state.dragNode = null;
      state.panning = false;
    }

    function onWheel(event) {
      event.preventDefault();
      const state = stateRef.current;
      if (!state) return;
      state.autoFit = false;
      const factor = event.deltaY < 0 ? 1.12 : 0.9;
      state.scale = Math.min(4, Math.max(0.1, state.scale * factor));
    }

    function onDoubleClick() {
      const state = stateRef.current;
      if (!state) return;
      state.autoFit = true;
      state.alpha = Math.max(state.alpha, 0.1);
    }

    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("dblclick", onDoubleClick);
    raf = requestAnimationFrame(step);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("dblclick", onDoubleClick);
    };
  }, [selectedId, highlightQuery]);

  return <canvas ref={canvasRef} className="kgCanvas" />;
}
