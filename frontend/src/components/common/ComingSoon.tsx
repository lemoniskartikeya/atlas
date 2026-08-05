import { motion } from "framer-motion";
import { type LucideIcon } from "lucide-react";

export function ComingSoon({
  title,
  phase,
  description,
  icon: Icon,
}: {
  title: string;
  phase: string;
  description: string;
  icon: LucideIcon;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid min-h-[62vh] place-items-center"
    >
      <div className="glass max-w-md rounded-3xl p-10 text-center">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-accent-soft text-accent">
          <Icon size={26} />
        </div>
        <h2 className="mt-5 text-xl font-semibold text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">{description}</p>
        <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-border/10 bg-ink/5 px-3 py-1 text-[12px] text-ink-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          {phase}
        </div>
      </div>
    </motion.div>
  );
}
