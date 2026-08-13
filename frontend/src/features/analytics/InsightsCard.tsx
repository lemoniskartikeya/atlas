import { Lightbulb, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useAnalyticsInsights } from "@/hooks/queries";
import type { Insight } from "@/lib/types";

/**
 * What the charts below would say if they could talk.
 *
 * Renders nothing at all when the backend has nothing it can honestly claim —
 * which is every new account. An empty "no insights yet" card would occupy the
 * top of the page to say nothing.
 */
export function InsightsCard() {
  const { data } = useAnalyticsInsights(365);
  const items = data?.insights ?? [];
  if (items.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>What your data says</CardTitle>
        <span className="text-[11px] text-ink-muted">from your own logs</span>
      </CardHeader>
      <CardBody className="space-y-2.5">
        {items.map((item) => (
          <InsightRow key={item.key} insight={item} />
        ))}
      </CardBody>
    </Card>
  );
}

function InsightRow({ insight }: { insight: Insight }) {
  const good = insight.tone === "good";
  const watch = insight.tone === "watch";
  // Matches the review card's palette rather than introducing colours.
  const color = good
    ? "rgb(var(--success))"
    : watch
      ? "#d0605e"
      : "rgb(var(--ink-faint))";
  const Icon = good ? TrendingUp : watch ? TrendingDown : Lightbulb;

  return (
    <div className="flex gap-2.5">
      <Icon size={14} className="mt-0.5 shrink-0" style={{ color }} />
      <div className="min-w-0">
        <p className="text-[13px] leading-relaxed text-ink">{insight.text}</p>
        {/* The numbers behind the claim, so it can be checked rather than trusted. */}
        <p className="mt-0.5 text-[11px] leading-relaxed text-ink-faint">{insight.evidence}</p>
      </div>
    </div>
  );
}
