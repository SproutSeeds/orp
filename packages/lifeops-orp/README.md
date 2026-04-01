# @lifeops/orp

`@lifeops/orp` is the bridge between ORP and Life Ops.

It reads ORP's machine-readable surfaces and turns them into:

- Life Ops-compatible agenda items
- share-ready project context
- structured prompts for outbound follow-up and project sharing

## Install

```bash
npm install @lifeops/orp
```

If you also want the Life Ops SDK:

```bash
npm install @lifeops/core @lifeops/orp
```

## What it does

- runs ORP JSON commands like `status`, `frontier state`, `frontier roadmap`, and `frontier checklist`
- maps readiness, next actions, frontier phases, and checklist items into Life Ops item objects
- derives a share-ready project input object that can be passed into `@lifeops/core`
- optionally builds a full project-share packet if you inject `buildProjectSharePacket` from `@lifeops/core`

## Quick example

```js
import { LifeOpsClient, buildProjectSharePacket } from "@lifeops/core";
import {
  createOrpConnector,
  buildOrpProjectSharePacket,
} from "@lifeops/orp";

const connector = createOrpConnector({
  repoRoot: "/abs/path/to/repo",
  orpCommand: "orp",
  projectName: "My Research Project",
  organization: "ORP",
});

const client = new LifeOpsClient({
  connectors: [connector],
});

const agenda = await client.agenda({
  timezone: "America/Chicago",
});

const sharePacket = await buildOrpProjectSharePacket({
  repoRoot: "/abs/path/to/repo",
  projectName: "My Research Project",
  repoUrl: "https://github.com/example/project",
  recipients: [
    {
      name: "Alicia",
      email: "alicia@example.com",
      whyRecipient: "You care about agent-native workflows and research tooling.",
    },
  ],
  buildProjectSharePacket,
});
```
