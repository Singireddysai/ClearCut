import { motion } from "framer-motion";
import { Film, ChevronRight, AlertCircle, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { Job } from "@/api/client";
import { cn } from "@/lib/utils";

const statusVariant: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  completed: "success",
  failed: "destructive",
  pending: "secondary",
  uploading: "secondary",
  ingesting: "default",
  analyzing: "default",
  segmenting: "default",
  summarizing: "default",
  assembling: "default",
  evaluating: "default",
};

interface JobCardProps {
  job: Job;
  onView: (id: string) => void;
  index?: number;
}

export function JobCard({ job, onView, index = 0 }: JobCardProps) {
  const isDone = job.status === "completed" || job.status === "failed";
  const isFailed = job.status === "failed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
    >
      <Card
        className={cn(
          "overflow-hidden transition-all duration-200 hover:border-zinc-600",
          isDone && "hover:border-accent/30"
        )}
      >
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-muted">
              <Film className="h-5 w-5 text-accent" />
            </div>
            <div>
              <p className="font-medium text-zinc-100 truncate max-w-[200px]" title={job.filename}>
                {job.filename}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant={statusVariant[job.status] ?? "secondary"} className="text-xs">
                  {job.status}
                </Badge>
                {job.current_length && (
                  <span className="text-xs text-muted">({job.current_length})</span>
                )}
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onView(job.id)}
            className="shrink-0"
          >
            <ChevronRight className="h-5 w-5" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {!isDone && (
            <div className="space-y-1.5">
              <p className="text-xs text-muted">{job.current_step}</p>
              <Progress value={job.progress_pct} className="h-1.5" />
            </div>
          )}
          {isFailed && job.error && (
            <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 p-3">
              <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-sm text-red-300">{job.error}</p>
            </div>
          )}
          {job.status === "completed" && (
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <CheckCircle className="h-4 w-4" />
              Ready to download
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
