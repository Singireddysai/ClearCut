import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Film } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getJob, getOutputs, type Job, type OutputsResponse } from "@/api/client";
import { OutputsPanel } from "@/components/outputs-panel";
import { GridBackground } from "@/components/aceternity/grid-background";

export function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [outputs, setOutputs] = useState<OutputsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    (async () => {
      try {
        const j = await getJob(jobId);
        if (!cancelled) setJob(j);
        if (j.status === "completed") {
          const o = await getOutputs(jobId);
          if (!cancelled) setOutputs(o);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load job");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !job || job.status === "completed" || job.status === "failed") return;
    const t = setInterval(async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
        if (j.status === "completed") {
          const o = await getOutputs(jobId);
          setOutputs(o);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(t);
  }, [jobId, job?.status]);

  if (error || (!job && jobId)) {
    return (
      <div className="relative min-h-screen">
        <GridBackground />
        <div className="relative mx-auto max-w-2xl px-6 py-12">
          <Button variant="ghost" onClick={() => navigate("/")} className="gap-2 mb-6">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-red-400">{error ?? "Job not found."}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="relative min-h-screen flex items-center justify-center">
        <GridBackground />
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-muted"
        >
          Loading…
        </motion.p>
      </div>
    );
  }

  const isDone = job.status === "completed" || job.status === "failed";

  return (
    <div className="relative min-h-screen">
      <GridBackground />
      <div className="relative mx-auto max-w-2xl px-6 py-12">
        <motion.div
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          className="mb-8"
        >
          <Button variant="ghost" onClick={() => navigate("/")} className="gap-2 -ml-2">
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex items-center gap-4 mb-8"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-accent-muted">
            <Film className="h-7 w-7 text-accent" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white truncate max-w-[280px]" title={job.filename}>
              {job.filename}
            </h1>
            <p className="text-sm text-muted capitalize">{job.status}</p>
          </div>
        </motion.div>

        {!isDone && (
          <Card className="mb-8">
            <CardHeader>
              <p className="text-sm font-medium text-zinc-300">{job.current_step}</p>
              {job.current_length && (
                <p className="text-xs text-muted">Length: {job.current_length}</p>
              )}
            </CardHeader>
            <CardContent>
              <Progress value={job.progress_pct} className="h-2" />
            </CardContent>
          </Card>
        )}

        {job.status === "failed" && job.error && (
          <Card className="mb-8 border-red-500/30 bg-red-500/5">
            <CardContent className="py-4">
              <p className="text-sm text-red-300">{job.error}</p>
            </CardContent>
          </Card>
        )}

        {outputs && (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="text-lg font-semibold text-zinc-200 mb-4">Outputs</h2>
            <OutputsPanel data={outputs} jobId={job.id} />
          </motion.section>
        )}
      </div>
    </div>
  );
}
