# Trace relations

| Entity | Useful fields | Relationship to evaluate |
|---|---|---|
| Request | ID, API, arguments, call time | Which observations belong to this request? |
| Instance | Engine ID, type, first/last presence | Does required overlap exist? |
| Animation | Instance, frame, play state, engine time | Does playback cover its required interval? |
| Motion | Instance, world position, engine time | Does position agree with the specified path? |
| Event | Name, payload, engine time, subscriber | Do count, order and payload satisfy the caller contract? |
| Removal | Instance, requested time, absent time | Is absence within the allowed completion bound? |

Prefer raw timestamped rows over an implementation's completed flag. Distinguish event identity from visual identity. A useful report cites a violated relation and the minimum supporting rows without prescribing the code change. For absent events, preserve the complete observation window and subscription setup.
