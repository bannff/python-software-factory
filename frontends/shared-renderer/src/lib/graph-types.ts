export interface GraphNode {
  id: string;
  name: string;
  type: string;
  color: string;
  val: number;
  properties?: Record<string, unknown>;
}

export interface GraphLink {
  source: string;
  target: string;
  label?: string;
}
