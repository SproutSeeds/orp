export interface OrpCommandInput {
  repoRoot: string;
  args: string[];
}

export interface OrpWorkspace {
  repoRoot: string;
  status: Record<string, unknown>;
  frontierState: Record<string, unknown> | null;
  frontierRoadmap: Record<string, unknown> | null;
  frontierChecklist: Record<string, unknown> | null;
  about: Record<string, unknown> | null;
  collectedAt: string;
}

export interface LifeOpsLikeItem {
  id: string;
  kind: "event" | "communication" | "routine" | "task" | "alert" | "document";
  title: string;
  summary?: string;
  priority?: "urgent" | "high" | "normal" | "low";
  organization?: string | null;
  tags?: string[];
  source?: {
    connector?: string;
    id?: string;
    account?: string | null;
  };
  metadata?: Record<string, unknown>;
}

export interface ProjectShareInput {
  name: string;
  summary: string;
  whyNow: string;
  highlights: string[];
  proofPoints: string[];
  links: Array<{ label: string; url: string }>;
  codebases: string[];
}

export declare function runOrpJson(options: {
  repoRoot: string;
  args: string[];
  orpCommand?: string;
}): Promise<Record<string, unknown>>;

export declare function collectOrpWorkspace(options: {
  repoRoot: string;
  orpCommand?: string;
  includeAbout?: boolean;
  commandRunner?: (input: OrpCommandInput) => Promise<Record<string, unknown>>;
}): Promise<OrpWorkspace>;

export declare function mapOrpWorkspaceToItems(options: {
  workspace: OrpWorkspace;
  projectName?: string;
  organization?: string;
}): LifeOpsLikeItem[];

export declare function createOrpProjectShareInput(options: {
  workspace: OrpWorkspace;
  projectName?: string;
  summary?: string;
  repoUrl?: string;
  liveUrl?: string;
  extraHighlights?: string[];
  extraProofPoints?: string[];
  extraCodebases?: string[];
}): ProjectShareInput;

export declare function buildOrpProjectSharePacket(options: {
  repoRoot: string;
  recipients: Array<Record<string, unknown>>;
  buildProjectSharePacket: (input: Record<string, unknown>) => unknown;
  orpCommand?: string;
  includeAbout?: boolean;
  commandRunner?: (input: OrpCommandInput) => Promise<Record<string, unknown>>;
  projectName?: string;
  summary?: string;
  repoUrl?: string;
  liveUrl?: string;
  extraHighlights?: string[];
  extraProofPoints?: string[];
  extraCodebases?: string[];
  senderName?: string;
  baseTime?: string | Date | number;
}): Promise<unknown>;

export declare function createOrpConnector(options: {
  repoRoot: string;
  orpCommand?: string;
  name?: string;
  projectName?: string;
  organization?: string;
  includeAbout?: boolean;
  commandRunner?: (input: OrpCommandInput) => Promise<Record<string, unknown>>;
}): {
  name: string;
  pull(): Promise<{
    items: LifeOpsLikeItem[];
    meta: {
      workspace: OrpWorkspace;
    };
  }>;
};
