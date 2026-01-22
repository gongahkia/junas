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
