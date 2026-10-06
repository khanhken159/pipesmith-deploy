"use client";

import { Card, Empty, PassMark } from "../ui";
import { useRun } from "./RunContext";

export function EvidencePanel() {
  const { detail } = useRun();
  if (!detail) return null;
  const measured = detail.evidence.measured ?? [];
  const claimed = Array.from(new Set(detail.evidence.claimed ?? []));
  return (
    <Card title="Bằng chứng">
      <div className="evidence">
        <div className="evidence-col">
          <h3>
            Code đo <span className="badge ok">kiểm chứng tất định, 0 token</span>
          </h3>
          {measured.length === 0 && <Empty>Chưa có số đo.</Empty>}
          <ul className="measured-list">
            {measured.map((item, index) => (
              <li key={`${item.node}-${item.check}-${index}`}>
                <PassMark passed={item.passed} />
                <div>
                  <div>
                    <strong>{item.check}:</strong> {item.result}
                  </div>
                  <div className="node">{item.node}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="evidence-col">
          <h3>
            LLM nói <span className="badge warn">chưa kiểm chứng</span>
          </h3>
          {claimed.length === 0 && <Empty>Agent không kèm giải thích.</Empty>}
          <ul className="claimed-list">
            {claimed.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}
