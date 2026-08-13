import { Clock } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useBehaviourProfile } from "@/hooks/queries";

/**
 * How you work, as opposed to how this week went.
 *
 * Distinct from the insights above it: those describe the current picture and
 * change week to week, these describe the person and shouldn't. Renders
 * nothing until the record actually supports a claim — a personality invented
 * from three weeks of logs would be a horoscope.
 */
export function ProfileCard() {
  const { data } = useBehaviourProfile();
  const traits = data?.traits ?? [];
  if (traits.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>How you work</CardTitle>
        <span className="text-[11px] text-ink-muted">
          last {Math.round((data?.window_days ?? 120) / 30)} months
        </span>
      </CardHeader>
      <CardBody className="space-y-2.5">
        {traits.map((trait) => (
          <div key={trait.key} className="flex gap-2.5">
            <Clock size={14} className="mt-0.5 shrink-0 text-ink-faint" />
            <div className="min-w-0">
              <p className="text-[13px] leading-relaxed text-ink">{trait.summary}</p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-ink-faint">
                {trait.evidence}
              </p>
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}
