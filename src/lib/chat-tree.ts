import { Message } from '@/types/chat';

export function getLinearHistory(nodeMap: Record<string, Message>, leafId: string): Message[] {
  const history: Message[] = [];
  let currentId: string | undefined = leafId;

  while (currentId && nodeMap[currentId]) {
    const node = nodeMap[currentId];
    history.unshift(node);
    currentId = node.parentId;
  }

  return history;
}

export function getBranchSiblings(nodeMap: Record<string, Message>, nodeId: string): string[] {
  const node = nodeMap[nodeId];
  if (!node || !node.parentId) return [nodeId];
  
  const parent = nodeMap[node.parentId];
  return parent.childrenIds || [nodeId];
}

export function addChild(nodeMap: Record<string, Message>, parentId: string, child: Message): Record<string, Message> {
  const newNodeMap = { ...nodeMap };
  
  // Add child
  newNodeMap[child.id] = { ...child, parentId };
  
  // Update parent
  if (newNodeMap[parentId]) {
    const parent = { ...newNodeMap[parentId] };
    parent.childrenIds = [...(parent.childrenIds || []), child.id];
    newNodeMap[parentId] = parent;
  }
  
  return newNodeMap;
}

export function createTreeFromLinear(messages: Message[]): { nodeMap: Record<string, Message>, leafId: string } {
  const nodeMap: Record<string, Message> = {};
  let prevId: string | undefined = undefined;
  let leafId = '';

  messages.forEach((msg, index) => {
    const node = { ...msg, parentId: prevId, childrenIds: [] };
    if (index < messages.length - 1) {
        node.childrenIds = [messages[index + 1].id];
    }
    nodeMap[msg.id] = node;
    prevId = msg.id;
    leafId = msg.id;
  });

  return { nodeMap, leafId };
}

export function generateDotTree(nodeMap: Record<string, Message>, currentLeafId: string | undefined): string {
  let dot = 'digraph G {\n';
  dot += '  rankdir=TB;\n';
  dot += '  bgcolor="transparent";\n';
  dot += '  node [fontname="monospace", fontsize=10, style="filled,rounded", fillcolor=white, penwidth=1, margin=0.2];\n';
  dot += '  edge [penwidth=1, arrowsize=0.7];\n';

  // Identify active path
  const activePath = new Set<string>();
  let curr = currentLeafId;
  while(curr && nodeMap[curr]) {
      activePath.add(curr);
      curr = nodeMap[curr].parentId;
  }

  // Sort nodes by timestamp to ensure deterministic graph (mostly)
  const sortedNodes = Object.values(nodeMap).sort((a, b) => 
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  sortedNodes.forEach(node => {
      const isActive = activePath.has(node.id);
      const isLeaf = currentLeafId === node.id;
      
      const roleLabel = node.role === 'user' ? 'USER' : 'JUNAS';
      let contentPreview = node.content.substring(0, 30).replace(/"/g, '\\"').replace(/\n/g, ' ');
      if (node.content.length > 30) contentPreview += '...';
      
      const label = `${roleLabel}\\n${contentPreview}`;
      
      const color = isActive ? '#000000' : '#aaaaaa';
      // Light theme colors by default, we rely on CSS classes ideally but Graphviz bakes colors.
      // Use generic colors that work in both modes or transparent with CSS override?
      // Graphviz SVG output has classes `node`, `edge`. We can style via CSS if we strip inline styles or use classes.
      // For now, hardcode neutral/light colors.
      const fill = isActive ? (isLeaf ? '#e6ffe6' : '#ffffff') : '#f5f5f5';
      const shape = node.role === 'user' ? 'box' : 'rect'; // rect with rounded style
      
      // Use 'class' attribute for styling hook (viz.js supports it)
      dot += `  "${node.id}" [label="${label}", shape=${shape}, color="${color}", fillcolor="${fill}", id="node_${node.id}", class="tree-node ${isActive ? 'active' : ''}"];\n`;
      
      if (node.parentId) {
          const edgeColor = isActive && activePath.has(node.parentId) ? '#000000' : '#cccccc';
          const penWidth = isActive && activePath.has(node.parentId) ? 2 : 1;
          dot += `  "${node.parentId}" -> "${node.id}" [color="${edgeColor}", penwidth=${penWidth}];\n`;
      }
  });

  dot += '}';
  return dot;
}
