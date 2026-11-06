# Permission matrix (planned additive overwrites)

## Channel class → @everyone / Member
| Class | View | Send | Connect (voice) |
|-------|------|------|-----------------|
| Start Here (welcome/rules/how-to-start/announcements) | Yes | No (support may allow send) | — |
| Coming Soon (education-start, course-library, algo-lab, …) | Yes | **No** | — |
| Community / gaming open text | Yes | Yes | — |
| Staff-only (manager-controls, etc.) | **No** | No | Unchanged private |
| Category voice (one per public category) | Yes | — | Yes |

## Diff policy
Dry-run reports: create category/channel, set `COMING SOON` topic, deny Send for @everyone on Coming Soon, create voice if missing.
Never clear existing allow overwrites on private channels.
Never grant View on channels that currently deny @everyone unless owner allowlists them.
