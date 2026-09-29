# ERD

```mermaid
erDiagram
  USER ||--|| PILGRIM_PROFILE : has
  PILGRIM_PROFILE ||--o{ LOCATION_PING : emits
  ZONE ||--o{ LOCATION_PING : contains
  ZONE ||--o{ DENSITY_RECORD : records
  PILGRIM_PROFILE ||--o{ SOS_INCIDENT : submits
  PILGRIM_PROFILE ||--o{ GROUP_MEMBERSHIP : joins
  PILGRIM_GROUP ||--o{ GROUP_MEMBERSHIP : contains
  HajjCampaign ||--o{ PILGRIM_GROUP : sponsors
```
