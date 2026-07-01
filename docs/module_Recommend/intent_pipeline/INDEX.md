# Mục Lục Wiki Query Understanding

Bộ tài liệu này chỉ mô tả phần Query Understanding do nhóm này phụ trách: từ guardrail, readiness, intent extraction, semantic mapping, session/profile update, planner đến router output.

Các module sau router và các contract vận hành/API chung thuộc phạm vi nhóm khác nên không nằm trong wiki này.

## Danh sách trang

1. [00-overview.md](00-overview.md)
2. [01-domain-model.md](01-domain-model.md)
3. [02-query-understanding-pipeline.md](02-query-understanding-pipeline.md)
4. [03-guardrail-and-assistant-help.md](03-guardrail-and-assistant-help.md)
5. [04-intent-extraction-and-hidden-intent.md](04-intent-extraction-and-hidden-intent.md)
6. [05-semantic-mapping-and-tag-expansion.md](05-semantic-mapping-and-tag-expansion.md)
7. [06-profile-retention.md](06-profile-retention.md)
8. [07-router-contract.md](07-router-contract.md)

## Thứ tự đọc đề xuất

- Người mới vào phần Query Understanding: 00 -> 01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07
- Sửa extraction/profile: 04 -> 05 -> 06
- Sửa route/plan handoff: 02 -> 07
- Debug query bị chặn hoặc không build plan: 03 -> 02 -> 07

## Ranh giới trách nhiệm

Query Understanding sở hữu:

- Phân loại guardrail ở đầu pipeline.
- Kiểm tra plan readiness.
- Extract explicit intent và hidden intent.
- Map semantic preference sang tag chuẩn.
- Mở rộng runtime tags bằng tag graph.
- Update `SessionContext`.
- Merge `ActiveProfile` và retention giữa `long_term_profile` / `tagremoved_profile`.
- Build `SearchPlanResult` và `RouterResult`.

Query Understanding không sở hữu:

- Graph orchestration sau `intent_node`.
- Các module thực thi sau router.
- Payload/API cuối cho frontend.
- Tài liệu vận hành và release chung.
