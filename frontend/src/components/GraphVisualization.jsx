import { useMemo } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import { FiShare2 } from 'react-icons/fi'

const LAYOUT = {
  name: 'cose',
  animate: true,
  animationDuration: 500,
  nodeRepulsion: 8000,
  idealEdgeLength: 120,
  gravity: 0.25,
  numIter: 200,
  padding: 30,
}

const STYLESHEET = [
  {
    selector: 'node',
    style: {
      'background-color': '#6366f1',
      label: 'data(label)',
      color: '#e2e8f0',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': '10px',
      'text-margin-y': 6,
      width: 30,
      height: 30,
      'border-width': 2,
      'border-color': '#818cf8',
      'text-outline-width': 2,
      'text-outline-color': '#0f172a',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#475569',
      'target-arrow-color': '#22d3ee',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      label: 'data(label)',
      color: '#94a3b8',
      'font-size': '8px',
      'text-rotation': 'autorotate',
      'text-outline-width': 2,
      'text-outline-color': '#0f172a',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'background-color': '#22d3ee',
      'border-color': '#06b6d4',
    },
  },
]

export default function GraphVisualization({ nodes, edges }) {
  const elements = useMemo(() => {
    if (nodes.length === 0) return []

    const cyNodes = nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        type: node.properties?.entity_type || node.type,
      },
    }))

    const cyEdges = edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.subject_id,
        target: edge.object_id,
        label: edge.predicate,
      },
    }))

    return [...cyNodes, ...cyEdges]
  }, [nodes, edges])

  if (elements.length === 0) {
    return (
      <div className="card">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <FiShare2 className="text-nova-accent" />
          Graph Visualization
        </h2>
        <div className="cytoscape-container flex items-center justify-center">
          <p className="text-gray-600">
            Upload documents and build the graph to see the visualization
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <FiShare2 className="text-nova-accent" />
        Graph Visualization
        <span className="text-xs text-gray-500 ml-auto">
          {nodes.length} nodes, {edges.length} edges
        </span>
      </h2>
      <CytoscapeComponent
        elements={elements}
        stylesheet={STYLESHEET}
        layout={LAYOUT}
        className="cytoscape-container"
        userZoomingEnabled={true}
        userPanningEnabled={true}
        boxSelectionEnabled={false}
      />
    </div>
  )
}
