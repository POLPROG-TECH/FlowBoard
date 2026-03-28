# Dashboard Guide

Complete guide to the FlowBoard interactive dashboard — tabs, settings, themes, and user interactions.

## Table of Contents

- [Overview](#overview)
- [Main Tabs](#main-tabs-8)
- [Sub-Views](#sub-views-17-total)
- [Summary Cards](#summary-cards)
- [Charts](#charts)
- [Timeline](#timeline)
- [Detail Panel](#detail-panel)
- [Settings Drawer](#settings-drawer)
- [Import / Export](#import--export)
- [Internationalization](#internationalization)
- [Keyboard Navigation](#keyboard-navigation)
- [Print Support](#print-support)

## Overview

FlowBoard generates a self-contained HTML file with all CSS and JS inline. Chart.js is loaded via CDN. The dashboard is fully interactive with client-side tab navigation, filtering, sorting, settings, and theme switching.

No server is required — open the generated HTML file directly in any modern browser.

## Main Tabs (8)

| #  | Tab            | Description                                          |
| -- | -------------- | ---------------------------------------------------- |
| 1  | Overview       | High-level summary with cards, charts, and signals   |
| 2  | Workload       | Team capacity, backlog quality, sprint readiness     |
| 3  | Sprints        | Sprint health, goals, scope changes, capacity        |
| 4  | Timeline       | Interactive Gantt with multiple swimlane modes       |
| 5  | PI View        | Program Increment Gantt with sprint slots            |
| 6  | Insights       | Risks, conflicts, blockers, delivery forecast        |
| 7  | Dependencies   | Dependency table and heatmap                         |
| 8  | Issues         | Filterable, sortable table of all issues             |

## Sub-Views (17 total)

### Overview Tab

Single view with:
- Summary cards (9 types)
- 6 charts (status, types, risk, team SP, per-person SP, sprint progress)
- Risk signals
- Product progress
- Ceremony tracker

### Workload Tab — 3 sub-tabs

| Sub-tab           | Content                                                |
| ----------------- | ------------------------------------------------------ |
| Workload          | Per-person story points and issue counts                |
| Backlog Quality   | Unestimated issues, stale items, missing priorities     |
| Sprint Readiness  | Upcoming sprint capacity and commitment analysis        |

### Sprints Tab — 4 sub-tabs

| Sub-tab                 | Content                                          |
| ----------------------- | ------------------------------------------------ |
| Sprint Health           | Velocity, burndown indicators, completion rates  |
| Sprint Goals            | Goal tracking and achievement status             |
| Scope Changes           | Issues added/removed mid-sprint                  |
| Capacity vs Commitment  | Planned vs actual capacity utilization           |

### Timeline Tab — 6 modes

| Mode        | Swimlanes                                           |
| ----------- | --------------------------------------------------- |
| Assignee    | Grouped by person                                   |
| Team        | Grouped by team                                     |
| Epic        | Grouped by epic                                     |
| Conflict    | Highlights scheduling overlaps and resource conflicts|
| Executive   | Simplified high-level view                          |
| Simulation  | What-if scenario modeling                           |

### PI View Tab

- Program Increment Gantt chart
- Sprint slots as columns
- Feature/epic progress bars
- Cross-sprint dependency lines

### Insights Tab — 4 sub-tabs

| Sub-tab           | Content                                             |
| ----------------- | --------------------------------------------------- |
| Risks             | Risk severity breakdown and aging analysis          |
| Conflicts         | Resource and scheduling conflicts                   |
| Blockers          | Blocked issues with dependency chains               |
| Delivery Forecast | Predicted completion based on velocity              |

### Dependencies Tab — 2 sub-tabs

| Sub-tab            | Content                                            |
| ------------------ | -------------------------------------------------- |
| Dependency Table   | Tabular view of all issue dependencies             |
| Dependency Heatmap | Visual matrix of cross-team/project dependencies   |

### Issues Tab

- Full issue table with all fields
- Column sorting (click headers)
- Text filter / search
- Status, type, and priority filters

## Summary Cards

9 card types displayed on the Overview tab:

| Card              | Value Shown                        |
| ----------------- | ---------------------------------- |
| Total Issues      | Count of all issues                |
| Open Issues       | Count of non-done issues           |
| Blocked           | Issues with blocker dependencies   |
| Story Points      | Total estimated story points       |
| Completed SP      | Story points in Done status        |
| Critical Risks    | Count of critical-severity risks   |
| High Risks        | Count of high-severity risks       |
| Overloaded        | People exceeding capacity threshold|
| Conflicts         | Number of scheduling conflicts     |

## Charts

6 charts rendered with Chart.js on the Overview tab:

| Chart                   | Type       | Data                              |
| ----------------------- | ---------- | --------------------------------- |
| Status Distribution     | Doughnut   | Issues by status category         |
| Issue Types             | Bar        | Issues by type (bug, story, etc.) |
| Risk Severity           | Bar        | Risks by severity level           |
| Team Story Points       | Bar        | Story points by team              |
| Story Points per Person | Bar        | Story points by assignee          |
| Sprint Progress         | Bar        | Completed vs remaining per sprint |

Charts adapt to the active theme colors. If Chart.js fails to load, a "Chart unavailable" fallback message is shown.

## Timeline

### Swimlane Modes

5 swimlane modes plus a simulation mode:

- **Assignee** — one row per person, shows all their issues
- **Team** — one row per team, aggregated view
- **Epic** — one row per epic, shows child issues
- **Conflict** — highlights resource conflicts and overlaps
- **Executive** — simplified bars for leadership review
- **Simulation** — what-if mode for drag-and-drop scenario modeling

### Controls

- **Zoom:** 25% to 400% (buttons or keyboard shortcuts)
- **Filter:** Text input to filter visible items
- **Sprint boundaries:** Vertical lines marking sprint start/end
- **Today marker:** Red vertical line at current date
- **Overlap zones:** Highlighted areas where issues conflict

### Interaction

- Click any bar to open the [Detail Panel](#detail-panel)
- Hover for tooltip with key details
- Scroll horizontally to navigate time range
- Zoom with controls or `Ctrl+Scroll`

## Detail Panel

Opens when clicking a timeline bar or issue row.

### Information Displayed

| Field        | Description                         |
| ------------ | ----------------------------------- |
| Key          | Jira issue key (e.g., PROJ-123)     |
| Title        | Issue summary                       |
| Type         | Story, Bug, Task, Epic, etc.        |
| Status       | Current status with category color  |
| Priority     | Issue priority level                |
| Assignee     | Assigned person                     |
| Team         | Team name                           |
| Sprint       | Current sprint name                 |
| Epic         | Parent epic name                    |
| Story Points | Estimated effort                    |
| Dates        | Start and end dates                 |
| Duration     | Calculated duration in days         |
| Progress     | Completion percentage               |
| Blocked      | Blocked status and blocker details  |

### Context-Aware Sections

- **Conflict mode:** Shows conflicting issues and overlap duration
- **Simulation mode:** Shows original vs simulated dates and delta

### Accessibility

- Focus trap while open (Tab cycles within the panel)
- Keyboard accessible — press `Esc` to close
- Screen reader–friendly labels and structure

## Settings Drawer

### Opening

- Click the **gear icon** in the top-right corner
- Or use the keyboard shortcut

### 5 Setting Cards

#### 1. Theme & Language

- **5 theme buttons:** Light, Dark, Midnight, Slate, System
- **2 language buttons:** English, Polish
- Theme applies immediately on selection
- Language change persists in `localStorage`

#### 2. Branding

| Setting          | Description                  |
| ---------------- | ---------------------------- |
| Title            | Dashboard main title         |
| Subtitle         | Dashboard subtitle           |
| Company          | Company name in header       |
| Primary Color    | Main accent color (hex)      |
| Secondary Color  | Secondary accent color (hex) |
| Tertiary Color   | Third accent color (hex)     |

#### 3. Layout & Tabs

- **Density:** Compact, Comfortable, or Spacious
- **8 tab toggles:** Show or hide each main tab independently

#### 4. Thresholds

| Threshold            | Default | Description                          |
| -------------------- | ------- | ------------------------------------ |
| Overload Points      | —       | SP threshold per person for overload |
| Overload Issues      | —       | Issue count threshold for overload   |
| WIP Limit            | —       | Work-in-progress limit per person    |
| Aging Days           | —       | Days before an issue is "stale"      |
| Capacity per Person  | —       | Expected SP capacity per sprint      |

#### 5. Charts & Display

- **Charts toggle:** Show or hide the charts section
- **Risk display options:** Configure risk severity visibility
- **Roadmap zoom:** Default zoom level for timeline
- **Timeline mode:** Default swimlane mode
- **Timeline display options:** Bar labels, date format, etc.

### Actions

| Action   | Behavior                                       |
| -------- | ---------------------------------------------- |
| Apply    | Applies current settings to the dashboard view |
| Reset    | Restores all settings to defaults              |
| Export   | Downloads `flowboard-config.json`              |
| Import   | Loads a JSON config file                       |
| Cancel   | Closes the drawer without applying changes     |

## Import / Export

### Export

- Serializes the current configuration to JSON
- Downloads as `flowboard-config.json`
- Includes all settings: branding, thresholds, tabs, charts, timeline, etc.
- Useful for sharing configurations across teams

### Import

- Accepts `.json` files only
- Validates JSON structure (must be a JSON object)
- Invalid JSON shows an error toast notification
- Populates settings fields from imported values
- Changes are reflected in the settings drawer immediately
- Full regeneration needed for complete effect

Themes control:
- Background and surface colors
- Text colors and contrast ratios
- Chart colors and gradients
- Card borders and shadows
- Timeline bar fills and labels
- Scrollbar styling

## Internationalization

- **Language switching:** English and Polish
- **Persistence:** Language choice saved in `localStorage`
- **Application:** Applied on next regeneration for full effect
- **Coverage:** 927 translation keys per locale
- **Scope:** All UI labels, tooltips, status text, tab names, settings labels, and error messages

## Keyboard Navigation

| Key / Action               | Behavior                                    |
| -------------------------- | ------------------------------------------- |
| `Tab`                      | Navigate between interactive elements       |
| `Enter` / `Space`          | Activate buttons and timeline bars          |
| `Escape`                   | Close panels and drawers                    |
| `Tab` from page load       | Skip-to-content link appears                |
| Focus in settings drawer   | Focus trap — Tab cycles within the drawer   |
| Focus in detail panel      | Focus trap — Tab cycles within the panel    |

## Print Support

- Trigger with `Ctrl+P` (Windows/Linux) or `Cmd+P` (macOS)
- Navigation bar, settings drawer, and overlays are hidden in print
- Page-break optimization for charts and cards
- Summary cards and charts print in a grid layout
- Timeline prints at current zoom level
