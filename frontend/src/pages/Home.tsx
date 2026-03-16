import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Scissors, Sparkles } from "lucide-react";
import { UploadZone } from "@/components/upload-zone";
import { JobCard } from "@/components/job-card";
import { GradientCard } from "@/components/aceternity/gradient-card";
import { GridBackground } from "@/components/aceternity/grid-background";
import { uploadVideo, listJobs, type Job } from "@/api/client";

export function Home() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshJobs = async () => {
    try {
      const { jobs: list } = await listJobs();
      setJobs(list);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshJobs();
    const t = setInterval(refreshJobs, 4000);
    return () => clearInterval(t);
  }, []);

  const handleUpload = async (file: File) => {
    const { job_id } = await uploadVideo(file);
    await refreshJobs();
    navigate(`/job/${job_id}`);
  };

  return (
    <div className="relative min-h-screen">
      <GridBackground />
      <div className="relative mx-auto max-w-3xl px-6 py-12 sm:py-16">
        <motion.header
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-center mb-12"
        >
          <motion.div
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.1, type: "spring", stiffness: 200 }}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-elevated/80 px-4 py-1.5 text-sm text-muted mb-6"
          >
            <Sparkles className="h-4 w-4 text-accent" />
            AI-powered video summaries
          </motion.div>
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
            ClearCut
          </h1>
          <p className="mt-3 text-lg text-zinc-400 max-w-xl mx-auto">
            Upload a video and get short, medium, and long AI summaries in one go.
          </p>
        </motion.header>

        <GradientCard className="mb-10" delay={0.15}>
          <UploadZone onUpload={handleUpload} />
        </GradientCard>

        <section>
          <h2 className="text-lg font-semibold text-zinc-200 mb-4 flex items-center gap-2">
            <Scissors className="h-5 w-5 text-accent" />
            Recent jobs
          </h2>
          {loading ? (
            <p className="text-muted text-sm">Loading…</p>
          ) : jobs.length === 0 ? (
            <p className="text-muted text-sm">No jobs yet. Upload a video to get started.</p>
          ) : (
            <ul className="space-y-3">
              {jobs.map((job, i) => (
                <li key={job.id}>
                  <JobCard job={job} onView={(id) => navigate(`/job/${id}`)} index={i} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
