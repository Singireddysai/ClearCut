import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface GradientCardProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}

export function GradientCard({ children, className, delay = 0 }: GradientCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 0.4, 0.25, 1] }}
      className={cn("group relative", className)}
    >
      <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-r from-accent via-purple-500 to-pink-500 opacity-30 blur transition duration-500 group-hover:opacity-50" />
      <div className="relative rounded-xl border border-border bg-surface-elevated p-6 transition duration-200">
        {children}
      </div>
    </motion.div>
  );
}
