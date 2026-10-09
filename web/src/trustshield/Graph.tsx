import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";

const TYPE_COLOR: Record<string, string> = {
  payment: "#3b5bdb", account: "#e8890c", phone: "#1c7ed6", url_domain: "#d6336c", upi: "#0ca678",
  campaign: "#7048e8", victim: "#868e96",
};

export const GRAPH_LEGEND = TYPE_COLOR;

export default function Graph({ data }: { data: { nodes: any[]; edges: any[] } | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !data) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...data.nodes.map((n) => ({ data: { ...n } })),
        ...data.edges.map((e) => ({ data: { ...e } })),
      ],
      style: [
        { selector: "node", style: {
          "background-color": (n: any) => TYPE_COLOR[n.data("type")] ?? "#999",
          label: "data(label)", "font-size": 9, "text-wrap": "wrap", "text-max-width": "110px",
          color: dark ? "#e8eaf1" : "#171a23", "text-valign": "bottom", "text-margin-y": 4,
          width: (n: any) => (n.data("type") === "campaign" ? 34 : n.data("type") === "payment" ? 30 : 18),
          height: (n: any) => (n.data("type") === "campaign" ? 34 : n.data("type") === "payment" ? 30 : 18),
          "border-width": (n: any) => (n.data("flagged") ? 3 : 0), "border-color": "#d6336c",
        } as any },
        { selector: "edge", style: { width: 1.2, "line-color": dark ? "#4a5068" : "#c3c8d4", "curve-style": "bezier",
          "target-arrow-shape": "triangle", "target-arrow-color": dark ? "#4a5068" : "#c3c8d4", "arrow-scale": 0.7 } },
      ],
      layout: { name: "cose", animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 70 } as any,
      wheelSensitivity: 0.2,
    });
    return () => cy.destroy();
  }, [data]);
  return (
    <div>
      <div ref={ref} className="graph" />
      <div className="legend" style={{ marginTop: 6 }}>
        {Object.entries(TYPE_COLOR).map(([k, c]) => <span key={k} style={{ ["--c" as any]: c }}>{k.replace("_", " ")}</span>)}
        <span style={{ ["--c" as any]: "transparent", outline: "none" }}>red ring = on watchlist</span>
      </div>
    </div>
  );
}
