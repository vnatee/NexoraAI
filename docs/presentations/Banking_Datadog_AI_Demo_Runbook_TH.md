# Banking Datadog + Applied AI Demo Runbook

## Demo goal

Show that a NexoraAI Operations Agent can retrieve authorized Datadog evidence,
correlate it with approved operational Knowledge, create a chart from exact tool results,
and produce an approval-ready recommendation without modifying production.

## Safety boundary

- Use a demonstration tenant and synthetic service names; do not show customer
  names, account numbers, tokens, host identifiers, or raw production logs.
- Bind the Agent only to the intended Team-owned Datadog connection and approved
  Knowledge Data Groups.
- Keep Datadog and every other integration read-only.
- Pre-test the exact prompts and time ranges on the same day as the event.
- Keep screenshots or a short recording as a fallback and label them clearly.

## Recommended scenario

Service: Mobile Banking Transfer
Symptom: P95 latency and error rate increase after a demonstration deployment.
Evidence: Datadog monitor events, latency/error time series, a synthetic change
record, and a fictional connection-pool runbook.

## Live prompts

1. Current state

   ช่วยสรุป Alert และเหตุการณ์สำคัญที่เกี่ยวข้องกับ Mobile Banking ในช่วง 60
   นาทีล่าสุด พร้อมระบุผลกระทบและข้อมูลที่ยังขาด

2. Visualization

   สร้างกราฟแนวโน้ม Alert แยกตาม Severity ในช่วงเวลาที่ตรวจสอบ และสรุปจุดเปลี่ยน
   ที่สำคัญ โดยใช้เฉพาะข้อมูลที่ดึงได้จริง

3. Correlation and Knowledge

   เชื่อม Timeline ของ Alert กับ Change ที่เกี่ยวข้อง ค้น Runbook ที่ได้รับอนุญาต
   แล้วจัดลำดับสมมติฐาน สาเหตุ หลักฐาน Gap และ Next Action ที่ต้องขออนุมัติ

## Presenter checklist

- [ ] Agent uses a tested tool-capable LLM profile.
- [ ] Datadog MCP connection test succeeds and discovered tools are visible.
- [ ] The Agent binding permits only the required read tools.
- [ ] Knowledge search is enabled for the synthetic Change and Runbook sources.
- [ ] Chart integration is enabled and tested with exact tool output.
- [ ] Each response shows source/time context and no fabricated metric.
- [ ] The final recommendation identifies owner, risk and approval requirement.
- [ ] Screenshot/video fallback is ready.
