# Persistence

CONFIRMED explicit script-facing state classes:

| State class | Evidence | Limit |
| --- | --- | --- |
| Object-scoped svar | ss-svar(used,self) investigation/examination; ss-svar(opened,self) safe | Native key construction and serialization unknown |
| Global svar | player-used-workbench; discovery/tutorial flags | Global save backing store unknown |
| Bitfield/counter | safes-found/safes-opened; workbenches-found | Index identity/schema needs native check |
| Fact | player scav-anim-active / in-workbench | Runtime facts are not proven saved flags |
| Local StateScript variable | drawer has-been-opened?/item-has-been-picked? | Reader exists; writer/restore ownership unknown |
| Checkpoint | remember-dynamic-checkpoint; clear-checkpoint-record event | Serializer implementation/order unknown |
| Native collectible record | collect-treasure / mark-treasure-examined-by-id | Storage/version migration unknown |
| Task state | task-active?/task-complete? | Query is not a completion write |

The persistence call map preserves first-argument SID or prior-call result, source state and offset. HIGH CONFIDENCE: separate mechanisms coexist; one generic complete state is not a universal save operation. UNKNOWN: save/reload idempotency until tested. See ../../databases/dependencies.json for filtered call records and event_graph for checkpoint event consumers.

[Generated corpus evidence](evidence.md).
